# -*- coding: utf-8 -*-
# @Project: index_test
# @Module: prompt_utils
# @Author: Wei Zhou
# @Time: 2025/8/16 21:13

from code_utils.constants import db_name

# Non-Agent

SYSTEM_PROMPT = """
You are an expert **{database} database engineer**.
Your task is **repository-level code completion**, specifically writing **database kernel code** that contributes directly to the official **{database} repository**.
Specifically, you should implement a **built-in function** that extends {database}, strictly following the provided function description and requirements below.

### 1. Syntax and Repository Standards

* Write code in the language and style used by {database} (e.g., C for PostgreSQL, and C++ for DuckDB).
* Follow official conventions for naming, indentation, data types, return values, and integration with the repository.

### 2. Functionality Requirements

* Implement **only** the described functionality without adding extra features, and avoid undefined behavior, memory leaks, or dangling pointers.
* Reuse existing modules (macros, namespaces, utility functions) and apply repository-approved error handling to safely process invalid inputs and edge cases.
* Respect all **explicit and implicit dependencies** (e.g., catalog definitions, and type system rules) to prevent conflicts, and maintain backward compatibility.

### 3. Test Case Coverage

* Ensure the code passes the repository’s **test suite**, and supports diverse cases such as NULL values (if supported).
* Validate input ranges to prevent overflow, underflow, or wrong type conversions.

### 4. Performance and Maintainability

* Implement with **time and space efficiency**, avoiding redundant allocations or computations.
* Write code that is **readable, modular, and consistent** with repository practices, with clear comments in {database}’s documentation style.
"""

USER_PROMPT = """
Write a built-in function named **{name}** for the **{database}** repository (the directory is: `{directory}`) using the details below:

1. **Function Declaration**
```
{declaration}
```

2. **Function Description**
{description}

3. **Usage Example**
```
{example}
```

{dependency}

### Output Format

Return your answer in **JSON** format (compatible with `json.loads()` in Python), including the following fields.
For example, `Code` field is a dictionary where each key is an absolute file path and the value is the corresponding code content for that file.
Ensure that all file paths are absolute paths relative to the repository directory (`{directory}`).
Please do not return any additional content.

```json
{{
    "Code": {{
        "the absolute file path for code1": "the corresponding content of code1",
        "the absolute file path for code2": "the corresponding content of code2"
    }},
    "Reasoning": "Step-by-step explanation of how the function was implemented and why.",
    "Confidence": "Confidence score for the implementation, ranging from 0 to 1."
}}
```
"""

prompt_template = """
你需要根据给定的已有代码，编写一个符合 PostgreSQL 扩展功能的 C++ 语言函数，请务必充分阅读并利用下方提供的“已有代码与依赖”，在其基础上最小增量地完成实现。

函数声明：{name}
功能描述：{describe}
调用示例：{example}

相关代码与依赖（请先彻底阅读理解，复用其中的类型、宏、工具函数与命名空间，如可直接调用，请调用，避免重复实现）：
{content}

要求：
1. 根据给定的功能名称，功能描述和相关代码，生成一个符合要求的代码实现，给出新增代码即可。
2. 请确保代码符合相应的编程规范，尤其是对输入输出数据类型的处理。
3. 如果涉及多个函数，请确保函数之间的逻辑关系清晰。
4. 给出代码和所在对应文件即可，文件需要给出相对项目根postgres的相对路径。
5. 输出使用json格式，即{{"file_path1": "content1", "file_path2": "content2"}}，不需要其它说明，请确保你给出的结果可以使用Python的json.loads()直接转为json格式。
"""


def generate_prompt(database, directory, name, description, example, dependency):
    system_prompt = SYSTEM_PROMPT.format(database=db_name[database]).strip()
    user_prompt = USER_PROMPT.format(database=db_name[database], directory=directory,
                                     name=name, declaration=name, description=description,
                                     example=example, dependency=dependency).strip()

    return system_prompt, user_prompt
    # return prompt_template.format(name=name, describe=describe, example=example, content=content)
