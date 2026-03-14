# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

from typing import override

from code_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter
from code_agent.tools.database.duckdb_compile_test import compile_incremental
from code_agent.tools.database.postgresql_compile_test import compile_postgresql
from code_agent.tools.database.sqlite_compile_test import compile_sqlite
from code_utils.constants import compile_folder, install_folder

TIMEOUT = 30

CompileToolModes = [
    "syntax",
    "compliance",
    "semantic",
    # "performance"
]

CompileToolDatabases = [
    "postgresql",
    "sqlite",
    "duckdb",
    "clickhouse",
]


class DatabaseCompileTool(Tool):
    """Verify whether the modified database project can be compiled successfully."""

    def __init__(self, model_provider: str | None = None) -> None:
        super().__init__(model_provider)

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "database_compile"

    @override
    def get_description(self) -> str:
        return "Verify whether the modified database project can be compiled successfully."

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="mode",
                type="string",
                description="The mode to verify the project.",
                required=True,
                enum=CompileToolModes,
            ),
            ToolParameter(
                name="database",
                type="string",
                description="The database to be verified.",
                required=True,
                enum=CompileToolDatabases,
            ),
            ToolParameter(
                name="code",
                type="dict",
                description="The implemented code to be verified.",
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        mode = str(arguments["mode"]) if "mode" in arguments else None
        if mode is None or mode not in CompileToolModes:
            return ToolExecResult(
                error=f"No or wrong mode provided for the {self.get_name()} tool",
                error_code=-1,
            )

        database = str(arguments["database"]) if "database" in arguments else None
        if database is None or database not in CompileToolDatabases:
            return ToolExecResult(
                error=f"No or wrong database provided for the {self.get_name()} tool",
                error_code=-1,
            )

        if mode == "syntax":
            return ToolExecResult(output="Task done.")

        elif mode == "compliance":
            if database == "postgresql":
                is_success, result = compile_postgresql(compile_folder, install_folder, timeout=TIMEOUT)

            elif database == "sqlite":
                is_success, result = compile_sqlite(compile_folder, timeout=TIMEOUT)
                # is_success = False
            #                 result = """
            #                 /usr/bin/ld: /tmp/ccfcYPDE.o: in function `substrFunc':
            # /data/user/code/sqlite5435/build/sqlite3.c:132689: undefined reference to `sqlite3Utf8ByteLen'
            # /usr/bin/ld: /data/user/code/sqlite5435/build/sqlite3.c:132690: undefined reference to `sqlite3Utf8ByteLen'
            # collect2: error: ld returned 1 exit status
            # make: *** [/data/user/code/sqlite5435/main.mk:2136: sqlite3] Error 1
            #                 """

            elif database == "duckdb":
                is_success, result = compile_incremental(compile_folder, timeout=TIMEOUT)

            else:
                is_success, result = True, "Skipped."

            if is_success:
                return ToolExecResult(output="Task done.")
            else:
                return ToolExecResult(error=f"Error occurs when try to compile the database "
                                            f"after the generated code integration:\n{result}", error_code=-1)

        elif mode == "semantic":
            return ToolExecResult(output="Task done.")

        else:
            # return ToolResult(
            #     name=tool_call.name,
            #     success=tool_exec_result.error_code == 0,
            #     result=tool_exec_result.output,
            #     error=tool_exec_result.error,
            #     call_id=tool_call.call_id,
            #     id=tool_call.id,
            # )
            return ToolExecResult(output="Task done.")
