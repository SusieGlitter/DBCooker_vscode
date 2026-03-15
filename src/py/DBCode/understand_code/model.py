import json
import re

import math
import os
import subprocess
import ast

import git
import pandas as pd
from simhash import SimhashIndex
from tqdm import tqdm

from code_utils.constants import understand_dir
from understand_code.project_analyze.utils import build_dependency_tree, build_commit_dependency_tree

# os.add_dll_directory(understand_dir)  # windows only
# import understand


class UnderstandRepo:
    def __init__(self, language, project_root):
        self.language = language  # Language
        self.project_root = project_root  # Repository directory
        self.project_name = os.path.basename(project_root)  # Repository name
        # self.udb_path = os.path.join(project_root, f"{self.project_name}.und")  # Database file save location, needs to be in repository directory
        self.udb_path = os.path.join(os.path.dirname(project_root), f"{self.project_name}.und")  # Database file save location, needs to be in repository directory
        self.db = None

    def if_exists(self):
        return os.path.exists(self.udb_path)

    def get_db(self):
        self.db = understand.open(self.udb_path)

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

    def analyze_dependency(self):
        if self.db is None:
            self.db = understand.open(self.udb_path)
        db = self.db

        simple_dependency = []  # File dependencies
        detail_dependency = []  # Function and variable dependencies
        total_file = len(db.ents("File"))
        i = 0

        # TODO: path to be unified
        project_dir = f"../../{self.project_name}"
        os.makedirs(project_dir, exist_ok=True)
        parameter_dir = os.path.join(project_dir, "dependency")
        os.makedirs(parameter_dir, exist_ok=True)

        entity_identifier = ""
        kindname = set()
        for file in db.ents("File"):
            i += 1
            print(f"Analyzing file {i}/{total_file}")
            if file.file_type() is None:
                continue
            dep_dict = file.depends()
            file_name = file.name()
            file_dependencies = []

            for key, deps in dep_dict.items():
                dep_key = str(key)
                file_dependencies.append(dep_key)
                for dep in deps:
                    dep_str = str(dep)
                    dep_ent = dep.ent()
                    dep_ent_name = dep_ent.name()
                    dep_scope_name = dep.scope().name()
                    dep_line = dep.line()
                    dep_ent_kind_name = dep_ent.kindname()
                    dep_identifier = file_name + dep_key + dep_str + dep_ent_name + dep_scope_name
                    # Using dep_ent.contents() can get dependency content, but it takes a long time, so it's not stored for now, and will be called when actually needed
                    if dep_identifier != entity_identifier:
                        detail_dependency.append(
                            (file_name, dep_key, dep_str, dep_ent_name, dep_scope_name, dep_line, dep_ent_kind_name))
                        kindname.add(dep_ent_kind_name)
                        entity_identifier = dep_identifier
                    # for key1, value1 in dep.ent().depends().items():
                    #     for dep1 in dep.ent().depends()[key1]:
                    #         print(dep1.ent().contents(), dep1.ent().name(), dep1.scope().name())
                    #         print("------------------------------------")

            simple_dependency.append((file_name, file_dependencies))

        df1 = pd.DataFrame(simple_dependency, columns=["Source File", "Dependency File"])
        df2 = pd.DataFrame(detail_dependency,
                           columns=["Source File", "Dependency File", "Dependency Description", "Dependency Source", "Dependency Item", "Dependency Line Number", "Dependency Type"])

        # Save results to Excel files
        df1.to_excel(f"{parameter_dir}/dependency_simple.xlsx", index=False)
        df2.to_excel(f"{parameter_dir}/dependency_detail.xlsx", index=False)

        print(f"Data saved to {parameter_dir}/dependency_simple.xlsx")
        print(f"Data saved to {parameter_dir}/dependency_detail.xlsx")

    def get_dependency(self):
        simple_df = pd.read_excel(f"../{self.project_name}_simple.xlsx")

        dependency = {}
        # Iterate through each row, processing dependency files
        for index, row in simple_df.iterrows():
            file_name = row["Source File"]
            dependencies_str = row["Dependency File"]  # This is a list
            dependencies = ast.literal_eval(dependencies_str)
            dependency[file_name] = dependencies

        return dependency

    def get_directory_structure(self):

        # dir_set = set()

        def traverse_directory(dir_path):
            # Get all files and subdirectories in the current directory
            items = os.listdir(dir_path)
            folder_contents = {}

            for item in items:
                item_path = os.path.join(dir_path, item)
                # dir_set.add(item_path)
                # If it's a file, add it directly to the current directory
                if os.path.isfile(item_path):
                    folder_contents[item] = None
                # If it's a directory, recursively traverse it
                elif os.path.isdir(item_path):
                    folder_contents[item] = traverse_directory(item_path)

            return folder_contents

        # Start recursive traversal from the given directory
        dir_structure = traverse_directory(self.project_root)
        # return dir_structure, dir_set
        return dir_structure

    def get_control_flow(self, analyze_file):
        # db = understand.open(self.udb_path)
        db = self.db
        control_flow = {}
        for file in db.ents("File"):
            # if not file.longname().startswith(self.project_root):
            #     continue
            file_name = str(file.longname())
            if file_name != analyze_file:
                continue
            total_info = []
            for function in file.ents("Define", "Function"):
                cfGraph = function.control_flow_graph()  # Get the control flow graph of this function
                # cfg_structure = {}
                node_list = []
                if cfGraph is not None:
                    for node in cfGraph.nodes():  # Get nodes in the control flow graph
                        # print(node.line_begin())
                        text = ""
                        lexer = file.lexer()  # Get all content in the file
                        line_begin = node.line_begin()
                        # line_end = node.line_end()
                        column_begin = node.column_begin()
                        # column_end = node.column_end()
                        if line_begin is not None and column_begin is not None:
                            # lexeme = lexer.lexeme(node.line_begin(), node.column_begin())
                            lexeme = lexer.lexeme(line_begin, 0)  # Get the part of the file at the start position of this node
                            if lexeme is not None:
                                # while lexeme.line_end() != node.line_end() or lexeme.column_end() != node.column_end():  # Determine if this part belongs to this node
                                while lexeme.line_end() <= node.line_end():  # Determine if this part belongs to this node
                                    text += lexeme.text()
                                    lexeme = lexeme.next()  # Get the next part of the content
                                    if lexeme is None:
                                        break
                                if lexeme is not None:  # Get the last part of the content that belongs to this node
                                    text += lexeme.text()

                        kind = node.kind()
                        children = node.children()

                        if kind in {"end-if", "else"} and children and line_begin is None:
                            location_node = children[0]
                        else:
                            location_node = node
                        # location_node = node

                        # Pre-calculate file type and node position information
                        file_kind = str(file.kind())
                        line_begin = location_node.line_begin()
                        line_end = location_node.line_end()
                        column_begin = location_node.column_begin()
                        column_end = location_node.column_end()

                        node_info = {
                            'Node Name': file_name + "_" + function.name() + "_" + str(line_begin) + "_" + str(
                                column_begin) + "_" + str(kind),
                            'Belongs to File': {
                                'File Name': file_name,
                                'File Type': file_kind  # Use pre-calculated value
                            },
                            'Content': text,
                            'Type': kind,
                            'Position': {  # Use pre-calculated position information
                                'Start Line': line_begin,
                                'End Line': line_end,
                                'Start Column': column_begin,
                                'End Column': column_end,
                            },
                            'Child Nodes': {
                                str(file.longname() + "_" + function.name() + "_" + str(lb) + "_" + str(cb) + "_" + str(
                                    child_kind)): {
                                    'Type': child_kind,
                                    'Position': {
                                        'Start Line': lb,
                                        'End Line': le,
                                        'Start Column': cb,
                                        'End Column': ce,
                                    }
                                } for child in children
                                for child_kind, lb, le, cb, ce in [
                                    (child.kind(), child.line_begin(), child.line_end(),
                                     child.column_begin(), child.column_end())
                                ]
                            }
                        }

                        # print(json.dumps(node_info, indent=4, ensure_ascii=False))

                        # cfg_structure[file_name + "_" + function.name() + "_" + str(line_begin) + "_" + str(column_begin) + "_" + str(kind)] = node_info
                        node_list.append(node_info)

                # Format dictionary
                # formatted_structure = {str(key): value for key, value in cfg_structure.items()}
                total_info.append({function.name(): node_list})

                # Use json.dumps to format output
                # formatted_json = json.dumps(formatted_structure, indent=4, ensure_ascii=False)

                # Output formatted results
                # print(formatted_json)

            control_flow[file_name] = total_info
            # print(json.dumps(control_flow, indent=4, ensure_ascii=False))

        return control_flow

    def parameter_reference(self):
        project_dir = f"../../{self.project_name}"
        os.makedirs(project_dir, exist_ok=True)
        parameter_dir = os.path.join(project_dir, "parameters")
        os.makedirs(parameter_dir, exist_ok=True)

        # db = understand.open(self.udb_path)
        db = self.db
        total_file = len(db.ents("File"))
        i = 0

        for file in db.ents("File"):
            i += 1
            print(f"Analyzing file {i}/{total_file}")
            abs_path = file.longname()
            if not abs_path.startswith(self.project_root):
                continue
            _, extension = os.path.splitext(abs_path)
            if not extension:
                continue
            file_longname = abs_path.replace("\\", "_").replace("/", "_").replace(":", "_").replace(".", "")
            file_parameter_data = []
            for function in file.ents("Define", "Function"):
                for parameter in function.refs():
                    parameter_ent = parameter.ent()
                    if parameter_ent.kind().name() != "Local Object":
                        continue
                    #     # print(parameter_ent.kind().name())
                    #
                    #     parameter_info = (file, function, parameter_ent.name(), parameter, parameter.line(), parameter.kindname(), parameter_ent.kind().name())
                    #     file_parameter_data.append(parameter_info)
                    # parameter_info = (file, function, parameter_ent.name(), parameter, parameter.line(), parameter.kindname(), 1)
                    parameter_info = (file, function, parameter_ent.name(), parameter, parameter.line(),
                                      parameter.kindname(), parameter_ent.kind().name())
                    file_parameter_data.append(parameter_info)

            df = pd.DataFrame(file_parameter_data,
                              columns=["Belongs to File", "Belongs to Function", "Parameter Name", "Parameter Description", "Line Number", "Parameter Call Type",
                                       "Parameter Type"])
            file_name = f"{parameter_dir}/{file_longname}_parameter.xlsx"
            df.to_excel(file_name, index=False)

        print(f"Data saved to {parameter_dir}")

    def get_data_control_flow(self, analyze_file, target_lines):
        project_dir = f"../{self.project_name}"
        parameter_dir = os.path.join(project_dir, "parameters")

        file_dir = analyze_file.replace("\\", "_").replace("/", "_").replace(":", "_").replace(".", "")
        full_dir = f"{parameter_dir}/{file_dir}_parameter.xlsx"

        try:
            df = pd.read_excel(full_dir)
        except FileNotFoundError:
            print(f"File {full_dir} not found, please check if the path is correct")
            exit()

        result_set = set()  # Use set to store results, automatically deduplicate

        for target_line in target_lines:  # Iterate through target line number list
            parameter = df[df["Line Number"] == target_line]
            if parameter.empty:
                # print(f"No data found for line number {target_line}")
                continue  # Skip current target line number, continue to next

            parameter_name = parameter["Parameter Name"].iloc[0]
            upper_rows = df[df["Line Number"] <= target_line]
            parameters = upper_rows[upper_rows["Parameter Name"] == parameter_name]
            parameters_define = parameters[parameters["Parameter Call Type"] == "Define"]
            line_numbers = parameters_define["Line Number"].tolist()

            # Add current target line number results to set
            result_set.update(line_numbers)

        return list(result_set)

    def get_data_control_content(self, analyze_file, function_name):
        """
        TODO: prune dependency content
        """
        db = self.db
        # i = 0
        content = {}
        vis = set()
        for file in db.ents("File"):
            # i += 1
            abs_path = file.longname()
            if abs_path != analyze_file:
                continue
            file_name = os.path.basename(abs_path)

            start = math.inf
            end = -math.inf
            for ref in file.filerefs():
                ref_ent_name = ref.ent().name()
                # print(ref_ent_name, ref.kindname(), ref.line())
                if function_name != ref_ent_name:
                    continue
                # print("ref_ent_name", ref_ent_name)

                kind = ref.kindname()
                if kind == "Define":
                    start = min(start, ref.line())
                elif kind == "End":
                    end = max(end, ref.line())

            target_lines_set = set([i for i in range(start - 1, end + 1)])  # Get function scope

            for ref in file.filerefs():
                ref_ent_name = ref.ent().name()
                if ref_ent_name == file_name:
                    continue

                ref_line = ref.line()
                if ref_line not in target_lines_set or ref.scope().kindname() == "File":  # Skip if not in scope or directly referencing files
                    continue

                if ref.isforward():  # Skip if referenced
                    continue

                kind = ref.kindname()
                if kind == "Begin" or kind == "End":  # Begin and end nodes are meaningless
                    continue

                sc = ref.scope()
                # print(sc.kindname())
                # if sc.name() not in lines[ref_line-1]:
                #     # print(ref_ent_name)
                #     # print(lines[ref_line-1])
                #     # print("------------------------------------")
                #     continue

                if sc.kindname() == "Macro":
                    ct = "#define " + sc.longname() + " " + sc.value() if sc.value() else "#define " + sc.longname()
                else:
                    ct = sc.contents()

                while sc and sc.kindname() != "File":  # Dependent file name
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

    def analyze_file_dependency(self, analyze_file, epoch, lines):
        # db = understand.open(self.udb_path)
        db = self.db
        dependency = []

        initial_hashes = SimhashIndex([], k=10)  # k takes 0-64, smaller k means stricter

        for file in db.ents("File"):
            if file.longname() == analyze_file:
                check = True
                build_dependency_tree(file=file, dependency_tree=dependency, index=initial_hashes, epoch=epoch,
                                      check=check, lines=lines)

        return dependency

    def find_lca(self, file_type):
        project_dir = f"../../{self.project_name}"
        full_dir = f"{project_dir}/commit_modifications.xlsx"

        try:
            df = pd.read_excel(full_dir)
        except FileNotFoundError:
            print(f"File {full_dir} not found, please check if the path is correct")
            exit()

        commits = df[file_type].apply(ast.literal_eval)
        all_lcas = []
        all_distances = [0] * len(commits)
        for k, paths in enumerate(commits):
            if not paths:
                all_distances[k] = 0
                all_lcas.append("")
                continue

            path_num = len(paths)

            # Split all paths into hierarchical lists
            split_paths = [path.replace("\\", "/").split("/") for path in paths]

            # Find the shortest length of all paths to avoid index out of range
            min_length = 1000
            for p in split_paths:
                path_dep = len(p)
                all_distances[k] += path_dep
                min_length = min(path_dep, min_length)

            # Compare all paths by level to find the longest common prefix
            lca_parts = []
            for i in range(min_length):
                # Extract folder names at the current level of all paths
                level_components = {p[i] for p in split_paths}
                if len(level_components) == 1:
                    all_distances[k] -= path_num
                    lca_parts.append(level_components.pop())  # All paths have the same level, add to LCA
                else:
                    break  # Found mismatched parts, terminate search
            all_lcas.append(os.sep.join(lca_parts))
            all_distances[k] /= len(paths)

        df[f"{file_type} Average Distance"] = all_distances
        df[f"{file_type} lca"] = all_lcas
        df.to_excel(full_dir, index=False)

        print(f"Data saved to {full_dir}")

    def commit_dependency(self, analyze_files, epoch, lines):
        db = self.db
        dependency = []
        file_line_map = dict(zip(analyze_files, lines))

        initial_hashes = SimhashIndex([], k=10)  # k takes 0-64, smaller k means stricter

        for file in db.ents("File"):
            file_name = file.longname()
            rel_path = os.path.relpath(file_name, self.project_root)
            rel_path = os.path.normpath(rel_path).replace("\\", "/")
            if rel_path in file_line_map:
                check = True
                correspond_lines = file_line_map[rel_path]
                build_commit_dependency_tree(file=file, dependency_tree=dependency, index=initial_hashes, epoch=epoch,
                                             check=check, lines=correspond_lines)

        return dependency

    def get_function_doc(self):
        db = self.db
        for file in db.ents("File"):
            file_longname = file.longname()
            if not file_longname.startswith(self.project_root):
                continue
            try:
                # Open file and read all lines
                with open(file_longname, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                lexer = file.lexer()

            except FileNotFoundError:
                print(f"File {file_longname} not found, please check if the path is correct")
                continue
            except Exception as e:
                print(f"Error occurred while reading file: {e}")
                continue
            for function in file.filerefs("Define", "Function"):
                comment_lines = []
                line_begin = function.line()
                current_line = line_begin - 1

                function_text = lines[line_begin - 1]
                # fin = function_text[-1]
                # l = [")", ":", "{"]
                # n = len(lines)
                # i = 0
                # while fin not in l and line_begin < n and i < 2:
                #     function_text += lines[line_begin]
                #     line_begin += 1
                #     fin = function_text[-1]
                #     i += 1

                # function_lex = lexer.lexeme(line_begin, 0)
                # function_text = function_lex.text()
                #
                line_lex = lexer.lexeme(current_line, 0)
                line_text = line_lex.text().strip()
                i = 0
                while not line_text.startswith("/*") or not line_text.endswith("*/") and i < 5:
                    current_line -= 1
                    line_lex = lexer.lexeme(current_line, 0)
                    if line_lex is None:
                        line_text = ""
                        break
                    line_text = line_lex.text().strip()
                    i += 1

                # Reverse comment order (because we searched from bottom to top)
                comment_lines.append(line_text)
                comment_lines.reverse()

                # Output function name and its comments
                print(file.longname())
                print(f"Function: {function_text}")
                # print(f"Function: {lexer.lexeme(current_line+1, 0).text().strip()}")
                if len(comment_lines) > 0:
                    print("Comment:")
                    print("\n".join(comment_lines))
                else:
                    print("No comment found")
                print("-" * 40)

    def get_function(self):
        db = self.db
        data = []
        for file in tqdm(db.ents("File")):
            if not file.longname().startswith(self.project_root):
                continue

            for function in file.ents("Define", "Function"):
                file_name = file.longname()
                function_name = function.name()

                print(file_name)
                print(function_name)
                print("------------------------------------")
                data.append((file_name, function_name))

        df = pd.DataFrame(data, columns=["file_name", "function_name"])

        return df

    def get_function_content(self, files, functions):
        combine = {}
        for file, function in zip(files, functions):
            if file not in combine:
                combine[file] = {function}
            else:
                combine[file].add(function)

        db = self.db
        contents = {}
        for file in db.ents("File"):
            file_name = file.longname()
            # print(file_name)
            if file_name not in combine:
                continue
            for function in file.ents("Define", "Function"):
                if function.name() in combine[file_name]:
                    contents[function.name()] = function.contents()

        return contents

    def git_grep_with_context(self, key_word):
        repo = git.Repo(self.project_root)

        # grep_result = repo.git.grep('-n', '-C', str(2), key_word, '--', "src/include/catalog/pg_proc.dat")
        #
        # result = []
        # check = 0
        # for line in grep_result.splitlines():
        #     if f"proname => {key_word}" in line:
        #         check = 1
        #     if check == 1 and "prosrc" in line:
        #         start = line.find("prosrc => '") + len("prosrc => '")
        #         end = line.find("'", start)
        #         if start != -1 and end != -1:
        #             prosrc_value = line[start:end]
        #             result.append(prosrc_value)
        #         check = 0

        grep_result = repo.git.grep('DATA(insert', '--', "src/include/catalog/pg_proc.h")
        result = []
        for line in grep_result.splitlines():
            if "DATA(insert" in line:
                # Fields within parentheses
                left = line.find('(')
                right = line.rfind(')')
                if left == -1 or right == -1:
                    continue
                content = line[left + 1:right]
                fields = content.split()
                if len(fields) >= 28 and fields[5] == key_word:
                    prosrc = fields[-5]
                    result.append(prosrc)

        return result

    def find_func_by_re(self, key_word):
        """
        git grep "BuiltinFuncs(" -- src/
        src/alter.c:  sqlite3InsertBuiltinFuncs(aAlterTableFuncs, ArraySize(aAlterTableFuncs));
        src/callback.c:void sqlite3InsertBuiltinFuncs(
        src/date.c:  sqlite3InsertBuiltinFuncs(aDateTimeFuncs, ArraySize(aDateTimeFuncs));
        src/func.c:  sqlite3InsertBuiltinFuncs(aBuiltinFunc, ArraySize(aBuiltinFunc));
        src/json.c:  sqlite3InsertBuiltinFuncs(aJsonFunc, ArraySize(aJsonFunc));
        src/sqliteInt.h:void sqlite3InsertBuiltinFuncs(FuncDef*,int);
        src/window.c:  sqlite3InsertBuiltinFuncs(aWindowFuncs, ArraySize(aWindowFuncs));
        :param key_word:
        :return:
        """
        func_loads = [
            f"{self.project_root}/src/func.c",
            f"{self.project_root}/src/date.c",
            f"{self.project_root}/src/json.c",
            f"{self.project_root}/src/window.c",
            f"{self.project_root}/src/alter.c"
        ]

        content = str()
        for func_load in func_loads:
            with open(func_load, "r") as rf:
                text = rf.read()
            content += f"{text}\n"

        pattern = rf'\(\s*({key_word}\s*,[\s\S]*?)\s*\)\s*,'
        pattern = rf'([A-Za-z_][A-Za-z0-9_]*)\(\s*({key_word}\s*,[\s\S]*?)\s*\)\s*,'
        matches = re.findall(pattern, content, re.DOTALL)

        key_functions = list()
        for typ, match in matches:
            item = match.split(",")

            if typ == "MFUNCTION":
                if len(item) != 4:
                    print(f"{key_word} is not MFUNCTION standard")
                    continue
                key_functions.append(item[-1].strip())


            elif typ == "JFUNCTION":
                if len(item) != 8:
                    print(f"{key_word} is not JFUNCTION standard")
                    continue
                key_functions.append(item[-1].strip())

            else:
                if len(item) < 5:
                    continue

                is_numeric = True
                for i in range(1, 4):
                    if not item[i].replace("-", "").strip().isdigit():
                        is_numeric = False
                        break

                if not is_numeric:
                    continue

                for i in range(4, len(item)):
                    if item[i].strip()[0].islower():
                        key_functions.append(item[i].strip())

        return key_functions

    def get_duckdb_func_struct(self, key_word):
        key_functions = list()

        # keyword_pattern = f'Name = "{key_word}"'
        # out = subprocess.run(["grep", "-r", keyword_pattern, compiler_folder])
        # for ref in file_ent.filerefs():
        #     ent = ref.scope()
        #     if ent.kind() == "Struct" and keyword_pattern in ent.contents():
        #
        #     def_refs = list(ent.refs("Definein"))
        #     if def_refs and def_refs[0].line() == line_number:

        file_load = "/data/user/program/DBCode/data/benchmark/duckdb/res_func.json"
        with open(file_load, "r") as rf:
            data = json.load(rf)

        for file_path, file_content in data[key_word]["Code"].items():
            # if not file_path.endswith(".cpp"):
            #     continue

            file_path = file_path.split(":")[0].replace("./duckdb-1.3.0", "/data/user/code/duckdb")
            file_ents = self.db.lookup(file_path, "File")
            if not file_ents:
                continue

            file_ent = file_ents[0]
            for ref in file_ent.filerefs():
                scope = ref.scope()
                if scope.contents == file_content:
                    key_functions.append(scope.name())

        return key_functions

    # Find the file address of each function, return as a list
    def get_relate_files(self, key_functions, all_func_list):
        # base_dir = os.path.dirname(os.path.abspath(__file__))
        # excel_path = os.path.join(base_dir, all_func_load)
        # excel_path = os.path.normpath(excel_path)

        # df = pd.read_excel(excel_path)
        files = list()
        key_functions_filtered = list()
        for key_function in key_functions:
            # print(key_function)
            # print(df.loc[df['Function Name'] == key_function, 'Belongs to File'].iloc[0])
            result = all_func_list.loc[all_func_list['function_name'] == key_function, 'file_name']
            if len(result) != 0:
                result = result.iloc[0]
                files.append(result)
                key_functions_filtered.append(key_function)
            else:
                print(f"Do not find the related file of `{key_function}`.")

        return files, key_functions_filtered

    def test(self):
        print(self.project_root)

# und create -db /path/to/projects/Simple-Web-Server/Simple-Web-Server.und -languages C++
# und add -db /path/to/projects/Simple-Web-Server/Simple-Web-Server.und /path/to/projects/Simple-Web-Server analyze -all
