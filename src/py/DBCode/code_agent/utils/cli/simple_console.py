# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

import asyncio
from typing import override
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from code_agent.agent.agent_basics import AgentExecution, AgentState, AgentStep, AgentStepState
from code_agent.utils.cli.cli_console import (
    AGENT_STATE_INFO, CLIConsole, ConsoleMode, ConsoleStep, generate_agent_step_table
)

class SimpleCLIConsole(CLIConsole):
    def __init__(self, mode: ConsoleMode = ConsoleMode.RUN, lakeview_config=None):
        super().__init__(mode, lakeview_config)
        self.console = Console()

    @override
    def update_status(self, agent_step: AgentStep | None = None, agent_execution: AgentExecution | None = None):
        # 1. 触发 UDP 通信
        super().update_status(agent_step, agent_execution)

        # 2. 原始终端逻辑
        if agent_step:
            if agent_step.step_number not in self.console_step_history:
                self.console_step_history[agent_step.step_number] = ConsoleStep(agent_step)

            if (agent_step.state in [AgentStepState.COMPLETED, AgentStepState.ERROR]
                and not self.console_step_history[agent_step.step_number].agent_step_printed):
                
                self._print_step_update(agent_step, agent_execution)
                self.console_step_history[agent_step.step_number].agent_step_printed = True

                # 异步生成 Lakeview 面板
                if self.lake_view and not self.console_step_history[agent_step.step_number].lake_view_panel_generator:
                    self.console_step_history[agent_step.step_number].lake_view_panel_generator = \
                        asyncio.create_task(self._create_lakeview_step_display(agent_step))

        self.agent_execution = agent_execution

    def _print_step_update(self, agent_step: AgentStep, agent_execution: AgentExecution | None = None):
        table = generate_agent_step_table(agent_step)
        if agent_step.llm_usage:
            table.add_row("Token Usage", f"In: {agent_step.llm_usage.input_tokens} | Out: {agent_step.llm_usage.output_tokens}")
        if agent_execution and agent_execution.total_tokens:
            table.add_row("Total Tokens", f"In: {agent_execution.total_tokens.input_tokens} | Out: {agent_execution.total_tokens.output_tokens}")
        self.console.print(table)

    @override
    async def start(self):
        while self.agent_execution is None or self.agent_execution.agent_state not in [AgentState.COMPLETED, AgentState.ERROR]:
            await asyncio.sleep(1)

        if self.lake_view and self.agent_execution:
            await self._print_lakeview_summary()
        if self.agent_execution:
            self._print_execution_summary()

    async def _print_lakeview_summary(self):
        self.console.print("\n[bold cyan]Lakeview Summary[/bold cyan]\n" + "=" * 60)
        for step in self.console_step_history.values():
            if step.lake_view_panel_generator:
                panel = await step.lake_view_panel_generator
                if panel: self.console.print(panel)

    def _print_execution_summary(self):
        if not self.agent_execution: return
        self.console.print("\n[bold green]Execution Summary[/bold green]\n" + "=" * 60)
        table = Table(show_header=False, width=60)
        table.add_row("Success", "✅ Yes" if self.agent_execution.success else "❌ No")
        table.add_row("Time", f"{self.agent_execution.execution_time:.2f}s")
        self.console.print(table)
        if self.agent_execution.final_result:
            self.console.print(Panel(Markdown(self.agent_execution.final_result), title="Final Result", border_style="green"))

    async def _create_lakeview_step_display(self, agent_step: AgentStep) -> Panel | None:
        if not self.lake_view: return None
        lv = await self.lake_view.create_lakeview_step(agent_step)
        if not lv: return None
        return Panel(f"[{lv.tags_emoji}] {lv.desc_task}\n{lv.desc_details}", title=f"Step {agent_step.step_number} (Lakeview)", border_style="blue", width=80)

    @override
    def print_task_details(self, details):
        super().print_task_details(details)
        res = "\n".join([f"[bold]{k}:[/bold] {v}" for k, v in details.items()])
        self.console.print(Panel(res, title="Task Details", border_style="blue"))

    @override
    def print(self, message, color="blue", bold=False):
        super().print(message, color, bold)
        msg = f"[bold]{message}[/bold]" if bold else message
        self.console.print(f"[{color}]{msg}[/{color}]")

    @override
    def get_task_input(self): return input("\nTask: ").strip() or None
    @override
    def get_working_dir_input(self): return input("Dir: ").strip()
    @override
    def stop(self): pass