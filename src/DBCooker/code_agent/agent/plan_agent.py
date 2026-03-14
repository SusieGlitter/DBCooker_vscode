# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

"""PlanAgent for software engineering tasks."""

import os
import re
import time
import json

import numpy as np
import sqlglot
import asyncio
import contextlib
import subprocess
from textwrap import dedent
from typing import override

from code_agent.agent.agent_basics import AgentError, AgentExecution, AgentStep
from code_agent.agent.base_agent import BaseAgent
from code_agent.prompt.agent_prompt import SYSTEM_PROMPT_PLAN_AGENT, USER_PROMPT_PLAN_AGENT
from code_agent.tools import tools_registry
from code_agent.tools.base import Tool, ToolResult
from code_agent.utils.config import MCPServerConfig, TraeAgentConfig
from code_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from code_agent.utils.mcp_client import MCPClient

PlanAgentToolNames = [
    "str_replace_based_edit_tool",
    "sequentialthinking",
    # "json_edit_tool",
    "task_done",
    "bash",
]


class PlanAgent(BaseAgent):
    """Plan Agent specialized for software engineering tasks."""

    def __init__(
            self,
            plan_agent_config: TraeAgentConfig,
            docker_config: dict | None = None,
            docker_keep: bool = True,
            agent_type: str = "plan_agent",
    ):
        """Initialize PlanAgent.

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
            plan_agent_config.mcp_servers_config if plan_agent_config.mcp_servers_config else None
        )
        self.allow_mcp_servers: list[str] | None = (
            plan_agent_config.allow_mcp_servers if plan_agent_config.allow_mcp_servers else []
        )
        self.mcp_tools: list[Tool] = []
        self.mcp_clients: list[MCPClient] = []  # Keep track of MCP clients for cleanup
        self.docker_config = docker_config

        self.agent_type = agent_type

        self.plan_list: list = []

        super().__init__(
            agent_config=plan_agent_config, docker_config=docker_config,
            docker_keep=docker_keep, agent_type=agent_type
        )

    async def initialise_mcp(self):
        """Async factory to create and initialize PlanAgent."""
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
    ):
        """Create a new task."""
        self._task: dict = task
        self._extra_args: dict = extra_args
        if tool_names is None and len(self._tools) == 0:
            tool_names = PlanAgentToolNames

            # Get the model provider from the LLM client
            provider = self._model_config.model_provider.provider
            self._tools: list[Tool] = [
                tools_registry[tool_name](model_provider=provider) for tool_name in tool_names
            ]
        # self._tool_caller: ToolExecutor = ToolExecutor(self._tools)

        self._initial_messages: list[LLMMessage] = []
        self._initial_messages.append(
            LLMMessage(role="system", content=self.get_system_prompt()))
        self._initial_messages.append(LLMMessage(role="user", content=self.get_initial_user_prompt()))

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

        # Finalize trajectory recording if the recorder is available
        if self._trajectory_recorder:
            self._trajectory_recorder.finalize_recording(
                agent_type=self.agent_type,
                success=execution.success, final_result=execution.final_result
            )

        return execution

    def get_system_prompt(self) -> str:
        """Get the system prompt for PlanAgent."""
        system_prompt = SYSTEM_PROMPT_PLAN_AGENT.format(database=self._task["db_name"][self._task["database"]]).strip()
        return system_prompt

    def get_initial_user_prompt(self) -> str:
        """Get the initial user prompt for PlanAgent."""
        self.self_specification = self.format_specification(self._task["func_name"],
                                                            self._task["description"], self._task["example"],
                                                            file_path=self._task["file_path"])
        self.other_specification = self.get_other_specification()
        dependency = self.get_other_dependency()
        self.dependency = self.format_dependency(dependency)

        user_prompt = USER_PROMPT_PLAN_AGENT.format(
            database=self._task["db_name"][self._task["database"]], directory=self._task["directory"],
            func_name=self._task["func_name"], self_specification=self.self_specification,
            other_specification=self.other_specification, dependency=self.dependency,
        ).strip()
        return user_prompt

    @override
    def reflect_on_result(self, tool_results: list[ToolResult]) -> str | None:
        return None

    def parse_plan_agent_output(self, llm_output) -> (bool, str):
        try:
            if "```json" in llm_output:
                pattern = r"```json\s*([\s\S]*?)\s*```"
            else:
                pattern = r"```\s*([\s\S]*?)\s*```"

            match = re.search(pattern, llm_output, re.DOTALL)
            if match:
                plan = json.loads(match.group(1).strip())["Plan"]
            else:
                plan = json.loads(llm_output.replace("```json", "")
                                  .replace("```", "").strip())["Plan"]

            return True, plan
        except Exception as e:
            print(f"Invalid JSON format: {e}")
            return False, {"Error": str(e)}

    def check_merge_rank_llm_plan(self, plan_list: list,
                                  filter_threshold: float = 0.3, coefficient=[0.2, 0.4, 0.4]) -> list:
        """
        (1) α * less file
        (2) β * correct file path
        (3) γ * correct code elements

        :param plan_list:
        :return:
        """
        file_num_list, file_incorrect_list, code_element_incorrect_list = [], [], []
        code_elements_pattern = r"Potential code elements:\s*(.*?)\s*$"
        for plan in plan_list:
            file_num, file_incorrect, code_element_incorrect = 0, 0, 0
            for file, content in plan.items():
                file_num += 1
                if not os.path.isabs(file) or not os.path.isfile(file) or not os.path.exists(file):
                    file_incorrect += 1
                code_elements_list = re.findall(code_elements_pattern, content, re.MULTILINE)
                for code_element in code_elements_list:
                    for element in code_element.split(","):
                        element = element.strip()
                        # TODO: check element in file content
                        result = self.check_code_element_by_grep(self._task["compile_folder"], element)
                        if not result["success"]:
                            code_element_incorrect += 1
            file_num_list.append(file_num)
            file_incorrect_list.append(file_incorrect)
            code_element_incorrect_list.append(code_element_incorrect)

        arr = np.array([file_num_list, file_incorrect_list, code_element_incorrect_list], dtype=float)
        score = np.zeros_like(arr)
        for i in range(arr.shape[0]):
            row = arr[i]
            min_val = np.min(row)
            max_val = np.max(row)

            if min_val == max_val:
                score[i] = coefficient[i] * 1.0
            else:
                score[i] = coefficient[i] * (1.0 - (row - min_val) / (max_val - min_val))

        score = np.sum(score, axis=0)
        order = np.argsort(score)[::-1]

        return [plan_list[no] for no in order if score[no] >= filter_threshold]

    async def get_processed_plan(self, task: dict, extra_args: dict[str, str] | None = None) -> str:
        plan_list = list()
        for no in range(self._run_steps):
            self.new_task(task, extra_args)
            execution = await self.execute_task(tools=[])
            _, plan = self.parse_plan_agent_output(execution.final_result)
            plan_list.append(plan)

        # TODO: analyze code elements (understand?) & de-duplicated plans.
        if len(plan_list) != 0:
            plan_list = self.check_merge_rank_llm_plan(plan_list)
        self.plan_list = plan_list

        plan_str = ""
        for no, plan in enumerate(plan_list):
            plan_str += f"<candidate_plan{no + 1}>\n"
            for file, content in plan.items():
                plan_str += f"<absolute_file_path>\n\t{file}\n</absolute_file_path>\n"
                plan_str += f"<plan_content>\n{dedent(content).strip()}\n</plan_content>\n"
            plan_str += f"</candidate_plan{no + 1}>\n"

        return plan_str.strip()

    @override
    def llm_indicates_task_completed(self, llm_response: LLMResponse) -> (bool, dict):
        """Check if the LLM indicates that the task is completed."""
        # if llm_response.tool_calls is None:
        #     return False
        # return any(tool_call.name == "task_done" for tool_call in llm_response.tool_calls)
        format_check, plan = self.parse_plan_agent_output(llm_response.content)
        return format_check, plan

    @override
    async def _is_task_completed(self, llm_response: LLMResponse, step: AgentStep = None) -> (bool, list[LLMMessage]):
        """Enhanced task completion detection."""
        return True, [LLMMessage(role="user", content="Plan received.")]

    @override
    async def cleanup_mcp_clients(self) -> None:
        """Clean up all MCP clients to prevent async context leaks."""
        for client in self.mcp_clients:
            with contextlib.suppress(Exception):
                # Use a generic server name for cleanup since we don't track which server each client is for
                await client.cleanup("cleanup")
        self.mcp_clients.clear()
