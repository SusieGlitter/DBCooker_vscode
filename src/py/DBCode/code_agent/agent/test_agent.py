# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

"""TestAgent for software engineering tasks."""
import json
import os
import re
import time
import asyncio
import contextlib
import subprocess
import uuid
from typing import override

from code_agent.agent.agent_basics import AgentError, AgentExecution, AgentStep, AgentStepState
from code_agent.agent.base_agent import BaseAgent

from code_agent.tools import tools_registry
from code_agent.tools.base import Tool, ToolResult, ToolCallArguments, ToolCall
from code_agent.utils.config import MCPServerConfig, TraeAgentConfig
from code_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from code_agent.utils.mcp_client import MCPClient
from code_agent.prompt.agent_prompt import SYSTEM_PROMPT_TEST_AGENT, USER_PROMPT_TEST_AGENT

from code_utils.fileControl import replace_compile_with_backup, process_list_data

TestAgentToolNames = [
    # "str_replace_based_edit_tool",
    "sequentialthinking",
    # "json_edit_tool",
    "task_done",
    # "bash",
]


class TestAgent(BaseAgent):
    """Test Agent specialized for software engineering tasks."""

    def __init__(
            self,
            test_agent_config: TraeAgentConfig,
            docker_config: dict | None = None,
            docker_keep: bool = True,
            agent_type: str = "test_agent",
    ):
        """Initialize TestAgent.

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
            test_agent_config.mcp_servers_config if test_agent_config.mcp_servers_config else None
        )
        self.allow_mcp_servers: list[str] | None = (
            test_agent_config.allow_mcp_servers if test_agent_config.allow_mcp_servers else []
        )
        self.mcp_tools: list[Tool] = []
        self.mcp_clients: list[MCPClient] = []  # Keep track of MCP clients for cleanup
        self.docker_config = docker_config

        self.agent_type = agent_type

        self.testcase_list = []

        super().__init__(
            agent_config=test_agent_config, docker_config=docker_config,
            docker_keep=docker_keep, agent_type=agent_type
        )

    async def initialise_mcp(self):
        """Async factory to create and initialize TestAgent."""
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
    def new_task(
            self,
            task: dict,
            extra_args: dict[str, str] | None = None,
            tool_names: list[str] | None = None,

            implemented_code: str = None,
            self_testcase: str = None,
            other_testcase: str = None
    ):
        """Create a new task."""
        self._task: dict = task
        self._extra_args: dict = extra_args
        if tool_names is None and len(self._tools) == 0:
            tool_names = TestAgentToolNames

            # Get the model provider from the LLM client
            provider = self._model_config.model_provider.provider
            self._tools: list[Tool] = [
                tools_registry[tool_name](model_provider=provider) for tool_name in tool_names
            ]
        # self._tool_caller: ToolExecutor = ToolExecutor(self._tools)

        self._initial_messages: list[LLMMessage] = []
        self._initial_messages.append(
            LLMMessage(role="system", content=self.get_system_prompt()))
        self._initial_messages.append(LLMMessage(role="user",
                                                 content=self.get_initial_user_prompt(implemented_code=implemented_code,
                                                                                      self_testcase=self_testcase,
                                                                                      other_testcase=other_testcase)))

        # If trajectory recorder is set, start recording
        if self._trajectory_recorder:
            self._trajectory_recorder.start_recording(
                agent_type=self.agent_type,
                task=task,
                provider=self._llm_client.provider.value,
                model=self._model_config.model,
                max_steps=self._max_steps,
            )

    @override
    async def execute_task(self, tools=None) -> AgentExecution:
        """Execute the task and finalize trajectory recording."""
        execution = await super().execute_task(tools)

        # Finalize trajectory recording if recorder is available
        if self._trajectory_recorder:
            self._trajectory_recorder.finalize_recording(
                agent_type=self.agent_type,
                success=execution.success, final_result=execution.final_result
            )

        return execution

    def get_system_prompt(self) -> str:
        """Get the system prompt for TestAgent."""
        system_prompt = SYSTEM_PROMPT_TEST_AGENT.format(database=self._task["db_name"][self._task["database"]]).strip()
        return system_prompt

    def get_initial_user_prompt(self, implemented_code=None, self_testcase=None, other_testcase=None) -> str:
        """Get the initial user prompt for TestAgent."""
        self.self_specification = self.format_specification(self._task["func_name"],
                                                            self._task["description"], self._task["example"])
        # # TODO: to be modified.
        # self.other_specification = self.get_other_specification()

        user_prompt = USER_PROMPT_TEST_AGENT.format(
            database=self._task["db_name"][self._task["database"]], directory=self._task["directory"],
            func_name=self._task["func_name"], self_specification=self.self_specification,
            implemented_code=implemented_code, self_testcase=self_testcase, other_testcase=other_testcase
        ).strip()
        return user_prompt

    def get_self_other_testcase(self):
        # TODO: to be added. load from json file.
        testcase_list = []
        # other_specification = str()
        # source_db = self._task["database"]
        # for target_db, file in self._task["spec_file"].items():
        #     try:
        #         if target_db == self._task["database"]:
        #             continue
        #
        #         source_db_sqlglot, target_db_sqlglot = source_db, target_db
        #         sql = f"SELECT {self._task["func_name"]}(1);"
        #         if source_db_sqlglot == "postgresql":
        #             source_db_sqlglot = "postgres"
        #         if target_db_sqlglot == "postgresql":
        #             target_db_sqlglot = "postgres"
        #         result = sqlglot.transpile(sql, read=source_db_sqlglot, write=target_db_sqlglot)[0]
        #         other_func_name = result.split("(")[0].split(" ")[-1]
        #
        #         with open(file, "r") as rf:
        #             spec_data = json.load(rf)
        #         for item in spec_data:
        #             if item["keyword"].split("(")[0].lower() == other_func_name.lower():
        #                 description = item["description"]
        #                 example = "\n".join(item["example"]) if (
        #                     isinstance(item["example"], list)) else item["example"]
        #                 code = self.format_code(item["code"]) if "code" in item.keys() else ""
        #                 other_specification += f"\n\n# Specification in **{self._task['db_name'][target_db]}**:\n"
        #                 other_specification += self.format_specification(other_func_name, description, example, code)
        #                 break
        #     except Exception as e:
        #         print(f"Error in get_other_specification of `{target_db}`: {e}")

        return testcase_list

    async def get_generated_testcase(self, task: dict, extra_args: dict,
                                     code_str: str, self_testcase: str, other_testcase: str) -> list:
        testcase_list = list()
        for no in range(self._run_steps):
            self.new_task(task, extra_args, implemented_code=code_str,
                          self_testcase=self_testcase, other_testcase=other_testcase)
            execution = await self.execute_task(tools=[])
            _, testcase = self.parse_test_agent_output(execution.final_result)
            testcase_list.append(testcase)

        # TODO: process de-duplicated testcases.
        if len(testcase_list) != 0:
            testcase_list = self.check_merge_rank_llm_testcase(testcase_list)

        return testcase_list

    def check_merge_rank_llm_testcase(self, testcase_list: list) -> list:
        # TODO: to be added.
        return testcase_list

    @override
    def reflect_on_result(self, tool_results: list[ToolResult]) -> str | None:
        return None

    def apply_code_changes(self, gen_code: dict) -> bool:
        origin_gen_code = [self._task["origin_code"], gen_code]

        replace_compile_with_backup(self._task["compile_folder"], self._task["backup_folder"])
        processed_files = process_list_data(origin_gen_code, self._task["database"])

        return processed_files

    def git_reset_hard(self, commit_hash="HEAD", repo_path="."):
        try:
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            result = subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"Reset Succeeded: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Reset Failed: {e.stderr}")
            return False
        finally:
            os.chdir(original_cwd)

    async def check_code_agent_syntax_compliance(self, mode: str, code_dict: dict,
                                                 step: AgentStep) -> (bool, list[LLMMessage]):
        step.state = AgentStepState.CALLING_TOOL
        self._update_cli_console(step)

        tool_name = "database_compile"
        arguments = ToolCallArguments({"mode": mode, "database": self._task["database"], "code": code_dict})
        call_id = f"call_{uuid.uuid4().hex[:16]}"
        tool_call = ToolCall(name=tool_name, call_id=call_id, arguments=arguments)
        tool_results = [await self._tool_caller.execute_tool_call(tool_call)]
        step.tool_results = tool_results

        messages: list[LLMMessage] = []
        for tool_result in tool_results:
            # Add tool result to conversation
            if not tool_result.success:
                # message = LLMMessage(role="user", tool_result=tool_result)
                message = LLMMessage(role="user", content=tool_result.error)
                messages.append(message)
        self._update_cli_console(step)

        if len(messages) == 0:
            return True, messages
        return False, messages

    async def check_code_agent_semantic(self, code_str: str, step: AgentStep) -> (bool, list[LLMMessage]):
        # TODO: self + generated test cases
        self_testcase = "[]"

        # other_testcase = self.get_self_other_testcase()
        other_testcase = "[]"

        generated_testcase = await self.get_generated_testcase(self._task, self._extra_args,
                                                               code_str, self_testcase, other_testcase)
        self.testcase_list.extend(generated_testcase)

        step.state = AgentStepState.CALLING_TOOL
        self._update_cli_console(step)

        # tool_name = "database_execute"
        # arguments = ToolCallArguments({"mode": "syntax", "database": self._task["database"]})
        # call_id = f"call_{uuid.uuid4().hex[:16]}"
        # tool_call = ToolCall(name=tool_name, call_id=call_id, arguments=arguments)
        # tool_results = [await self._tool_caller.execute_tool_call(tool_call)]
        # step.tool_results = tool_results

        messages: list[LLMMessage] = []
        # for tool_result in tool_results:
        #     # Add tool result to conversation
        #     if not tool_result.success:
        #         # message = LLMMessage(role="user", tool_result=tool_result)
        #         message = LLMMessage(role="user", content=tool_result.error)
        #         messages.append(message)
        # self._update_cli_console(step)
        #
        # reflection = self.reflect_on_result(tool_results)
        # if reflection:
        #     step.state = AgentStepState.REFLECTING
        #     step.reflection = reflection
        #
        #     # Display reflection
        #     self._update_cli_console(step)
        #
        #     messages.append(LLMMessage(role="assistant", content=reflection))

        if len(messages) == 0:
            return True, messages
        return False, messages

    async def test_check_code_agent(self, task: dict, extra_args: dict, code_dict: dict,
                                    code_str: str, step: AgentStep) -> (bool, list[LLMMessage]):
        self._task: dict = task
        self._extra_args: dict = extra_args

        # mode = "syntax"
        # check_syntax, messages = await self.check_code_agent_syntax_compliance(mode, code_dict, step)
        # if not check_syntax:
        #     return False, messages

        mode = "compliance"
        if len(code_dict) != 0:
            processed_files = self.apply_code_changes(gen_code=code_dict)
        check_compliance, messages = await self.check_code_agent_syntax_compliance(mode, code_dict, step)
        if not check_compliance:
            if len(code_dict) != 0:
                processed_files = self.apply_code_changes(gen_code=dict())
            return False, messages

        # TODO: special tool to invoke test agent.
        # check_semantic, messages = await self.check_code_agent_semantic(code_str, step)
        # if not check_semantic:
        #     processed_files = self.apply_code_changes(gen_code=dict())
        #     return False, messages

        if len(code_dict) != 0:
            processed_files = self.apply_code_changes(gen_code=dict())
        return True, messages

    def parse_test_agent_output(self, llm_output) -> (bool, str):
        try:
            if "```json" in llm_output:
                pattern = r"```json\s*([\s\S]*?)\s*```"
            else:
                pattern = r"```\s*([\s\S]*?)\s*```"

            match = re.search(pattern, llm_output, re.DOTALL)
            if match:
                test = json.loads(match.group(1).strip())["Testcase"]
            else:
                test = json.loads(llm_output.replace("```json", "")
                                  .replace("```", "").strip())["Testcase"]

            return True, test
        except Exception as e:
            print(f"Invalid JSON format: {e}")
            return False, {"Error": str(e)}

    @override
    def llm_indicates_task_completed(self, llm_response: LLMResponse) -> (bool, dict):
        """Check if the LLM indicates that the task is completed."""
        # TODO: to be removed.
        format_check, testcase = self.parse_test_agent_output(llm_response.content.replace("Code", "Testcase"))
        return format_check, testcase

    @override
    async def _is_task_completed(self, llm_response: LLMResponse, step: AgentStep = None) -> (bool, list[LLMMessage]):
        """Enhanced task completion detection."""
        return True, [LLMMessage(role="user", content="Testcase received.")]

    @override
    async def cleanup_mcp_clients(self) -> None:
        """Clean up all MCP clients to prevent async context leaks."""
        for client in self.mcp_clients:
            with contextlib.suppress(Exception):
                # Use a generic server name for cleanup since we don't track which server each client is for
                await client.cleanup("cleanup")
        self.mcp_clients.clear()
