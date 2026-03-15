# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

import os
import re
import subprocess
from typing import override

import math
# import understand

from code_agent.tools.base import Tool, ToolCallArguments, ToolExecResult, ToolParameter


class UnderstandTool(Tool):
    """Tool to mark a task as done."""

    def __init__(self, model_provider: str | None = None, language: str = None, project_root: str = None) -> None:
        self.language = language
        self.project_root = project_root
        self.project_name = os.path.basename(self.project_root)
        self.udb_path = os.path.join(os.path.dirname(self.project_root), f"{self.project_name}.und")

        if not os.path.exists(self.udb_path):
            self.db = self.create_udb()
        self.db = understand.open(self.udb_path)

        super().__init__(model_provider)

    def create_udb(self):
        try:
            subprocess.check_output(
                "und create -db {udb_path} -languages {lang}".format(udb_path=self.udb_path,
                                                                     lang=self.language),
                shell=True)
            subprocess.check_output("und add -db {udb_path} {project} analyze -all".format(
                udb_path=self.udb_path, project=self.project_root), shell=True)
        except subprocess.CalledProcessError:
            import traceback
            traceback.print_exc()

            raise Exception("Failed to create udb file.")

        print("udb created")

    def prune_function_implementation(self, code):
        # Pattern 1: Match constructors and destructors (with parameter lists and initialization lists)
        pattern1 = r'(\w+::)?\w+\([^;{]*\)\s*(?::[^{]*)?\s*\{[^}]*\}'

        # Pattern 2: Match ordinary member function implementations
        pattern2 = r'(\w+(?:<[^>]*>)?\s+)?(\w+::)?\w+\([^;{]*\)\s*(?:const\s*)?\{[^}]*\}'

        # Pattern 3: Match function implementations with complex return types
        pattern3 = r'(\w+(?:::\w+)?\s+)+(\w+::)?\w+\([^;{]*\)\s*(?:const\s*)?\{[^}]*\}'

        def extract_declaration(function_impl):
            """Extract declaration part from function implementation"""
            # Find the position of the first {
            brace_pos = function_impl.find('{')
            if brace_pos != -1:
                # Return the part before { plus semicolon
                declaration = function_impl[:brace_pos].strip()
                # Ensure it ends with semicolon
                if not declaration.endswith(';'):
                    declaration += ';'
                return declaration
            return function_impl

        # Process complex patterns first, then simple ones
        cleaned_code = code
        for pattern in [pattern1, pattern2, pattern3]:
            cleaned_code = re.sub(pattern, lambda m: extract_declaration(m.group()), cleaned_code, flags=re.DOTALL)

        return cleaned_code

    def format_dependency_info(self, entity, is_pruned):
        kindname = entity.kindname()
        # const unsigned char * sqlite3_value_text(sqlite3_value *pVal)
        if "Function" in kindname:
            if is_pruned:
                return_type = entity.type() or "void"
                parameters = entity.parameters() or "void"
                func_name = entity.longname()
                dependency = f"{return_type} {func_name}({parameters})"
            else:
                dependency = entity.contents()

        # #define UNUSED_PARAMETER(x) (void)(x)
        elif "Macro" in kindname:
            if (entity.longname().startswith("assert") or
                    entity.longname().startswith("__ASSERT")):
                return None

            if entity.parameters() is not None:
                dependency = f"#define {entity.longname()}({entity.parameters()}) {entity.value()}"
            elif entity.value() is not None:
                dependency = f"#define {entity.longname()} {entity.value()}"
            else:
                dependency = f"#define {entity.longname()}"

        # typedef sqlite3_int64 i64
        elif "Typedef" in kindname:
            dependency = f"typedef {entity.type()} {entity.longname()}"

        elif "Namespace" in kindname:
            if len(entity.contents()) == 0:
                dependency = f"namespace {entity.longname()}"
            else:
                if is_pruned:
                    dependency = f"{self.prune_function_implementation(entity.contents())}"
                else:
                    dependency = entity.contents()

        elif "Class" in kindname:
            if is_pruned:
                dependency = f"{self.prune_function_implementation(entity.contents())}"
            else:
                dependency = entity.contents()

        elif "Struct" in kindname:
            if is_pruned:
                dependency = f"{self.prune_function_implementation(entity.contents())}"
            else:
                dependency = entity.contents()

        elif "Type" in kindname:
            dependency = entity.longname()

        elif "Enum" in kindname:
            dependency = entity.contents()

        elif "Object" in kindname or "Parameter" in kindname or "File" in kindname:
            dependency = None

        else:
            print("type:", kindname, entity.type(), entity.name(), entity.contents(), entity.value())
            dependency = None

        return dependency

    def get_file_all_dependencies(self, file_path, max_layer=1, is_pruned=True):
        file_ent = self.db.lookup(file_path, "File")[0]

        all_kind = set()
        all_dependencies = dict()

        def get_dependencies_recursive(entity, visited, layer):
            if layer > max_layer:
                return
            if entity.id() in visited:
                return
            visited.add(entity.id())

            for ref in entity.refs():
                entity = ref.ent()
                dependency = self.format_dependency_info(entity, is_pruned)
                if dependency is not None:
                    all_kind.add(entity.kindname())
                    kindname = entity.kindname()
                    if "Function" in kindname:
                        kindname = "Function"
                    if "Macro" in kindname:
                        kindname = "Macro"
                    if "Typedef" in kindname:
                        kindname = "Typedef"
                    if "Namespace" in kindname:
                        kindname = "Namespace"
                    if "Class" in kindname:
                        kindname = "Class"
                    if "Struct" in kindname:
                        kindname = "Struct"
                    if "Type" in kindname:
                        kindname = "Type"
                    if "Enum" in kindname:
                        kindname = "Enum"

                    if "Object" in kindname:
                        kindname = "Object"
                    if "Parameter" in kindname:
                        kindname = "Parameter"
                    if "File" in kindname:
                        kindname = "File"

                    if kindname not in all_dependencies.keys():
                        all_dependencies[kindname] = set()
                    all_dependencies[kindname].add(dependency)

                get_dependencies_recursive(entity, visited, layer + 1)

        get_dependencies_recursive(file_ent, set(), 1)
        for kindname in all_dependencies.keys():
            all_dependencies[kindname] = sorted(list(all_dependencies[kindname]))
        all_kind = sorted(list(all_kind))

        return all_dependencies, all_kind

    def get_function_declaration(self, func_name, kind="Function", is_pruned=True):
        func_ent = self.db.lookup(func_name, kind)[0]
        declaration = self.format_dependency_info(func_ent, is_pruned)
        return declaration

    def get_function_all_dependencies(self, func_name, kind="Function", is_pruned=True):
        """
        [(ref.ent().simplename(), ref.ent().contents(), ref.ent().type(), ref.ent().value()) for ref in func_ent.refs() if ref.ent().kindname() == "Local Object"]
        set([ref.ent().kindname() for ref in func_ent.refs()])
        """
        dependencies_dict = dict()
        func_ent = self.db.lookup(func_name, kind)[0]
        for ref in func_ent.refs():
            if func_name == ref.ent().longname():
                continue

            kindname = ref.ent().kindname()
            if "Function" in kindname:
                kindname = "Function"
            if "Macro" in kindname:
                kindname = "Macro"
            if "Typedef" in kindname:
                kindname = "Typedef"
            if "Namespace" in kindname:
                kindname = "Namespace"
            if "Class" in kindname:
                kindname = "Class"
            if "Struct" in kindname:
                kindname = "Struct"
            if "Type" in kindname:
                kindname = "Type"
            if "Enum" in kindname:
                kindname = "Enum"

            if "Object" in kindname:
                kindname = "Object"
            if "Parameter" in kindname:
                kindname = "Parameter"
            if "File" in kindname:
                kindname = "File"

            dependency = self.format_dependency_info(ref.ent(), is_pruned)
            if dependency is None or len(dependency) == 0:
                continue

            if kindname not in dependencies_dict.keys():
                dependencies_dict[kindname] = set()
            dependencies_dict[kindname].add(dependency)

        for kindname in dependencies_dict.keys():
            dependencies_dict[kindname] = sorted(list(dependencies_dict[kindname]))

        return dependencies_dict

    def get_data_control_content(self, analyze_file, function_name, row=None):
        db = self.db
        content = {}
        vis = set()
        for file in db.ents("File"):
            abs_path = file.longname()
            if abs_path != analyze_file:
                continue
            file_name = os.path.basename(abs_path)

            start = math.inf
            end = -math.inf
            for ref in file.filerefs():
                ref_ent_name = ref.ent().name()
                if function_name != ref_ent_name:
                    continue

                kind = ref.kindname()
                if kind == "Define":
                    start = min(start, ref.line())
                elif kind == "End":
                    end = max(end, ref.line())

            if end == -math.inf and row is not None:
                end = start + row

            target_lines_set = set([i for i in range(start - 1, end + 1)])

            for ref in file.filerefs():
                ref_ent_name = ref.ent().name()
                if function_name != ref_ent_name:
                    continue

                # if ref_ent_name == file_name:
                #     continue

                # ref_line = ref.line()
                # if ref_line not in target_lines_set or ref.scope().kindname() == "File":
                #     continue

                # if ref.isforward():
                #     continue

                kind = ref.kindname()
                if kind == "Begin" or kind == "End":
                    continue

                sc = ref.ent()
                if sc.kindname() == "Macro":
                    ct = f"#define {sc.longname()} {sc.value()}" if sc.value() else "#define " + sc.longname()
                else:
                    ct = sc.contents()

                while sc and sc.kindname() != "File":
                    sc = sc.parent()

                if len(ct) > 0:
                    if ct in vis:
                        continue
                    vis.add(ct)

                    if not sc:
                        continue

                    name = sc.longname()
                    if name in content:
                        content[name] += "\n" + ct
                    else:
                        content[name] = ct

        return content

    @override
    def get_model_provider(self) -> str | None:
        return self._model_provider

    @override
    def get_name(self) -> str:
        return "understand_toolkit"

    @override
    def get_description(self) -> str:
        return "Report the completion of the task. Note that you cannot call this tool before any verification is done. You can write reproduce / test script to verify your solution."

    @override
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                # description=f"The commands to run. Allowed options are: {', '.join(EditToolSubCommands)}.",
                required=True,
                # enum=EditToolSubCommands,
            ),
            ToolParameter(
                name="file_text",
                type="string",
                description="Required parameter of `create` command, with the content of the file to be created.",
            ),
        ]

    @override
    async def execute(self, arguments: ToolCallArguments) -> ToolExecResult:
        return ToolExecResult(output="Task done.")


if __name__ == "__main__":
    tool = UnderstandTool()

    # sqlite: upperFunc, substrFunc
    # postgresql: text_substr, text_substring
    # deps = tool.get_function_all_dependencies("text_substring")

    file_path = "/data/user/code/sqlite/src/func.c"
    deps = tool.get_file_all_dependencies(file_path=file_path)
    print(deps)
