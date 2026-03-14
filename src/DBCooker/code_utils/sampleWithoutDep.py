import pandas as pd

from understand_code.model import UnderstandRepo
from ai_api import get_deepseek_result

lang = "C++"
project_dir = "/path/to/pythonProjects\\postgres"

project = UnderstandRepo(lang, project_dir)
if not project.if_exists():
    project.create_udb()
project.get_db()

df = pd.read_csv('functions.csv')
function_names = df["function"].to_list()
descriptions = df.set_index('function')['describe'].to_dict()

prompt_template = """
You need to write a C++ language function that conforms to PostgreSQL extension functionality based on the given code content.

Function name: {name}
Function description: {describe}

Requirements:
1. Based on the given function name, function description and related code, generate a code implementation that meets the requirements, just provide the new code.
2. Please ensure the code conforms to the corresponding programming standards, especially for input and output data type handling.
3. If multiple functions are involved, please ensure the logical relationships between functions are clear.
4. Just provide the code and corresponding file, the file needs to give the relative path relative to the project root postgres.
5. Output using JSON format, i.e. {{"file_path1": "content1", "file_path2": "content2"}}, no other explanation needed, please ensure your result can be directly converted to JSON format using Python's json.loads().
"""


def generate_prompt(name, describe):
    return prompt_template.format(name=name, describe=describe)


for function_name in function_names:
    prompt = generate_prompt(function_name, descriptions[function_name])

    result = get_deepseek_result(prompt)
    print(result["choices"][0]["message"]["content"])
    print("-------------------------------------------")

    # print(code_prompt)
