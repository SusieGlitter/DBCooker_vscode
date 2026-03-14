# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

from typing import override

from code_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class TaskDoneTool(Tool):
    """Tool to mark a task as done."""

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "task_done"

    @override
    def get_description(self) -> str:
        # You can write reproduce / test script to verify your solution.
        return "Report the completion of the task. Note that you cannot call this tool before any verification is done."

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return []

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        return ToolExecResult(output="Task done.")
