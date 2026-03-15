# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

import asyncio
import os
from typing import override
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Input, RichLog, Static
from code_agent.agent.agent_basics import AgentExecution, AgentStep, AgentStepState
from code_agent.utils.cli.cli_console import (
    AGENT_STATE_INFO, CLIConsole, ConsoleMode, ConsoleStep, generate_agent_step_table
)

class RichCLIConsole(CLIConsole):
    def __init__(self, mode: ConsoleMode = ConsoleMode.RUN, lakeview_config=None):
        super().__init__(mode, lakeview_config)
        self.app = None
        self.agent = None

    @override
    async def start(self):
        from .rich_console import RichConsoleApp # 避免循环引用
        self.app = RichConsoleApp(self)
        await self.app.run_async()

    @override
    def update_status(self, agent_step=None, agent_execution=None):
        # 推送 UDP
        super().update_status(agent_step, agent_execution)

        # 更新 TUI
        if agent_step and self.app:
            if agent_step.step_number not in self.console_step_history:
                self.console_step_history[agent_step.step_number] = ConsoleStep(agent_step)
            if agent_step.state in [AgentStepState.COMPLETED, AgentStepState.ERROR]:
                self.app.log_agent_step(agent_step)
        
        if agent_execution and self.app and hasattr(self.app, "token_display"):
            self.app.token_display.update_tokens(agent_execution)

    @override
    def print_task_details(self, details):
        super().print_task_details(details)
        if self.app:
            content = "\n".join([f"[bold]{k}:[/bold] {v}" for k, v in details.items()])
            self.app.query_one("#execution_log", RichLog).write(Panel(content, title="Details", border_style="blue"))

    @override
    def print(self, message, color="blue", bold=False):
        super().print(message, color, bold)
        if self.app:
            msg = f"[bold]{message}[/bold]" if bold else message
            self.app.query_one("#execution_log", RichLog).write(f"[{color}]{msg}[/{color}]")

    @override
    def get_task_input(self): return None
    @override
    def get_working_dir_input(self): return os.getcwd()
    @override
    def stop(self):
        if self.app: self.app.exit()

    def set_agent_context(self, agent, *args):
        self.agent = agent