import json

from utils import get_control_and_data_dependency
from understand_code.model import UnderstandRepo


# Repository language
lang = "C++"
# project_dir = "/path/to/pythonProjects\\book-management-system"
# project_dir = "/path/to/pythonProjects\\postgres"
project_dir = "/path/to/PostgreSQL\\source"
# project_dir = "/path/to/pythonProjects\\test"

project = UnderstandRepo(lang, project_dir)
if not project.if_exists():
    project.create_udb()
project.get_db()

# 1: Analyze repository
# 2: Analyze repository dependencies
# 3: Get dependency relationships between files
# 4: Analyze repository file path structure
# 5: Get parameter definition and usage relationships
# 6: Get control flow context for specified statements
# 7: Get data and cross-file dependencies for specified statements
# 8: Get all function names and locations in repository
# 9. Get related code for specified functions in documentation
operation_type = 8
if operation_type == 2:
    project.analyze_dependency()
elif operation_type == 3:
    dependency = project.get_dependency()
    print(json.dumps(dependency, indent=4, ensure_ascii=False))
elif operation_type == 4:
    structure = project.get_directory_structure()
    print(json.dumps(structure, indent=4, ensure_ascii=False))
elif operation_type == 5:
    project.parameter_reference()
elif operation_type == 6:
    # analyze_file = "/path/to/pythonProjects\\book-management-system\\main.cpp"
    analyze_file = "/path/to/pythonProjects\\postgres\\contrib\\btree_gist\\btree_bit.c"
    target_lines = [97, 110, 132, 156, 158]
    parent_count = 4
    lines, text = get_control_and_data_dependency(project, analyze_file, target_lines, parent_count)
    print(text)
elif operation_type == 7:
    analyze_file = "/path/to/pythonProjects\\postgres\\src\\backend\\utils\\adt\\numeric.c"
    function_name = "numeric_abs"
    data_dependency = project.get_data_control_content(analyze_file, function_name)
    # print(data_dependency)
    # print("-------------------------------------------")
    # epoch = 3
    # file_dependency = project.analyze_file_dependency(analyze_file, epoch, lines)
    for item in data_dependency:
        print(f"File: {item[0]}\n")
        print(item[1])
        print("-------------------------------------------")
elif operation_type == 8:
    project.get_function()
elif operation_type == 9:
    key_word = "abs"
    key_functions = project.git_grep_with_context(key_word)
    files = project.get_relate_files(key_functions)
    data_dependencies = {}
    for i in range(len(key_functions)):
        data_dependencies[key_functions[i]] = project.get_data_control_content(files[i], key_functions[i])

    print(json.dumps(data_dependencies, indent=4, ensure_ascii=False))















