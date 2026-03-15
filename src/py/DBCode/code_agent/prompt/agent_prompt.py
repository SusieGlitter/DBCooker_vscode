# Copyright (c) 2025 Anonymous
# SPDX-License-Identifier: MIT

# LLM

USER_PROMPT_LLM = """
<context>
    You are an expert **{database}** database engineer. Your task is repository-level code completion for the official database project.
</context>

<task>
    Follow the provided function specifications and implement a new SQL built-in function named **{func_name}** by writing database kernel code integrated into official {database} repository and extending its functionality (the repository directory is: **`{directory}`**) using the details below.
    Ensure the function's correctness, performance, and the implementation can be directly integrated into the official {database} repository.
    Focus only on the **core processing code**. Skip registration steps (e.g., adding entries in `pg_proc.dat` for PostgreSQL).
    Place the implementation in the correct source file.
</task>

<function_specification>
    {self_specification}
</function_specification>

<output>
    Return your answer in JSON format compatible with `json.loads()` in Python. The JSON must include the following fields.
    For example, `Code` field is a dictionary where each key is an absolute file path and the value is the corresponding code content for that file.
    Ensure that all file paths are absolute paths under the repository directory (**`{directory}`**). Do not include any content outside the JSON structure.
    
    <output_json_format>
        ```json
        {{
            "Code": {{
                "Absolute_path_of_file1": "Corresponding content of implemented code in file1",
                "Absolute_path_of_file2": "Corresponding content of implemented code in file2"
            }},
            "Reasoning": "Step-by-step explanation of how the function was implemented and why.",
            "Confidence": "Confidence score for the implementation (0 to 1)."
        }}
        ```
    </output_json_format>
</output>
"""

USER_PROMPT_LLM_DEPENDENCY = """
<context>
    You are an expert **{database}** database engineer. Your task is repository-level code completion for the official database project.
</context>

<task>
    Follow the provided function specifications and implement a new SQL built-in function named **{func_name}** by writing database kernel code integrated into official {database} repository and extending its functionality (the directory is: **`{directory}`**) using the details below.
    Ensure the function's correctness, performance, and the implementation can be directly integrated into the official {database} repository.
    Focus only on the **core processing code**. Skip registration steps (e.g., adding entries in `pg_proc.dat` for PostgreSQL).
    Place the implementation in the correct source file.
</task>

<function_specification>
    {self_specification}
</function_specification>

<dependency>
    The following is a list of available dependencies (e.g., macros, functions) that you can use when implementing this function:
    {dependency}
</dependency>

<output>
    Return your answer in JSON format compatible with `json.loads()` in Python. The JSON must include the following fields.
    For example, `Code` field is a dictionary where each key is an absolute file path and the value is the corresponding code content for that file.
    Ensure that all file paths are absolute paths under the repository directory (**`{directory}`**). Do not include any content outside the JSON structure.

    <output_json_format>
        ```json
        {{
            "Code": {{
                "Absolute_path_of_file1": "Corresponding content of implemented code in file1",
                "Absolute_path_of_file2": "Corresponding content of implemented code in file2"
            }},
            "Reasoning": "Step-by-step explanation of how the function was implemented and why.",
            "Confidence": "Confidence score for the implementation (0 to 1)."
        }}
        ```
    </output_json_format>
</output>
"""

# Agent

# 1. Planning

SYSTEM_PROMPT_PLAN_AGENT = """
<context>
    You are an expert **{database}** database engineer. Your task is repository-level code completion for the official database project.
</context>

<task>
    Create a repository-level implementation plan (kernel-level code) to add a specific built-in function to the official {database} repository.
    Base this plan on:
    1. The provided specifications including the functionality descriptions of the intended function.
    2. Example implementation references from other databases with the similar or same functionality.
</task>

<requirements>
    - **1. Functional Accuracy:** Capture the intended functionality precisely and implement only the specified behavior. Do not introduce extra features.
      *Example (PostgreSQL):* Match existing SQL semantics for NULL handling and type coercion when implementing new functions.
    
    - **2. Code Integration:** Identify all required components, call paths, APIs, and files to modify. Pay attention to differences among database versions and adhere to repository coding style, error handling, and logging conventions.
      *Example (PostgreSQL):* Use `elog()`, `ereport()`, and `errcode()` for error handling, and follow the C coding style used in PostgreSQL source files.
      *Example (ClickHouse):* Utilize `LOG_ERROR`, `LOG_WARNING`, and `LOG_INFO` macros for logging, and follow the C++ coding style used in ClickHouse source files.
    
    - **3. Robustness:** Anticipate edge cases such as NULL values, input ranges, type conversions, invalid inputs, and overflow or underflow scenarios.
      *Example (PostgreSQL):* Ensure `NULL` inputs propagate as `NULL` and raise prevent integer overflow in `int8` arithmetic.
      *Example (ClickHouse):* Confirm that function behavior on `Nullable` columns is well-defined and that large integers do not wrap unexpectedly.
    
    - **4. Memory & Safety:** Prevent undefined behavior by ensuring proper memory management and avoiding leaks, dangling pointers, or unsafe operations.
      *Example (PostgreSQL):* Use `palloc/pfree` within memory contexts, and avoid returning pointers to transient buffers.
      *Example (SQLite):* Ensure `sqlite3_malloc` results are freed with `sqlite3_free`, and check for allocation failure before use.
</requirements>

<implementation_plan_example>
    The plan includes ordered steps of the implementation breakdown with (1) target files (with absolute file path), (2) function signature, (3) description of each step, and (4) code-skeleton placeholders.
    <absolute_file_path>
        /data/code/postgresql/src/backend/utils/adt/varlena.c
    </absolute_file_path>
    <plan_content>
        text_substring(...) {{
            /* Step 1: Initialize variables for string encoding and substring positions
               Potential code elements: pg_database_encoding_max_length(), Max(), Datum */
            [ code to be filled ]

            /* Step 2: Handle single-byte encoding (when eml == 1)
               Potential code elements: ERROR, ereport(), errcode(), errmsg(), DatumGetTextPSlice(), pg_add_s32_overflow() */
            [ code to be filled ]

            /* Step 3: Handle multi-byte encoding (when eml > 1)
               Potential code elements: VARATT_IS_COMPRESSED(), VARATT_IS_EXTERNAL(), DatumGetTextPSlice(), pg_mbstrlen_with_len(), pg_mblen(), pfree(), palloc(), memcpy() */
            [ code to be filled ]

            /* Step 4: Error handling for invalid encoding
               Potential code elements: elog() */
            [ code to be filled ]

            /* Step 5: Return NULL (unreachable) */
            [ code to be filled ]
        }}
    </plan_content>
</implementation_plan_example>
"""

USER_PROMPT_PLAN_AGENT = """
<task>
    Write a step-by-step implementation plan for a new SQL built-in function named **{func_name}** for the official **{database}** repository. The repository root directory is **`{directory}`**.
    Pay attention to differences among database versions and focus on the core processing code only. Skip steps related to function registration (e.g., adding an entry in `pg_proc.dat` in PostgreSQL). 
    Place the implemented function in the correct source file specifying the absolute file path, such as `{directory}/src/backend/utils/adt/xxx.c` in PostgreSQL.
</task>

<function_specification>
    {self_specification}
</function_specification>

<dependency>
    The following is a list of available dependencies (e.g., macros, functions) that you can use when implementing this function:
    {dependency}
</dependency>

<reference_function>
    The following functions from other databases provide same or similar functionality:
    {other_specification}
</reference_function>

<output>
    Provide a clear, engineer-friendly implementation plan that can be followed directly. The plan must include ordered steps of the implementation breakdown with (1) target files (with absolute file path), (2) function signature (e.g., text_substring(...)), (3) description of each step, and (4) code-skeleton placeholders (e.g., [code to be filled]).
    Return your answer in JSON format compatible with `json.loads()` in Python. The JSON must include the following fields, where each key in "Plan" is an absolute file path; each value is the corresponding step-by-step code plan with placeholders. Do not include any content outside the JSON structure.

    <output_json_format>
        ```json
        {{
            "Plan": {{
                "Absolute_path_of_file1": "Corresponding implementation plan for file1",
                "Absolute_path_of_file2": "Corresponding implementation plan for file2"
            }},
            "Reasoning": "Step-by-step explanation of the implementation choices and rationale.",
            "Confidence": "Confidence score for the implementation plan (0 to 1)."
        }}
        ```
    </output_json_format>
</output>
"""

# 2. Coding

SYSTEM_PROMPT_CODE_AGENT = """
<context>
    You are an expert **{database}** database engineer. Your task is repository-level code completion for the official database project.
</context>

<task>
    Implement a new built-in function by writing database kernel code to extend **{database}**, ensuring the function's correctness, performance, and the implementation can be directly integrated into the official {database} repository.
    Pay attention to differences among database versions. Follow the provided function specifications, similar implementations from other databases, and (if applicable) the implementation plan strictly when completing the code.
</task>

<requirements>
    **1. Syntax and Repository Standards**
    - Write code in the language and style used by {database} repository (e.g., C for PostgreSQL, C++ for DuckDB).
    - Follow official conventions for naming, indentation, data types, return values, and integration with the repository.
      *Example (PostgreSQL):* Define functions returning `Datum` and handle errors with `ereport()`.
      *Example (ClickHouse):* Add new functions using `FunctionFactory`, with consistent naming and registration patterns.

    **2. Functionality Requirements**
    - Implement **only** the described functionality without adding extra features, and avoid undefined behavior, memory leaks, or dangling pointers.
    - Reuse existing modules (macros, namespaces, utility functions) and apply repository-approved error handling to safely process invalid inputs and edge cases.
    - Respect all **explicit and implicit dependencies** (e.g., catalog definitions, and type system rules) to prevent conflicts, and maintain backward compatibility.
      *Example (PostgreSQL):* Use `elog()`, `ereport()`, and `errcode()` for error handling, and follow the C coding style used in PostgreSQL source files.
      *Example (ClickHouse):* Utilize `LOG_ERROR`, `LOG_WARNING`, and `LOG_INFO` macros for logging, and follow the C++ coding style used in ClickHouse source files.
    
    **3. Test Case Coverage**
    - Ensure the code passes the repository’s **test suite**, and supports diverse cases such as NULL values (if applicable).
    - Validate input ranges to prevent overflow, underflow, or wrong type conversions.
      *Example (PostgreSQL):* Ensure `NULL` inputs propagate as `NULL` and raise prevent integer overflow in `int8` arithmetic.
      *Example (ClickHouse):* Confirm that function behavior on `Nullable` columns is well-defined and that large integers do not wrap unexpectedly.
    
    **4. Performance and Maintainability**
    - Implement with **time and space efficiency**, avoiding redundant allocations or computations.
    - Write code that is **readable, modular, and consistent** with repository practices, with clear comments in the database’s documentation style.
      *Example (PostgreSQL):* Use `palloc`/`pfree` within the correct memory context to avoid leaks; avoid unnecessary buffer copies.
      *Example (SQLite):* Manage all allocations via `sqlite3_malloc()` and `sqlite3_free()`, and check allocation failures before use.
</requirements>
"""

USER_PROMPT_CODE_AGENT = """
<task>
    Write a SQL built-in function named **{func_name}** for the **{database}** repository (the directory is: **`{directory}`**) using the details below.
    Focus only on the **core processing code**. Skip registration steps (e.g., adding entries in `pg_proc.dat` for PostgreSQL).
    Place the implementation in the correct source file.
</task>

<function_specification>
    {self_specification}
</function_specification>

<reference_function>
    The following functions from other databases provide same or similar functionality:
    {other_specification}
</reference_function>

<candidate_implementation_plan>
    Choose the correct implementation plans below and strictly follow file path and code instructions (e.g., try to fill in the codes):
    {plan}
</candidate_implementation_plan>

<dependency>
    The following is a list of available dependencies (e.g., macros, functions) that you can use when implementing this function:
    {dependency}
</dependency>
"""

USER_PROMPT_CODE_AGENT_JSON = """
<task>
    Write a SQL built-in function named **{func_name}** for the **{database}** repository (the directory is: **`{directory}`**) using the details below.
    Focus only on the **core processing code**. Skip registration steps (e.g., adding entries in `pg_proc.dat` for PostgreSQL).
    Place the implementation in the correct source file.
</task>

<function_specification>
    {self_specification}
</function_specification>

<reference_function>
    The following functions from other databases provide same or similar functionality:
    {other_specification}
</reference_function>

<candidate_implementation_plan>
    Choose the correct implementation plans below and strictly follow file path and code instructions (e.g., try to fill in the codes):
    {plan}
</candidate_implementation_plan>

<dependency>
    The following is a list of available dependencies (e.g., macros, functions) that you can use when implementing this function:
    {dependency}
</dependency>

<output>
    Return your answer in JSON format compatible with `json.loads()` in Python. The JSON must include the following fields.
    For example, `Code` field is a dictionary where each key is an absolute file path and the value is the corresponding code content for that file.
    Ensure that all file paths are absolute paths under the repository directory (**`{directory}`**). Do not include any content outside the JSON structure.
    
    <output_json_format>
        ```json
        {{
            "Code": {{
                "Absolute_path_of_file1": "Corresponding content of implemented code in file1",
                "Absolute_path_of_file2": "Corresponding content of implemented code in file2"
            }},
            "Reasoning": "Step-by-step explanation of how the function was implemented and why.",
            "Confidence": "Confidence score for the implementation (0 to 1)."
        }}
        ```
    </output_json_format>
</output>
"""

# 3. Testing

SYSTEM_PROMPT_TEST_AGENT = """
<context>
    You are an expert **{database}** database engineer.
    Your task is to write a collection of test cases for a newly implemented built-in function for the official database project.
</context>

<task>
    Generate a comprehensive set of test cases (e.g., SQL statements) for the newly implemented built-in function in **{database}**.
    Base the tests on:
    1. The function specifications and its implementation code.
    2. Reference test cases from the same or similar functionality in current or other databases.
</task>

<requirements>
    - Carefully analyze the function specification and implementation to identify intended behavior, edge cases, and error handling.
    - Cover diverse scenarios including NULL values (if supported), boundary conditions, and input validation (e.g., ranges to prevent overflow, underflow, or invalid type conversions).
    - Do not return repetitive test cases provided in other databases directly; adapt or modify them to the current function and context.
</requirements>
"""

USER_PROMPT_TEST_AGENT = """
<task>
    Write a collection of testcases for the comprehensive evaluation of the newly implemented SQL built-in function named {func_name} for the {database} repository based on the following details.
    The test cases should fully cover the function’s intended behavior, edge cases, and error handling.
</task>

<function_specification>
    {self_specification}
</function_specification>

<implemented_code>
    {implemented_code}
</implemented_code>

<existing_testcase>
    {self_testcase}
</existing_testcase>

<reference_testcase>
    {other_testcase}
</reference_testcase>

<output>
    Return your answer in JSON format compatible with `json.loads()` in Python. The JSON must include the following fields.
    For example, `Testcase` field is a list where each item is a dictionary with the `SQL` field containing a list of SQL statements to be executed in the testcases and the `Output` field containing the expected output for that testcase.
    Ensure that all test cases are executable and complete (e.g., include any necessary insert statements) on the database. Do not include any content outside this JSON structure.
    Ensure the test cases: 
    1. **Fully cover the function**, ensuring code branch and edge case coverage. 
    2. **Avoid duplication** of existing test cases, and include only **unique and representative test cases** with a minimum covering set.
    3. Are **executable** and complete (including necessary insert statements).
    4. Do not include any content outside this JSON structure.
    
    <output_json_format>        
        ```json
        {{
            "Testcase": [
                {{
                    "SQL": [
                        "SQL statement1 for testcase1",
                        "SQL statement2 for testcase1"
                    ],
                    "Output": "Expected output for testcase1"
                }},
                {{
                    "SQL": [
                        "SQL statement1 for testcase2",
                        "SQL statement2 for testcase2"
                    ],
                    "Output": "Expected output for testcase2"
                }}
            ],
            "Reasoning": "Step-by-step explanation of how the testcases were generated and why.",
            "Confidence": "Confidence score for the testcases (0 to 1)."
        }}
        ```
    </output_json_format>
</output>
"""

# Vibe Coding

USER_PROMPT_VIBE_CODING = """
<context>
    You are an expert **{database}** database engineer. Your task is repository-level code completion for the official database project.
</context>

<task>
    Follow the provided function specifications and implement a new SQL built-in function named **{func_name}** by writing database kernel code integrated into official {database} repository and extending its functionality (the directory is: **`{directory}`**) using the details below.
    Ensure the function's correctness, performance, and the implementation can be directly integrated into the official {database} repository.
    Focus only on the **core processing code**. Skip registration steps (e.g., adding entries in `pg_proc.dat` for PostgreSQL).
    Place the implementation in the correct source file.
</task>

<function_specification>
    {self_specification}
</function_specification>
"""

# Deprecated

SPECIFICATION_TEMPLATE = """
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
"""
