# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

"""Tools module for Trae Agent."""

from code_agent.tools.base import Tool, ToolCall, ToolExecutor, ToolResult
from code_agent.tools.bash_tool import BashTool
from code_agent.tools.ckg_tool import CKGTool
from code_agent.tools.edit_tool import TextEditorTool
from code_agent.tools.json_edit_tool import JSONEditTool
from code_agent.tools.sequential_thinking_tool import SequentialThinkingTool
from code_agent.tools.task_done_tool import TaskDoneTool

from code_agent.tools.database_compile_tool import DatabaseCompileTool
from code_agent.tools.database_execute_tool import DatabaseExecuteTool
from code_agent.tools.understand_tool import UnderstandTool

__all__ = [
    "Tool",
    "ToolResult",
    "ToolCall",
    "ToolExecutor",
    "BashTool",
    "TextEditorTool",
    "JSONEditTool",
    "SequentialThinkingTool",
    "TaskDoneTool",
    "CKGTool",
    "DatabaseCompileTool",
    "DatabaseExecuteTool",
    "UnderstandTool",
]

tools_registry: dict[str, type[Tool]] = {
    "bash": BashTool,
    "str_replace_based_edit_tool": TextEditorTool,
    "json_edit_tool": JSONEditTool,
    "sequentialthinking": SequentialThinkingTool,
    "task_done": TaskDoneTool,
    "ckg": CKGTool,

    # TODO: new tools to be added.
    "database_compile": DatabaseCompileTool,
    "database_execute": DatabaseExecuteTool,
    "understand_toolkit": UnderstandTool,
}
