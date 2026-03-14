# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

"""CodeAgent for software engineering tasks."""
import json
import os
import re
import time
import asyncio
import contextlib
import subprocess
from textwrap import dedent
from typing import override

from code_agent.agent.agent_basics import AgentError, AgentExecution, AgentStep, AgentState, AgentStepState
from code_agent.agent.base_agent import BaseAgent

from code_agent.tools import tools_registry
from code_agent.tools.base import Tool, ToolResult, ToolCall, ToolCallArguments
from code_agent.utils.config import MCPServerConfig, TraeAgentConfig
from code_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from code_agent.utils.mcp_client import MCPClient
from code_agent.prompt.agent_prompt import SYSTEM_PROMPT_CODE_AGENT, USER_PROMPT_CODE_AGENT, USER_PROMPT_CODE_AGENT_JSON


CodeAgentToolNames = [
    "str_replace_based_edit_tool",
    "sequentialthinking",
    "json_edit_tool",
    "task_done",
    "bash",
]


class CodeAgent(BaseAgent):
    """Code Agent specialized for software engineering tasks."""

    def __init__(
            self,
            code_agent_config: TraeAgentConfig,
            docker_config: dict | None = None,
            docker_keep: bool = True,
            agent_type: str = "code_agent",
    ):
        """Initialize CodeAgent.

        Args:
            config: Configuration object containing model parameters and other settings.
                   Required if llm_client is not provided.
            llm_client: Optional pre-configured LLMClient instance.
                       If provided, it will be used instead of creating a new one from config.
            docker_config: Optional configuration for running in a Docker environment.
        """
        self.project_path: str = ""
        self.base_commit: str | None = None
        self.must_patch: str = "false"
        self.patch_path: str | None = None
        self.mcp_servers_config: dict[str, MCPServerConfig] | None = (
            code_agent_config.mcp_servers_config if code_agent_config.mcp_servers_config else None
        )
        self.allow_mcp_servers: list[str] | None = (
            code_agent_config.allow_mcp_servers if code_agent_config.allow_mcp_servers else []
        )
        self.mcp_tools: list[Tool] = []
        self.mcp_clients: list[MCPClient] = []  # Keep track of MCP clients for cleanup
        self.docker_config = docker_config

        self.agent_type = agent_type

        # newly added (subagent).
        self.plan_agent: None = None
        self.test_agent: None = None

        self.code_format = dict()
        self.code_completed = dict()

        super().__init__(
            agent_config=code_agent_config, docker_config=docker_config,
            docker_keep=docker_keep, agent_type=agent_type
        )

    def initialize_subagent(self, plan_agent, test_agent):
        self.plan_agent = plan_agent
        self.test_agent = test_agent

    async def initialise_mcp(self):
        """Async factory to create and initialize CodeAgent."""
        await self.discover_mcp_tools()

        if self.mcp_tools:
            self._tools.extend(self.mcp_tools)

    async def discover_mcp_tools(self):
        if self.mcp_servers_config:
            for mcp_server_name, mcp_server_config in self.mcp_servers_config.items():
                if self.allow_mcp_servers is None:
                    return
                if mcp_server_name not in self.allow_mcp_servers:
                    continue
                mcp_client = MCPClient()
                try:
                    await mcp_client.connect_and_discover(
                        mcp_server_name,
                        mcp_server_config,
                        self.mcp_tools,
                        self._llm_client.provider.value,
                    )
                    # Store client for later cleanup
                    self.mcp_clients.append(mcp_client)
                except Exception:
                    # Clean up failed client
                    with contextlib.suppress(Exception):
                        await mcp_client.cleanup(mcp_server_name)
                    continue
                except asyncio.CancelledError:
                    # If the task is cancelled, clean up and skip this server
                    with contextlib.suppress(Exception):
                        await mcp_client.cleanup(mcp_server_name)
                    continue
        else:
            return

    @override
    async def new_task(
            self,
            task: dict,
            extra_args: dict[str, str] | None = None,
            tool_names: list[str] | None = None,
    ):
        """Create a new task."""
        self._task: dict = task
        self._extra_args: dict = extra_args
        if not extra_args:
            raise AgentError("Project path and issue information are required.")
        if "project_path" not in extra_args:
            raise AgentError("Project path is required")
        optional_attrs_to_set = ["base_commit", "must_patch", "patch_path"]
        for attr in optional_attrs_to_set:
            if attr in extra_args:
                setattr(self, attr, extra_args[attr])
        self.project_path = extra_args.get("project_path", "")

        if tool_names is None and len(self._tools) == 0:
            tool_names = CodeAgentToolNames

            # Get the model provider from the LLM client
            provider = self._model_config.model_provider.provider
            self._tools: list[Tool] = [
                tools_registry[tool_name](model_provider=provider) for tool_name in tool_names
            ]
        # self._tool_caller: ToolExecutor = ToolExecutor(self._tools)

        self.self_specification = self.format_specification(self._task["func_name"],
                                                            self._task["description"], self._task["example"],
                                                            file_path=self._task["file_path"])

        # TODO: add self function specification dependency (same category + semantic)
        # self.inner_specification = self.get_inner_specification()
        self.other_specification = self.get_other_specification()
        dependency = self.get_other_dependency()
        self.dependency = self.format_dependency(dependency)

        # TODO: special tool to invoke plan agent to get plan.
        # messages = await self._run_llm_step(step, messages, execution, tools)
        plan_str = await self.plan_agent.agent.get_processed_plan(task, extra_args)

        self._initial_messages: list[LLMMessage] = []
        self._initial_messages.append(
            LLMMessage(role="system", content=self.get_system_prompt()))
        self._initial_messages.append(LLMMessage(role="user", content=self.get_initial_user_prompt(plan=plan_str)))

        # If trajectory recorder is set, start recording
        if self._trajectory_recorder:
            self._trajectory_recorder.start_recording(
                agent_type=self.agent_type,
                task=task,
                provider=self._llm_client.provider.value,
                model=self._model_config.model,
                max_steps=self._max_steps,
            )
            self._trajectory_recorder.start_recording_first(task=task)

    @override
    async def execute_task(self, tools=None) -> AgentExecution:
        # """Execute the task and finalize trajectory recording."""
        execution = await super().execute_task(tools)

        # Finalize trajectory recording if recorder is available
        if self._trajectory_recorder:
            self._trajectory_recorder.finalize_recording(
                agent_type=self.agent_type,
                success=execution.success, final_result=execution.final_result
            )
            self._trajectory_recorder.finalize_recording_last(
                success=execution.success, final_result=execution.final_result
            )

        if self.patch_path is not None:
            with open(self.patch_path, "w") as patch_f:
                model_patch = self.get_git_diff()
                # patch = self.remove_patches_to_tests(model_patch)
                _ = patch_f.write(model_patch)

        return execution

    def get_system_prompt(self) -> str:
        """Get the system prompt for CodeAgent."""
        system_prompt = SYSTEM_PROMPT_CODE_AGENT.format(database=self._task["db_name"][self._task["database"]]).strip()
        return system_prompt

    def get_initial_user_prompt(self, plan=None) -> str:
        """Get the initial user prompt for CodeAgent."""
        if plan is None:
            plan = ""

        if self.tools == 0:
            user_prompt = USER_PROMPT_CODE_AGENT_JSON.format(
                database=self._task["db_name"][self._task["database"]], directory=self._task["directory"],
                func_name=self._task["func_name"], self_specification=self.self_specification,
                other_specification=self.other_specification, plan=plan, dependency=self.dependency,
            ).strip()

        else:
            user_prompt = USER_PROMPT_CODE_AGENT.format(
                database=self._task["db_name"][self._task["database"]], directory=self._task["directory"],
                func_name=self._task["func_name"], self_specification=self.self_specification,
                other_specification=self.other_specification, plan=plan, dependency=self.dependency,
            ).strip()

        return user_prompt

    def get_processed_code(self, code) -> str:
        code_str = ""
        for no, (file, content) in enumerate(code.items()):
            code_str += f"<absolute_file_path{no + 1}>\n\t{file}\n\t</absolute_file_path{no + 1}>\n"
            code_str += f"<code_content{no + 1}>\n\t{dedent(content).strip()}\n\t</code_content{no + 1}>\n"

        return code_str.strip()

    @override
    def reflect_on_result(self, tool_results: list[ToolResult]) -> str | None:
        return None

    def get_git_diff(self) -> str:
        """Get the git diff of the project."""
        # pwd = os.getcwd()
        if not os.path.isdir(self.project_path):
            return ""
        os.chdir(self.project_path)
        try:
            if not self.base_commit:
                stdout = subprocess.check_output(["git", "--no-pager", "diff"]).decode()
            else:
                stdout = subprocess.check_output(
                    ["git", "--no-pager", "diff", self.base_commit, "HEAD"]
                ).decode()
        except (subprocess.CalledProcessError, FileNotFoundError):
            stdout = ""
        # finally:
        #     os.chdir(pwd)
        return stdout

    # Copyright (c) 2024 paul-gauthier
    # SPDX-License-Identifier: Apache-2.0
    # Original remove_patches_to_tests function was released under Apache-2.0 License, with the full license text
    # available at https://github.com/Aider-AI/aider-swe-bench/blob/6e98cd6c3b2cbcba12976d6ae1b07f847480cb74/LICENSE.txt
    # Original function is at https://github.com/Aider-AI/aider-swe-bench/blob/6e98cd6c3b2cbcba12976d6ae1b07f847480cb74/tests.py#L45
    def remove_patches_to_tests(self, model_patch: str) -> str:
        """
        Remove any changes to the tests directory from the provided patch.
        This is to ensure that the model_patch does not disturb the repo's
        tests when doing acceptance testing with the `test_patch`.
        """
        lines = model_patch.splitlines(keepends=True)
        filtered_lines: list[str] = []
        test_patterns = ["/test/", "/tests/", "/testing/", "test_", "tox.ini"]
        is_tests = False

        for line in lines:
            if line.startswith("diff --git a/"):
                target_path = line.split()[-1]
                is_tests = target_path.startswith("b/") and any(
                    p in target_path for p in test_patterns
                )

            if not is_tests:
                filtered_lines.append(line)

        return "".join(filtered_lines)

    def parse_code_agent_output(self, llm_output) -> (bool, str):
        try:
            if "```json" in llm_output:
                pattern = r"```json\s*([\s\S]*?)\s*```"
            else:
                pattern = r"```\s*([\s\S]*?)\s*```"

            match = re.search(pattern, llm_output, re.DOTALL)
            if match:
                code = json.loads(match.group(1).strip())["Code"]
            else:
                code = json.loads(llm_output.replace("```json", "")
                                  .replace("```", "").strip())["Code"]

            return True, code
        except Exception as e:
            print(f"Invalid JSON format: {e}")
            return False, {"Error": str(e)}

    @override
    def llm_indicates_task_completed(self, llm_response: LLMResponse) -> (bool, dict):
        """Check if the LLM indicates that the task is completed."""
        format_check, code_dict = False, dict()
        if self.tools == 0:
            format_check, code_dict = self.parse_code_agent_output(llm_response.content)
            if format_check:
                self.code_format = code_dict
        return format_check, code_dict

    @override
    async def _is_task_completed(self, code_dict: dict, step: AgentStep) -> (bool, list[LLMMessage]):
        """Enhanced task completion detection."""
        code_str = self.get_processed_code(code_dict)

        syntax_compliance_semantic_check, messages = (await self.test_agent.agent.
                                                      test_check_code_agent(self._task, self._extra_args,
                                                                            code_dict, code_str, step))
        if syntax_compliance_semantic_check:
            self.code_format = code_dict
            self.code_completed = code_dict
            if self.must_patch == "true":
                model_patch = self.get_git_diff()
                patch = self.remove_patches_to_tests(model_patch)
                # if not patch.strip():
                #     return False, [LLMMessage(role="user", content=self.task_incomplete_message())]

        return syntax_compliance_semantic_check, messages

    @override
    def task_incomplete_message(self) -> str:
        """Return a message indicating that the task is incomplete."""
        return "ERROR! Your Patch is empty. Please provide a patch that fixes the problem."

    @override
    async def cleanup_mcp_clients(self) -> None:
        """Clean up all MCP clients to prevent async context leaks."""
        for client in self.mcp_clients:
            with contextlib.suppress(Exception):
                # Use a generic server name for cleanup since we don't track which server each client is for
                await client.cleanup("cleanup")
        self.mcp_clients.clear()
