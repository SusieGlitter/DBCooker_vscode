# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

"""Base Agent class for LLM-based agents."""
import json
import os
import subprocess
import time
import contextlib
from abc import ABC, abstractmethod
from typing import Union

import sqlglot

import sys
# sys.path = ["/data/user/program/DBCode"] + sys.path

from code_agent.agent.agent_basics import AgentExecution, AgentState, AgentStep, AgentStepState
from code_agent.agent.docker_manager import DockerManager
from code_agent.tools import tools_registry
from code_agent.tools.base import Tool, ToolCall, ToolExecutor, ToolResult
from code_agent.tools.ckg.ckg_database import clear_older_ckg
from code_agent.tools.docker_tool_executor import DockerToolExecutor
from code_agent.utils.cli import CLIConsole
from code_agent.utils.config import AgentConfig, ModelConfig
from code_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from code_agent.utils.llm_clients.llm_client import LLMClient
from code_agent.utils.trajectory_recorder import TrajectoryRecorder


class BaseAgent(ABC):
    """Base class for LLM-based agents."""

    _tool_caller: Union[ToolExecutor, DockerToolExecutor]

    def __init__(
            self, agent_config: AgentConfig, docker_config: dict | None = None,
            docker_keep: bool = True, agent_type: str = "base_agent"
    ):
        """Initialize the agent.
        Args:
            agent_config: Configuration object containing model parameters and other settings.
            docker_config: Configuration for running in a Docker environment.
        """
        self._llm_client = LLMClient(agent_config.model)
        self._model_config = agent_config.model
        self._max_steps = agent_config.max_steps
        self._run_steps = agent_config.run_steps
        self._initial_messages: list[LLMMessage] = []
        self._task: dict = {}
        self._extra_args: dict = {}
        self._tools: list[Tool] = [
            tools_registry[tool_name](model_provider=self._model_config.model_provider.provider)
            for tool_name in agent_config.tools
        ]
        self.docker_keep = docker_keep
        self.docker_manager: DockerManager | None = None
        original_tool_executor = ToolExecutor(self._tools)
        if docker_config:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # tools_dir = os.path.join(project_root, 'tools')

            tools_dir = os.path.join(project_root, "dist")

            is_interactive_mode = False
            self.docker_manager = DockerManager(
                image=docker_config.get("image"),
                container_id=docker_config.get("container_id"),
                dockerfile_path=docker_config.get("dockerfile_path"),
                docker_image_file=docker_config.get("docker_image_file"),
                workspace_dir=docker_config["workspace_dir"],
                tools_dir=tools_dir,
                interactive=is_interactive_mode,
            )
            self._tool_caller = DockerToolExecutor(
                original_executor=original_tool_executor,
                docker_manager=self.docker_manager,
                docker_tools=["bash", "str_replace_based_edit_tool", "json_edit_tool"],
                host_workspace_dir=docker_config.get("workspace_dir"),
                container_workspace_dir=self.docker_manager.container_workspace,
            )
        else:
            self._tool_caller = original_tool_executor

        self._cli_console: CLIConsole | None = None

        # Trajectory recorder
        self._trajectory_recorder: TrajectoryRecorder | None = None

        # CKG tool-specific: clear the older CKG databases
        clear_older_ckg()

        self.self_specification: str | None = None
        self.other_specification: str | None = None
        self.dependency: str | None = None

        self.agent_type = agent_type

    @property
    def llm_client(self) -> LLMClient:
        return self._llm_client

    @property
    def trajectory_recorder(self) -> TrajectoryRecorder | None:
        """Get the trajectory recorder for this agent."""
        return self._trajectory_recorder

    def set_trajectory_recorder(self, recorder: TrajectoryRecorder | None) -> None:
        """Set the trajectory recorder for this agent."""
        self._trajectory_recorder = recorder
        # Also set it on the LLM client
        self._llm_client.set_trajectory_recorder(recorder)

    @property
    def cli_console(self) -> CLIConsole | None:
        """Get the CLI console for this agent."""
        return self._cli_console

    def set_cli_console(self, cli_console: CLIConsole | None) -> None:
        """Set the CLI console for this agent."""
        self._cli_console = cli_console

    @property
    def tools(self) -> list[Tool]:
        """Get the tools available to this agent."""
        return self._tools

    @property
    def task(self) -> dict:
        """Get the current task of the agent."""
        return self._task

    @task.setter
    def task(self, value: str):
        """Set the current task of the agent."""
        self._task = value

    @property
    def initial_messages(self) -> list[LLMMessage]:
        """Get the initial messages for the agent."""
        return self._initial_messages

    @property
    def model_config(self) -> ModelConfig:
        """Get the model config for the agent."""
        return self._model_config

    @property
    def max_steps(self) -> int:
        """Get the maximum number of steps for the agent."""
        return self._max_steps

    @property
    def run_steps(self) -> int:
        """Get the number of steps for the agent."""
        return self._run_steps

    @abstractmethod
    def new_task(
            self,
            task: str,
            extra_args: dict[str, str] | None = None,
            tool_names: list[str] | None = None,
    ):
        """Create a new task."""
        pass

    async def execute_task(self, tools=None) -> AgentExecution:
        """Execute a task using the agent."""
        if self.docker_manager:
            self.docker_manager.start()

        start_time = time.time()
        execution = AgentExecution(task=self._task, steps=[])
        step: AgentStep | None = None

        try:
            messages = self._initial_messages
            step_number = 1
            execution.agent_state = AgentState.RUNNING
            if tools is None:
                tools = self._tools

            while step_number <= self._max_steps:
                step = AgentStep(step_number=step_number, state=AgentStepState.THINKING)
                try:
                    # TODO: code agent different step (messages expansion such as more dependency information)
                    # if self.agent_type == "code_agent" and step_number > 1:
                    #     tool_calls = llm_response.tool_calls
                    #     if tool_calls is not None:
                    #         return await self._tool_call_handler(tool_calls, step)
                    #     else:
                    #         return [LLMMessage(role="user", content=self.incorrect_output_format_message())]

                    messages = await self._run_llm_step(step, messages, execution, tools)
                    await self._finalize_step(
                        step, messages, execution
                    )  # record trajectory for this step and update the CLI console

                    if execution.agent_state == AgentState.COMPLETED:
                        break
                    step_number += 1
                except Exception as error:
                    import traceback
                    traceback.print_exc()

                    execution.agent_state = AgentState.ERROR
                    step.state = AgentStepState.ERROR
                    step.error = str(error)
                    await self._finalize_step(step, messages, execution)
                    break
            if step_number > self._max_steps and not execution.success:
                execution.final_result = "Task execution exceeded maximum steps without completion."
                execution.agent_state = AgentState.ERROR

        except Exception as e:
            execution.final_result = f"Agent execution failed: {str(e)}"
            import traceback
            traceback.print_exc()

        finally:
            if self.docker_manager and not self.docker_keep:
                self.docker_manager.stop()

        # Ensure tool resources are released whether an exception occurs or not.
        await self._close_tools()

        execution.execution_time = time.time() - start_time

        # Clean up any MCP clients
        with contextlib.suppress(Exception):
            await self.cleanup_mcp_clients()

        self._update_cli_console(step, execution)
        return execution

    async def _close_tools(self):
        """Release tool resources, mainly about BashTool object."""
        if self._tool_caller:
            # Ensure all tool resources are properly released.
            res = await self._tool_caller.close_tools()
            return res

    async def _run_llm_step(
            self, step: "AgentStep", messages: list["LLMMessage"], execution: "AgentExecution", tools: list[Tool] = None
    ) -> list["LLMMessage"]:
        # Display thinking state
        step.state = AgentStepState.THINKING
        self._update_cli_console(step, execution)
        # Get LLM response
        llm_response = self._llm_client.chat(messages, self._model_config, tools, agent_type=self.agent_type)
        step.llm_response = llm_response

        # Display step with LLM response
        self._update_cli_console(step, execution)

        # Update token usage
        self._update_llm_usage(llm_response, execution)
        format_check, content_dict = self.llm_indicates_task_completed(llm_response)
        if format_check:
            is_completed, messages = await self._is_task_completed(content_dict, step)
            if is_completed:
                execution.agent_state = AgentState.COMPLETED
                execution.final_result = llm_response.content
                execution.success = True
                return messages
            else:
                execution.agent_state = AgentState.RUNNING
                return messages
        else:
            # TODO: to be modified, not all function call every time?
            tool_calls = llm_response.tool_calls
            if tool_calls is not None:
                return await self._tool_call_handler(tool_calls, step)
            else:
                return [LLMMessage(role="user", content=self.incorrect_output_format_message())]

    async def _run_llm_step_branch(
            self, step: "AgentStep", messages: list["LLMMessage"], execution: "AgentExecution", tools: list[Tool] = None
    ) -> list["LLMMessage"]:
        # Display thinking state
        step.state = AgentStepState.THINKING
        self._update_cli_console(step, execution)
        # Get LLM response
        llm_response = self._llm_client.chat(messages, self._model_config, tools, agent_type=self.agent_type)
        step.llm_response = llm_response

        # Display step with LLM response
        self._update_cli_console(step, execution)

        # Update token usage
        self._update_llm_usage(llm_response, execution)
        tool_calls = llm_response.tool_calls
        if tool_calls is not None:
            return await self._tool_call_handler(tool_calls, step)
        else:
            return [LLMMessage(role="user", content=self.incorrect_output_format_message())]

    async def _finalize_step(
            self, step: "AgentStep", messages: list["LLMMessage"], execution: "AgentExecution"
    ) -> None:
        step.state = AgentStepState.COMPLETED
        self._record_handler(step, messages)
        self._update_cli_console(step, execution)
        execution.steps.append(step)

    def reflect_on_result(self, tool_results: list[ToolResult]) -> str | None:
        """Reflect on tool execution result. Override for custom reflection logic."""
        if len(tool_results) == 0:
            return None

        reflection = "\n".join(
            f"The tool execution failed with error: {tool_result.error}. Consider trying a different approach or fixing the parameters."
            for tool_result in tool_results
            if not tool_result.success
        )

        return reflection

    def llm_indicates_task_completed(self, llm_response: LLMResponse) -> (bool, dict):
        """Check if the LLM indicates that the task is completed. Override for custom logic."""
        completion_indicators = [
            "task completed",
            "task finished",
            "done",
            "completed successfully",
            "finished successfully",
        ]

        response_lower = llm_response.content.lower()
        return any(indicator in response_lower for indicator in completion_indicators), dict()

    async def _is_task_completed(self, content_dict: dict, step: AgentStep) -> (bool, list[
        LLMMessage]):  # pyright: ignore[reportUnusedParameter]
        """Check if the task is completed based on the response. Override for custom logic."""
        return True

    def task_incomplete_message(self) -> str:
        """Return a message indicating that the task is incomplete. Override for custom logic."""
        return "The task is incomplete. Please try again."

    def incorrect_output_format_message(self) -> str:
        """Return a message indicating that the generated output format is incorrect."""
        return "The output format is not a correct JSON format. Please try again."

    @abstractmethod
    async def cleanup_mcp_clients(self) -> None:
        """Clean up MCP clients. Override in subclasses that use MCP."""
        pass

    def _update_cli_console(
            self, step: AgentStep | None = None, agent_execution: AgentExecution | None = None
    ) -> None:
        if self.cli_console:
            self.cli_console.update_status(step, agent_execution)

    def _update_llm_usage(self, llm_response: LLMResponse, execution: AgentExecution):
        if not llm_response.usage:
            return
        # if execution.total_tokens is None then set it to be llm_response.usage else sum it up
        # execution.total_tokens is not None
        if not execution.total_tokens:
            execution.total_tokens = llm_response.usage
        else:
            execution.total_tokens += llm_response.usage

    def _record_handler(self, step: AgentStep, messages: list[LLMMessage]) -> None:
        if self.trajectory_recorder:
            self.trajectory_recorder.record_agent_step(
                agent_type=self.agent_type,
                step_number=step.step_number,
                state=step.state.value,
                llm_messages=messages,
                llm_response=step.llm_response,
                tool_calls=step.tool_calls,
                tool_results=step.tool_results,
                reflection=step.reflection,
                error=step.error,
            )

    async def _tool_call_handler(
            self, tool_calls: list[ToolCall] | None, step: AgentStep
    ) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        if not tool_calls or len(tool_calls) <= 0:
            messages = [
                LLMMessage(
                    role="user",
                    content="It seems that you have not completed the task.",
                )
            ]
            return messages

        step.state = AgentStepState.CALLING_TOOL
        step.tool_calls = tool_calls
        self._update_cli_console(step)

        if self._model_config.parallel_tool_calls:
            tool_results = await self._tool_caller.parallel_tool_call(tool_calls)
        else:
            tool_results = await self._tool_caller.sequential_tool_call(tool_calls)
        step.tool_results = tool_results
        self._update_cli_console(step)
        for tool_result in tool_results:
            # Add tool result to conversation
            message = LLMMessage(role="user", tool_result=tool_result)
            messages.append(message)

        reflection = self.reflect_on_result(tool_results)
        if reflection:
            step.state = AgentStepState.REFLECTING
            step.reflection = reflection

            # Display reflection
            self._update_cli_console(step)

            messages.append(LLMMessage(role="assistant", content=reflection))

        return messages

    @staticmethod
    def format_specification(func_name: str, description: str,
                             example: str, code: str = "", file_path: str = "") -> str:
        specification = list()
        if len(func_name) != 0:
            specification.append(f"<function_declaration>\n\t{func_name}\n\t</function_declaration>""")
        if len(file_path) != 0:
            specification.append(f"<candidate_function_file_path>\n\t{file_path}\n\t</candidate_function_file_path>")
        if len(description) != 0:
            specification.append(f"<function_description>\n\t{description}\n\t</function_description>")
        if len(example) != 0:
            specification.append(f"<function_example>\n\t{example}\n\t</function_example>")
        if len(code) != 0:
            specification.append(f"<function_code>\n\t{code}\n\t</function_code>")

        # specification_str = ""
        # for no, spec in enumerate(specification):
        #     specification_str += f"**{no + 1}.{spec}\n\n"
        specification_str = "\n\t".join(specification)
        return specification_str.strip()

    def format_code(self, code: dict) -> str:
        """

        :param code:
        :return:
        """
        # TODO: to be modified. code
        if len(code) == 0:
            return ""
        code = "\n\t".join(["\n\t".join([f"<absolute_file_path{no + 1}>\n\t{file}\n\t</absolute_file_path{no + 1}>\n\t"
                                         f"<code_content{no + 1}>\n\t{content}\n\t</code_content{no + 1}>"
                                         for file, content in it[1].items()]) for no, it in enumerate(code.values())])
        return code

    @staticmethod
    def format_dependency(dependency: dict):
        dependency_processed = ""
        # for func in dependency.keys():
        #     dependency_processed += f"The dependency of `{func}` is:\n"
        for no, typ in enumerate(dependency.keys()):
            dependency_processed += f"{no + 1}. {typ} Dependency:\n"
            for item in dependency[typ]:
                dependency_processed += f"\n<{typ}>\n{item}\n</{typ}>\n"
            dependency_processed += "\n\n"
        dependency_processed += "\n"

        return dependency_processed

    def get_inner_specification(self) -> str:
        func_name = self._task["func_name"]
        spec_load = self._task["spec_file"][self._task["database"]]
        with open(spec_load, "r") as rf:
            spec_data = json.load(rf)

        target_category = ""
        for item in spec_data:
            if item["keyword"] == func_name:
                target_category = item["category"]
                break

        inner_specification = list()
        for item in spec_data:
            if item["keyword"] == func_name:
                continue
            if item["category"] == target_category:
                inner_specification.append(item)

        inner_code = ""
        for item in inner_specification:
            item["code"] = self.format_code(item["code"])

        pass

    def get_other_specification(self) -> str:
        other_specification = str()
        source_db = self._task["database"]
        for target_db, file in self._task["spec_file"].items():
            try:
                if target_db == self._task["database"]:
                    continue

                source_db_sqlglot, target_db_sqlglot = source_db, target_db
                sql = f"SELECT {self._task["func_name"]}(1);"
                if source_db_sqlglot == "postgresql":
                    source_db_sqlglot = "postgres"
                if target_db_sqlglot == "postgresql":
                    target_db_sqlglot = "postgres"
                result = sqlglot.transpile(sql, read=source_db_sqlglot, write=target_db_sqlglot)[0]
                other_func_name = result.split("(")[0].split(" ")[-1]

                with open(file, "r") as rf:
                    spec_data = json.load(rf)
                for item in spec_data:
                    if item["keyword"].split("(")[0].lower() == other_func_name.lower():
                        description = item["description"]
                        example = "\n".join(item["example"]) if (
                            isinstance(item["example"], list)) else item["example"]
                        code = self.format_code(item["code"]) if "code" in item.keys() else ""
                        other_specification += f"\n\t<function_in_{self._task['db_name'][target_db]}>\n"
                        other_specification += self.format_specification(other_func_name, description, example, code)
                        other_specification += f"\n\t</function_in_{self._task['db_name'][target_db]}>\n"
                        break
            except Exception as e:
                print(f"Error in get_other_specification of `{target_db}`: {e}")

        return other_specification

    def get_other_dependency(self):
        category = self._task["category"]
        spec_load = self._task["spec_file"][self._task["database"]]
        with open(spec_load, "r") as rf:
            spec_data = json.load(rf)

        dependency_total = dict()
        for item in spec_data:
            if (item["keyword"] == self._task["func_name"]
                    or item["category"] != category):
                continue

            for func, dependency in item["element"].items():
                for typ in dependency:
                    if typ not in dependency_total:
                        dependency_total[typ] = list()
                    dependency_total[typ].extend(dependency[typ])

        for typ in dependency_total:
            dependency_total[typ] = list(set(dependency_total[typ]))

        return dependency_total

    @staticmethod
    def check_code_element_by_grep(directory, pattern, file_pattern="*", case_sensitive=True):
        try:
            cmd = ["grep"]
            if not case_sensitive:
                cmd.append("-i")  # Ignore case

            cmd.extend(["-r", "-n", pattern, directory])

            if file_pattern != "*":
                cmd.extend(["--include", file_pattern])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            if result.returncode == 0:
                return {
                    'success': True,
                    'matches': result.stdout.strip().split('\n') if result.stdout else [],
                    'error': None
                }
            elif result.returncode == 1:
                return {
                    'success': True,
                    'matches': [],  # No matches
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'matches': [],
                    'error': result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                'success': True,
                'matches': [],
                'error': 'Search timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'matches': [],
                'error': str(e)
            }


if __name__ == "__main__":
    compile_folder = "/data/user/code/sqlite5435"
    pattern = "sqlite"
    # result = BaseAgent.check_code_element_by_grep(compile_folder, pattern)

    result = BaseAgent.get_inner_specification()
    print(result)
