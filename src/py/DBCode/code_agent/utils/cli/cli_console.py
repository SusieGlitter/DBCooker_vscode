# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

import asyncio
import json
import socket
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from code_agent.agent.agent_basics import AgentExecution, AgentStep, AgentStepState
from code_agent.utils.config import LakeviewConfig
from code_agent.utils.lake_view import LakeView

class ConsoleMode(Enum):
    RUN = "run"
    INTERACTIVE = "interactive"

class ConsoleType(Enum):
    SIMPLE = "simple"
    RICH = "rich"

AGENT_STATE_INFO = {
    AgentStepState.THINKING: ("blue", "🤔"),
    AgentStepState.CALLING_TOOL: ("yellow", "🔧"),
    AgentStepState.REFLECTING: ("magenta", "💭"),
    AgentStepState.COMPLETED: ("green", "✅"),
    AgentStepState.ERROR: ("red", "❌"),
}

@dataclass
class ConsoleStep:
    agent_step: AgentStep
    agent_step_printed: bool = False
    lake_view_panel_generator: asyncio.Task[Panel | None] | None = None

def generate_agent_step_table(agent_step: AgentStep) -> Table:
    """生成详细的终端步骤表格。"""
    color, emoji = AGENT_STATE_INFO.get(agent_step.state, ("white", "❓"))

    table = Table(show_header=False, width=120)
    table.add_column("Step Number", style="cyan", width=15)
    table.add_column(f"{agent_step.step_number}", style="green", width=105)

    table.add_row(
        "Status",
        f"[{color}]{emoji} Step {agent_step.step_number}: {agent_step.state.value.title()}[/{color}]",
    )

    if agent_step.llm_response and agent_step.llm_response.content:
        table.add_row("LLM Response", f"💬 {agent_step.llm_response.content}")

    if agent_step.tool_calls:
        tool_names = [f"[cyan]{call.name}[/cyan]" for call in agent_step.tool_calls]
        table.add_row("Tools", f"🔧 {', '.join(tool_names)}")

        for tool_call in agent_step.tool_calls:
            tool_call_table = Table(show_header=False, width=100)
            tool_call_table.add_column("Arguments", style="green", width=50)
            tool_call_table.add_column("Result", style="green", width=50)
            
            tool_result_str = ""
            for tool_result in agent_step.tool_results or []:
                if tool_result.call_id == tool_call.call_id:
                    tool_result_str = str(tool_result.result or "")
                    break
            tool_call_table.add_row(f"{tool_call.arguments}", tool_result_str)
            table.add_row(tool_call.name, tool_call_table)

    if agent_step.reflection:
        table.add_row("Reflection", f"💭 {agent_step.reflection}")

    if agent_step.error:
        table.add_row("Error", f"❌ {agent_step.error}")

    return table

class CLIConsole(ABC):
    """支持 UDP 通信的基类。"""
    def __init__(self, mode: ConsoleMode = ConsoleMode.RUN, lakeview_config: LakeviewConfig | None = None, udp_port: int = 9999):
        self.mode = mode
        self.set_lakeview(lakeview_config)
        self.console_step_history: dict[int, ConsoleStep] = {}
        self.agent_execution: AgentExecution | None = None
        self.udp_addr = ('127.0.0.1', udp_port)

    def _send_to_plugin(self, category: str, data: dict):
        """发送 JSON 给插件。"""
        payload = {"category": category, "data": data}
        try:
            # 使用 default=str 解决非序列化对象问题
            json_str = json.dumps(payload, default=str, ensure_ascii=False)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(json_str.encode('utf-8'), self.udp_addr)
        except:
            pass

    def _notify_plugin_step(self, agent_step: AgentStep):
        """推送 Agent 状态数据。"""
        color, emoji = AGENT_STATE_INFO.get(agent_step.state, ("white", "❓"))
        
        # 1. 建立 call_id 到 result / error 的映射
        tool_results_map: dict[str, str] = {}
        tool_errors_map: dict[str, str] = {}
        for res in (agent_step.tool_results or []):
            if res.call_id:
                tool_results_map[res.call_id] = str(res.result or "")
                if res.error:
                    tool_errors_map[res.call_id] = str(res.error)

        # 2. 构造包含 result 的工具数据
        tools_data = []
        from code_agent.tools import tools_registry
        
        for call in (agent_step.tool_calls or []):
            summary = ""
            display_in = None
            display_out = None
            # Try to get summary and display info from tool class
            tool_class = tools_registry.get(call.name)
            if tool_class:
                try:
                    # Create a temporary instance to get summary
                    # Note: get_summary should be static-like or not depend on complex init
                    temp_tool = tool_class()
                    summary = temp_tool.get_summary(call.arguments)
                    # Display-IN from tool
                    try:
                        display_in = temp_tool.get_display_in(call.arguments)
                    except Exception:
                        display_in = None
                    # Display-OUT from tool using result / error
                    try:
                        display_out = temp_tool.get_display_out(
                            tool_results_map.get(call.call_id, None),
                            tool_errors_map.get(call.call_id, None)
                        )
                    except Exception:
                        display_out = None
                except Exception:
                    # Fallback to arguments if summary fails
                    summary = ""
            
            # If no summary from tool, use fallback logic
            if not summary:
                if call.name == "bash":
                    cmd = call.arguments.get("command", "")
                    summary = cmd[:40] + "..." if len(cmd) > 40 else cmd
                elif "path" in call.arguments:
                    path = str(call.arguments.get("path", ""))
                    summary = f"{call.name}: {path.split('/')[-1]}"
                else:
                    # Final fallback: just the tool name or first few args
                    summary = f"Calling {call.name}"
            
            tools_data.append({
                "name": call.name,
                "args": call.arguments,
                "result": tool_results_map.get(call.call_id, ""),
                "summary": summary,
                "display_in": display_in,
                "display_out": display_out
            })

        step_data = {
            "step_number": agent_step.step_number,
            "state": agent_step.state.value,
            "color": color,
            "emoji": emoji,
            "content": agent_step.llm_response.content if agent_step.llm_response else "",
            "summary": agent_step.llm_response.content[:50] + "..." if agent_step.llm_response and agent_step.llm_response.content else "",
            "tools": tools_data,
            "reflection": agent_step.reflection if hasattr(agent_step, 'reflection') else "",
            "error": agent_step.error if hasattr(agent_step, 'error') else ""
        }
        self._send_to_plugin("step", step_data)

    def update_status(self, agent_step: AgentStep | None = None, agent_execution: AgentExecution | None = None):
        if agent_step:
            self._notify_plugin_step(agent_step)

    @abstractmethod
    async def start(self): pass

    def print_task_details(self, details: dict[str, str]):
        self._send_to_plugin("task", {"details": details})

    def print(self, message: str, color: str = "blue", bold: bool = False):
        self._send_to_plugin("log", {"message": message, "color": color})

    @abstractmethod
    def stop(self): pass

    def set_lakeview(self, lakeview_config: LakeviewConfig | None = None):
        self.lake_view = LakeView(lakeview_config) if lakeview_config else None
