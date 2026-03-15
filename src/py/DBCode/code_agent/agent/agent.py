import asyncio
import contextlib
from enum import Enum

from code_agent.utils.cli.cli_console import CLIConsole
from code_agent.utils.config import AgentConfig, Config
from code_agent.utils.trajectory_recorder import TrajectoryRecorder
from code_agent.vector_store.chroma_store import ChromaStore
from code_agent.vector_store.embeddings import EmbeddingManager


class AgentType(Enum):
    PlanAgent = "plan_agent"
    CodeAgent = "code_agent"
    TestAgent = "test_agent"


class Agent:
    def __init__(
            self,
            agent_type: AgentType | str,
            config: Config,
            trajectory_file: str | None = None,
            cli_console: CLIConsole | None = None,
            docker_config: dict | None = None,
            docker_keep: bool = True,
    ):
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)
        self.agent_type: AgentType = agent_type

        # Set up trajectory recording
        if trajectory_file is not None:
            if isinstance(trajectory_file, TrajectoryRecorder):
                self.trajectory_file: str = str(trajectory_file.trajectory_path)
                self.trajectory_recorder: TrajectoryRecorder = trajectory_file
            else:
                self.trajectory_file: str = trajectory_file
                self.trajectory_recorder: TrajectoryRecorder = TrajectoryRecorder(trajectory_file)
        else:
            # Auto-generate trajectory file path
            self.trajectory_recorder = TrajectoryRecorder()
            self.trajectory_file = self.trajectory_recorder.get_trajectory_path()

        match self.agent_type:
            case AgentType.PlanAgent:
                if config.plan_agent is None:
                    raise ValueError("plan_agent_config is required for PlanAgent")
                from .plan_agent import PlanAgent

                self.agent_config: AgentConfig = config.plan_agent
                self.agent: PlanAgent = PlanAgent(
                    self.agent_config, docker_config=docker_config,
                    docker_keep=docker_keep, agent_type=AgentType.PlanAgent.value
                )
                self.agent.set_cli_console(cli_console)

            case AgentType.CodeAgent:
                if config.code_agent is None:
                    raise ValueError("code_agent_config is required for CodeAgent")
                from .code_agent import CodeAgent

                self.agent_config: AgentConfig = config.code_agent
                self.agent: CodeAgent = CodeAgent(
                    self.agent_config, docker_config=docker_config,
                    docker_keep=docker_keep, agent_type=AgentType.CodeAgent.value
                )
                self.agent.set_cli_console(cli_console)

            case AgentType.TestAgent:
                if config.test_agent is None:
                    raise ValueError("test_agent_config is required for TestAgent")
                from .test_agent import TestAgent

                self.agent_config: AgentConfig = config.test_agent
                self.agent: TestAgent = TestAgent(
                    self.agent_config, docker_config=docker_config,
                    docker_keep=docker_keep, agent_type=AgentType.TestAgent.value
                )
                self.agent.set_cli_console(cli_console)

        if cli_console:
            if (config.plan_agent.enable_lakeview or
                    config.code_agent.enable_lakeview or config.test_agent.enable_lakeview):
                cli_console.set_lakeview(config.lakeview)
            else:
                cli_console.set_lakeview(None)

        self.agent.set_trajectory_recorder(self.trajectory_recorder)

        # self.vector_database = ChromaStore(persist_directory=config.vector_database.persist_directory)
        # model_config = {
        #     "name": config.embeddings.model,
        #     "model_provider": config.embeddings.model_provider.provider,
        #     "api_key": config.embeddings.model_provider.api_key,
        #     "base_url": config.embeddings.model_provider.base_url,
        # }
        # self.embedding_model = EmbeddingManager(model_name=config.embeddings.model,
        #                                         model_config=model_config)

    async def run(
            self,
            task: dict,
            extra_args: dict[str, str] | None = None,
            tool_names: list[str] | None = None,
    ):
        await self.agent.new_task(task, extra_args, tool_names)

        if self.agent.allow_mcp_servers:
            if self.agent.cli_console:
                self.agent.cli_console.print("Initialising MCP tools...")
            await self.agent.initialise_mcp()

        if self.agent.cli_console:
            task_details = {
                "Task": task,
                "Model Provider": self.agent_config.model.model_provider.provider,
                "Model": self.agent_config.model.model,
                "Max Steps": str(self.agent_config.max_steps),
                "Trajectory File": self.trajectory_file,
                "Tools": ", ".join([tool.name for tool in self.agent.tools]),
            }
            if extra_args:
                for key, value in extra_args.items():
                    task_details[key.capitalize()] = value
            self.agent.cli_console.print_task_details(task_details)

        cli_console_task = (
            asyncio.create_task(self.agent.cli_console.start()) if self.agent.cli_console else None
        )

        try:
            if len(self.agent.tools) == 0:
                execution = await self.agent.execute_task(tools=[])
            else:
                execution = await self.agent.execute_task(tools=self.agent.tools)
            if len(self.agent.tools) == 0 and self.agent_type.name == "CodeAgent":
                execution.final_result = self.agent.code_completed
        finally:
            # Ensure MCP cleanup happens even if execution fails
            with contextlib.suppress(Exception):
                await self.agent.cleanup_mcp_clients()

        if cli_console_task:
            await cli_console_task

        return execution
