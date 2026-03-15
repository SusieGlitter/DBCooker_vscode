import os
import json
import shutil
import time
from datetime import datetime
from json import JSONDecodeError
from typing import Any, Dict, Tuple

import pandas as pd
from pathlib import Path

from code_agent.tools import ToolCall, ToolResult
from code_agent.utils.config import ModelConfig, ModelProvider
from understand_code.model import UnderstandRepo

from code_utils.prompt_utils import generate_prompt
from code_utils.ai_api import get_deepseek_result
from code_utils.constants import database, test_suffix, data_folder, compile_folder, API_KEY, BASE_URL, MODEL_NAME

from code_utils.fileControl import replace_compile_with_backup, process_list_data, on_rm_error

from code_agent.utils.llm_clients.llm_client import LLMClient
from code_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse
from code_agent.tools.database.sqlite_compile_test import compile_sqlite, run_batch_test, run_sqlite_function_tests
from code_agent.tools.database.postgresql_compile_test import (compile_postgresql, init_postgresql,
                                                               start_postgresql, stop_postgresql,
                                                               installcheck_postgresql,
                                                               status_postgresql)
# from code_agent.tools.database.clickhouse_compile_test import (
#     compile_incremental,
#     compile_clean,
#     start_server,
#     stop_server,
#     run_full_tests,
#     run_single_function_tests,
#     run_builtin_tests,
#     write_failed_stderr_json,
#     remove_install_folder_if_exists,
#     _abs,
#     _read_file,
# )
from code_agent.tools.database.duckdb_compile_test import (
    compile_incremental,
    compile_clean,
    run_full_tests,
    run_group_tests,
    run_all_builtin_groups,
    run_single_test_file,
    run_function_tests,
    run_functions_union_tests,
    write_duckdb_results_json,
)

def pretty_print_complex(data):
    for sql_name, impl_dict in data.items():
        print(f"=== {sql_name} ===\n")
        for c_func_name, contents_list in impl_dict.items():
            print(f"Function name: {c_func_name} <---\n")
            for content_dict in contents_list:
                for file_path, content in content_dict.items():
                    print(f"--- {file_path} ---")
                    print(content)
                    print("\n")
        print("\n")


def get_functions_data_dependencies(function_names, project, all_func_list, database="postgresql"):
    functions_data_dependencies = {}
    function_contents = []
    print(len(function_names))
    for function_name in function_names:
        # key_word = "'" + function_name + "'"
        key_functions = None
        if database == "postgresql":
            key_functions = project.git_grep_with_context(function_name)  # Find all related sub-functions for this feature
        elif database == "sqlite":
            key_functions = project.find_func_by_re(function_name)
        else:
            # TODO: other databases
            raise NotImplementedError
        # print(f"key_functions: {key_functions}")
        # print(function_name, key_functions)

        # Understand processing: files <-> key_functions
        files, key_functions = project.get_relate_files(key_functions, all_func_list)  # Find file addresses of all sub-functions, list()
        contents = project.get_function_content(files, key_functions)  # Find source code of all sub-functions, dict()
        # print(json.dumps(contents, indent=4))

        if len(files) != 0:
            data_dependencies = {}
            function_content = {}
            for i in range(len(key_functions)):
                data_dependencies[key_functions[i]] = [project.get_data_control_content(files[i], key_functions[i]),
                                                       {files[i]: contents[key_functions[i]]}]  # Find dependency code
                if files[i] in function_content:
                    function_content[files[i]].append(contents[key_functions[i]])
                else:
                    function_content[files[i]] = [contents[key_functions[i]]]
            functions_data_dependencies[function_name] = data_dependencies
            # print(json.dumps(function_content, indent=4))
            function_contents.append(function_content)
        else:
            print("files=0", function_name)

    return functions_data_dependencies, function_contents


# pretty_print_complex(functions_data_dependencies)

# Example of a single dictionary item
# "ceil": {
#         "dceil": [
#             {
#                 "/path/to/PostgreSQL\\source\\src\\include\\fmgr.h": "#define PG_FUNCTION_ARGS FunctionCallInfo fcinfo\n#define PG_GETARG_DATUM (fcinfo->arg[n])\n#define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))\n#define PG_RETURN_FLOAT8 return Float8GetDatum(x)",
#                 "/path/to/PostgreSQL\\source\\src\\include\\postgres.h": "#define DatumGetFloat8 (* ((float8 *) DatumGetPointer(X)))\n#define DatumGetPointer ((Pointer) (X))",
#                 "/path/to/PostgreSQL\\source\\src\\backend\\utils\\fmgr\\fmgr.c": "Datum\nFloat8GetDatum(float8 X)\n{\n#ifdef USE_FLOAT8_BYVAL\n\tunion\n\t{\n\t\tfloat8\t\tvalue;\n\t\tint64\t\tretval;\n\t}\t\t\tmyunion;\n\n\tmyunion.value = X;\n\treturn SET_8_BYTES(myunion.retval);\n#else\n\tfloat8\t   *retval = (float8 *) palloc(sizeof(float8));\n\n\t*retval = X;\n\treturn PointerGetDatum(retval);\n#endif\n}"
#             },
#             {
#                 "/path/to/PostgreSQL\\source\\src\\backend\\utils\\adt\\float.c": "Datum\ndceil(PG_FUNCTION_ARGS)\n{\n\tfloat8\t\targ1 = PG_GETARG_FLOAT8(0);\n\n\tPG_RETURN_FLOAT8(ceil(arg1));\n}"
#             }
#         ],
#         "numeric_ceil": [
#             {
#                 "/path/to/PostgreSQL\\source\\src\\include\\c.h": "struct varlena\n{\n\tchar\t\tvl_len_[4];\t\t/* Do not touch this field directly! */\n\tchar\t\tvl_dat[FLEXIBLE_ARRAY_MEMBER];\t/* Data content is here */\n};",
#                 "/path/to/PostgreSQL\\source\\src\\include\\fmgr.h": "#define PG_DETOAST_DATUM pg_detoast_datum((struct varlena *) DatumGetPointer(datum))\n#define PG_FUNCTION_ARGS FunctionCallInfo fcinfo\n#define PG_GETARG_DATUM (fcinfo->arg[n])",
#                 "/path/to/PostgreSQL\\source\\src\\backend\\utils\\fmgr\\fmgr.c": "struct varlena *\npg_detoast_datum(struct varlena * datum)\n{\n\tif (VARATT_IS_EXTENDED(datum))\n\t\treturn heap_tuple_untoast_attr(datum);\n\telse\n\t\treturn datum;\n}",
#                 "/path/to/PostgreSQL\\source\\src\\include\\postgres.h": "#define DatumGetPointer ((Pointer) (X))\n#define PointerGetDatum ((Datum) (X))",
#                 "/path/to/PostgreSQL\\source\\src\\include\\utils\\numeric.h": "#define DatumGetNumeric ((Numeric) PG_DETOAST_DATUM(X))\n#define NumericGetDatum PointerGetDatum(X)\n#define PG_GETARG_NUMERIC DatumGetNumeric(PG_GETARG_DATUM(n))\n#define PG_RETURN_NUMERIC return NumericGetDatum(x)",
#                 "/path/to/PostgreSQL\\source\\src\\backend\\utils\\adt\\numeric.c": "#define NUMERIC_FLAGBITS ((n)->choice.n_header & NUMERIC_SIGN_MASK)\n#define NUMERIC_IS_NAN (NUMERIC_FLAGBITS(n) == NUMERIC_NAN)\n#define NUMERIC_SIGN_MASK 0xC000\nstatic void\nceil_var(NumericVar *var, NumericVar *result)\n{\n\tNumericVar\ttmp;\n\n\tinit_var(&tmp);\n\tset_var_from_var(var, &tmp);\n\n\ttrunc_var(&tmp, 0);\n\n\tif (var->sign == NUMERIC_POS && cmp_var(var, &tmp) != 0)\n\t\tadd_var(&tmp, &const_one, &tmp);\n\n\tset_var_from_var(&tmp, result);\n\tfree_var(&tmp);\n}\nstatic void\nfree_var(NumericVar *var)\n{\n\tdigitbuf_free(var->buf);\n\tvar->buf = NULL;\n\tvar->digits = NULL;\n\tvar->sign = NUMERIC_NAN;\n}\nstatic void\ninit_var_from_num(Numeric num, NumericVar *dest)\n{\n\tdest->ndigits = NUMERIC_NDIGITS(num);\n\tdest->weight = NUMERIC_WEIGHT(num);\n\tdest->sign = NUMERIC_SIGN(num);\n\tdest->dscale = NUMERIC_DSCALE(num);\n\tdest->digits = NUMERIC_DIGITS(num);\n\tdest->buf = NULL;\t\t\t/* digits array is not palloc'd */\n}\nstatic Numeric\nmake_result(NumericVar *var)\n{\n\tNumeric\t\tresult;\n\tNumericDigit *digits = var->digits;\n\tint\t\t\tweight = var->weight;\n\tint\t\t\tsign = var->sign;\n\tint\t\t\tn;\n\tSize\t\tlen;\n\n\tif (sign == NUMERIC_NAN)\n\t{\n\t\tresult = (Numeric) palloc(NUMERIC_HDRSZ_SHORT);\n\n\t\tSET_VARSIZE(result, NUMERIC_HDRSZ_SHORT);\n\t\tresult->choice.n_header = NUMERIC_NAN;\n\t\t/* the header word is all we need */\n\n\t\tdump_numeric(\"make_result()\", result);\n\t\treturn result;\n\t}\n\n\tn = var->ndigits;\n\n\t/* truncate leading zeroes */\n\twhile (n > 0 && *digits == 0)\n\t{\n\t\tdigits++;\n\t\tweight--;\n\t\tn--;\n\t}\n\t/* truncate trailing zeroes */\n\twhile (n > 0 && digits[n - 1] == 0)\n\t\tn--;\n\n\t/* If zero result, force to weight=0 and positive sign */\n\tif (n == 0)\n\t{\n\t\tweight = 0;\n\t\tsign = NUMERIC_POS;\n\t}\n\n\t/* Build the result */\n\tif (NUMERIC_CAN_BE_SHORT(var->dscale, weight))\n\t{\n\t\tlen = NUMERIC_HDRSZ_SHORT + n * sizeof(NumericDigit);\n\t\tresult = (Numeric) palloc(len);\n\t\tSET_VARSIZE(result, len);\n\t\tresult->choice.n_short.n_header =\n\t\t\t(sign == NUMERIC_NEG ? (NUMERIC_SHORT | NUMERIC_SHORT_SIGN_MASK)\n\t\t\t : NUMERIC_SHORT)\n\t\t\t| (var->dscale << NUMERIC_SHORT_DSCALE_SHIFT)\n\t\t\t| (weight < 0 ? NUMERIC_SHORT_WEIGHT_SIGN_MASK : 0)\n\t\t\t| (weight & NUMERIC_SHORT_WEIGHT_MASK);\n\t}\n\telse\n\t{\n\t\tlen = NUMERIC_HDRSZ + n * sizeof(NumericDigit);\n\t\tresult = (Numeric) palloc(len);\n\t\tSET_VARSIZE(result, len);\n\t\tresult->choice.n_long.n_sign_dscale =\n\t\t\tsign | (var->dscale & NUMERIC_DSCALE_MASK);\n\t\tresult->choice.n_long.n_weight = weight;\n\t}\n\n\tAssert(NUMERIC_NDIGITS(result) == n);\n\tif (n > 0)\n\t\tmemcpy(NUMERIC_DIGITS(result), digits, n * sizeof(NumericDigit));\n\n\t/* Check for overflow of int16 fields */\n\tif (NUMERIC_WEIGHT(result) != weight ||\n\t\tNUMERIC_DSCALE(result) != var->dscale)\n\t\tereport(ERROR,\n\t\t\t\t(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),\n\t\t\t\t errmsg(\"value overflows numeric format\")));\n\n\tdump_numeric(\"make_result()\", result);\n\treturn result;\n}",
#                 "/path/to/PostgreSQL\\source\\src\\interfaces\\ecpg\\test\\expected\\sql-sqlda.c": "#define NUMERIC_NAN 0xC000"
#             },
#             {
#                 "/path/to/PostgreSQL\\source\\src\\backend\\utils\\adt\\numeric.c": "Datum\nnumeric_ceil(PG_FUNCTION_ARGS)\n{\n\tNumeric\t\tnum = PG_GETARG_NUMERIC(0);\n\tNumeric\t\tres;\n\tNumericVar\tresult;\n\n\tif (NUMERIC_IS_NAN(num))\n\t\tPG_RETURN_NUMERIC(make_result(&const_nan));\n\n\tinit_var_from_num(num, &result);\n\tceil_var(&result, &result);\n\n\tres = make_result(&result);\n\tfree_var(&result);\n\n\tPG_RETURN_NUMERIC(res);\n}"
#             }
#         ]
#     }


def clean_json_string(text: str):
    """

    :rtype: str | Any
    """
    # Find from the first { to the last }
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1 or end == -1:
        raise ValueError("No valid JSON block found")
    json_str = text[start:end]
    # Replace illegal characters: escape backslashes, quotes, and line breaks
    # json_str = json_str.encode('unicode_escape').decode('utf-8')  # Convert line breaks, \0, etc. to \\n, \\0
    # json_str = json_str.replace("'", '"')  # Unify quotes
    # print(json_str)
    try:
        json_str = json.loads(json_str)
    except JSONDecodeError:
        return ""
    return json_str


def get_gen_code_dependency(func_name_list, project_dir, lang, all_func_list, database="postgresql"):
    """

    :param func_name_list: TODO BE REPLACED!!!
    :param project_dir:
    :param lang:
    :param database:
    :return:
    """

    # with open(json_file, 'r', encoding='utf-8') as f:   # Extract original model-generated code and function source code
    #     try:
    #         ori_gen_code = json.load(f)
    #     except JSONDecodeError:
    #         ori_gen_code = []

    project = UnderstandRepo(lang, project_dir)
    if not project.if_exists():
        project.create_udb()
    project.get_db()

    # fdp is function dependency content, fcs is function content itself
    fdp, fcs = get_functions_data_dependencies(func_name_list,
                                               project, all_func_list, database)

    return fdp, fcs


def get_gen_code_context(descriptions, examples, details, if_dep):
    dependency = {}
    code_names = ", ".join([f"`{func_name}`" for func_name in details.keys()])
    code_dependency = "The following repository code dependency may be relevant when implementing this function:\n"
    for code_name, codes in details.items():  # code_name is the name of a small function in this feature, codes is its corresponding code
        code_dependency += f"`{code_name}` function dependency:\n"
        for no, (file, content) in enumerate(codes[0].items()):  # Only take dependency code
            # TODO: to be removed.
            file = file.replace("\\", "/").replace("/path/to/PostgreSQL/source", compile_folder)
            code_dependency += f"{no + 1}.`{file}`\n```\n{content}\n```\n"
            if file not in dependency:
                dependency[file] = [content]
            else:
                dependency[file].append(content)
        code_dependency += "\n"
    code_dependency = code_dependency.strip()

    if not if_dep:
        code_dependency = ""

    code_context = generate_prompt(database, compile_folder,
                                   code_names, descriptions, examples, code_dependency)
    # print(code_context)
    # print("-------------------------------------------")

    return code_context, dependency


def serialize_tool_call(tool_call: ToolCall) -> dict[str, Any]:
    """Serialize a tool call to a dictionary."""
    return {
        "call_id": tool_call.call_id,
        "name": tool_call.name,
        "arguments": tool_call.arguments,
        "id": getattr(tool_call, "id", None),
    }


def serialize_message(message: LLMMessage) -> dict[str, Any]:
    """Serialize an LLM message to a dictionary."""
    data: dict[str, Any] = {"role": message.role, "content": message.content}

    if message.tool_call:
        data["tool_call"] = serialize_tool_call(message.tool_call)

    if message.tool_result:
        data["tool_result"] = serialize_tool_result(message.tool_result)

    return data


def serialize_tool_result(tool_result: ToolResult) -> dict[str, Any]:
    """Serialize a tool result to a dictionary."""
    return {
        "call_id": tool_result.call_id,
        "success": tool_result.success,
        "result": tool_result.result,
        "error": tool_result.error,
        "id": getattr(tool_result, "id", None),
    }


def serialize_llm_response(messages, response, model_config):
    interaction = {
        "timestamp": datetime.now().isoformat(),
        "provider": model_config.model_provider.provider,
        "model": model_config.model,
        "input_messages": [serialize_message(msg) for msg in messages],
        "response": {
            "content": response.content,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
                "cache_creation_input_tokens": getattr(
                    response.usage, "cache_creation_input_tokens", None
                )
                if response.usage
                else None,
                "cache_read_input_tokens": getattr(
                    response.usage, "cache_read_input_tokens", None
                )
                if response.usage
                else None,
                "reasoning_tokens": getattr(response.usage, "reasoning_tokens", None)
                if response.usage
                else None,
            },
            "tool_calls": [serialize_tool_call(tc) for tc in response.tool_calls]
            if response.tool_calls
            else None,
        },
    }

    return interaction


def get_llm_gen_code(code_context, project_dir):
    """
    # Below is the format of result_clean items, the first item is model-generated code, the second item is source code
    # [
    #     {
    #         "file_path1": "content1",
    #         "file_path2": "content2"
    #     },
    #     {
    #         "file_path1": "content1",
    #         "file_path2": "content2"
    #     }
    # ]
    """
    messages = [
        LLMMessage(role="system", content=code_context[0]),
        LLMMessage(role="user", content=code_context[1])
    ]

    provider = "doubao"  # doubao, google

    model_provider = ModelProvider(api_key=API_KEY, provider=provider, base_url=BASE_URL)
    model_config = ModelConfig(model=MODEL_NAME, model_provider=model_provider,
                               max_tokens=8192, temperature=0.0, max_retries=5,
                               top_p=1, top_k=0, parallel_tool_calls=True)

    llm_client = LLMClient(model_config)
    response = llm_client.chat(messages=messages, model_config=model_config)

    # response = ""
    # while len(response) == 0:
    #     response = get_deepseek_result(code_context)
    #     print(result)
    # response_json = clean_json_string(response)  # Parse JSON format

    # code_clean = {}
    # for key, value in response_json.items():
    #     # TODO: to be removed.
    #     path = os.path.join(project_dir, key)
    #     if os.path.exists(path):
    #         code_clean[path] = value
    #
    # return response, response_json, code_clean

    response_json = serialize_llm_response(messages, response, model_config)
    return response, response_json, ""


def eval_sqlite_code(func_name, method_id, compile_folder, install_folder):
    """

    :param method_id:
    :param func_name:
    :param compile_folder:
    :param install_folder:
    :return:
    """
    time_total = dict()
    if os.path.exists(install_folder):
        shutil.rmtree(install_folder, onerror=on_rm_error)

    print("==1.Starting database compilation==")
    time_start = time.time()
    is_success, result = compile_sqlite(compile_folder)
    time_total["db_compile"] = time.time() - time_start
    if not is_success:
        return is_success, f"[COMPILE DATABASE ERROR]\n{result}", time_total

    print("==2.Starting database testing==")
    time_start = time.time()
    # is_success, result = run_batch_test(compile_folder, test_type="test")  # test, quicktest
    is_success, result = run_sqlite_function_tests(compile_folder)
    time_total["db_installcheck"] = time.time() - time_start
    if is_success:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        src = f"{compile_folder}/build/test-out.txt"
        if os.path.exists(src):
            if is_success:
                is_success = False
                result = f"[TEST DATABASE ERROR]\n{result}"

            dst = os.path.abspath(f"results/{database}/{method_id}/{func_name}_{method_id}_{timestamp}.log")
            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))

            # if os.path.exists(dst):
            #     os.remove(dst)

            shutil.copyfile(src, dst)
            print(f"{src} copied as {dst}")

        return is_success, result, time_total

    return is_success, f"[TEST DATABASE ERROR]\n{result}", time_total


def eval_postgresql_code(func_name, method_id, compile_folder, install_folder):
    """

    :param method_id:
    :param func_name:
    :param compile_folder:
    :param install_folder:
    :return:
    """
    time_total = dict()
    if os.path.exists(install_folder):
        is_success, result = status_postgresql(install_folder, data_folder)
        if is_success:
            print("==0.Starting to stop database==")
            time_start = time.time()
            is_success, result = stop_postgresql(install_folder, data_folder)
            time_total["db_stop"] = time.time() - time_start
            if not is_success:
                return is_success, f"[STOP DATABASE ERROR]\n{result}", time_total
        shutil.rmtree(install_folder, onerror=on_rm_error)

    print("==1.Starting database compilation==")
    time_start = time.time()
    is_success, result = compile_postgresql(compile_folder, install_folder)
    time_total["db_compile"] = time.time() - time_start
    if not is_success:
        return is_success, f"[COMPILE DATABASE ERROR]\n{result}", time_total
    os.makedirs(data_folder)

    print("==2.Starting database initialization==")
    time_start = time.time()
    is_success, result = init_postgresql(install_folder, data_folder)
    time_total["db_init"] = time.time() - time_start
    if not is_success:
        return is_success, f"[INIT DATABASE ERROR]\n{result}", time_total

    print("==3.Starting database startup==")
    time_start = time.time()
    is_success, result = start_postgresql(install_folder, data_folder)
    time_total["db_start"] = time.time() - time_start
    if not is_success:
        return is_success, f"[START DATABASE ERROR]\n{result}", time_total

    print("==4.Starting database testing==")
    time_start = time.time()
    is_success, result = installcheck_postgresql(compile_folder)
    time_total["db_installcheck"] = time.time() - time_start
    if is_success:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # r'/path/to/PostgreSQL/build/REL9_5_0/'
        for suffix in test_suffix[database]:
            src = f"{compile_folder}/src/test/regress/regression.{suffix}"
            if os.path.exists(src):
                if is_success:
                    is_success = False
                    result = f"[TEST DATABASE ERROR]\n{result}"

                dst = os.path.abspath(f"results/{database}/{method_id}/{func_name}_{method_id}_{timestamp}.{suffix}")
                if not os.path.exists(os.path.dirname(dst)):
                    os.makedirs(os.path.dirname(dst))

                # if os.path.exists(dst):
                #     os.remove(dst)

                shutil.copyfile(src, dst)
                print(f"{src} copied as {dst}")
        return is_success, result, time_total

    return is_success, f"[TEST DATABASE ERROR]\n{result}", time_total


def eval_duckdb_code(
    func_name: str,            # Can be left empty here (not needed for full testing); if running single file/function name can be used as tag
    method_id: str,
    compile_folder: str,       # Convention is duckdb root directory
    install_folder: str,       # DuckDB has no installation directory requirement, only for interface consistency
) -> Tuple[bool, str, Dict[str, float]]:
    """
    DuckDB evaluation process (according to your specification):
    1) Compile (default incremental make release; if starting from scratch, use compile_clean)
    2) Test (default full: ./build/release/test/unittest)
       - Run single test: run_single_test_file("test/xxx/test_foo.test", compile_folder)
       - Run all tests for a single function: run_function_tests(func_name, compile_folder)
       - Run union of all function tests: run_functions_union_tests(compile_folder)
       - Run all function-related groups (BUILTIN_GROUPS once): run_all_builtin_groups(compile_folder)
       - Run full test (default): run_full_tests(compile_folder)
    3) Write JSON: Record "test file path + terminal output content (stdout/stderr)", and summary/failure list
       Path: results/duckdb/{method_id}/{tag}_{method_id}_{timestamp}.json
    """
    time_total: Dict[str, float] = {}

    # 1) Compile (default incremental)
    print("==1.Starting DuckDB compilation (incremental)==")
    t0 = time.time()
    ok, msg = compile_incremental(compile_folder)
    # If compiling from scratch:
    # print("==1.Starting DuckDB compilation (from scratch)==")
    # ok, msg = compile_clean(compile_folder)
    time_total["db_compile"] = time.time() - t0
    if not ok:
        return False, f"[COMPILE DATABASE ERROR]\n{msg}", time_total

    # 2) Test (default full)
    print("==2.Starting DuckDB testing (full)==")
    t0 = time.time()

    # ---- Default: Full test ----
    # ok, info = run_full_tests(compile_folder, timeout=None)
    # tag = "full"

    # ---- Other modes (use as needed, keep commented interface) ----
    # 1) Run single test file
    # ok, info = run_single_test_file("test/sql/projection/test_simple_projection.test", compile_folder)
    # tag = "single"

    # 2) Run all tests for a single function (from mapping JSON)
    ok, info = run_function_tests(func_name, compile_folder)
    tag = f"function:{func_name}"

    # 3) Run union of all function tests (union of test_files from mapping JSON)
    # ok, info = run_functions_union_tests(compile_folder)
    # tag = "union:functions"
    #
    # 4) Run all function-related groups (run all BUILTIN_GROUPS once)
    # ok, info = run_all_builtin_groups(compile_folder)
    # tag = "builtin-groups"

    time_total["db_test"] = time.time() - t0

    # 3) Write JSON (test files + terminal output)
    out_json = write_duckdb_results_json(
        method_id=method_id,
        tag=tag if not func_name else func_name,  # If you use func_name as custom tag, override here
        stdout_text=info.get("stdout", "") or "",
        stderr_text=info.get("stderr", "") or "",
        failed_tests=info.get("failed_tests", []) or [],
        extra_summary=info.get("summary", {}) or {},
        results=info.get("results"),     # Exists when running file by file
        groups=info.get("groups"),       # Exists when running batch groups
    )

    if ok:
        return True, f"DuckDB testing completed ({tag}), result: {out_json}", time_total
    else:
        return False, f"[TEST DATABASE ERROR]\nSee details: {out_json}", time_total


def eval_clickhouse_code(
    func_name: str,
    method_id: str,
    compile_folder: str,   # Convention is ClickHouse root directory
    install_folder: str,   # Reserved for interface alignment; CH doesn't strongly depend on it
) -> Tuple[bool, str, Dict[str, float]]:
    """
    Evaluation process (aligned with PostgreSQL style & your ClickHouse specification):
    1) Compile (default incremental; if compiling from scratch, replace with compile_clean)
    2) Start server (modify config.xml port + path in place to independent runtime directory)
    3) Test (default full: ./tests/clickhouse-test, no terminal log recording)
       - Failed items are summarized by scanning generated *.stderr files
       - Other test modes keep interface (commented)
    4) Stop server (restore config.xml), clean runtime directory
    5) Write failed stderr merged JSON: results/clickhouse/{method_id}/{func_or_mode}_{method_id}_{timestamp}.json
    """
    time_total: Dict[str, float] = {}
    proc = None
    config_xml = None
    backup_path = None
    runtime_dir = None

    # 1) Compile (default: incremental)
    print("==1.Starting database compilation (incremental)==")
    t0 = time.time()
    ok, msg = compile_incremental(compile_folder)
    # If compiling from scratch, change to:
    # print("==1.Starting database compilation (from scratch)==")
    # ok, msg = compile_clean(compile_folder)
    time_total["db_compile"] = time.time() - t0
    if not ok:
        return False, f"[COMPILE DATABASE ERROR]\n{msg}", time_total

    # 2) Start
    print("==2.Starting database startup==")
    t0 = time.time()
    ok, data = start_server(compile_folder)
    time_total["db_start"] = time.time() - t0
    if not ok:
        return False, f"[START DATABASE ERROR]\n{data.get('error','unknown error')}", time_total
    proc = data.get("proc")
    config_xml = data.get("config_xml")
    backup_path = data.get("backup")
    runtime_dir = data.get("runtime_dir")

    # 3) Test (default full)
    print("==3.Starting database testing (full)==")
    t0 = time.time()

    # ---- Default FULL ----
    ok, info = run_full_tests(compile_folder, timeout=None)

    # ---- Other mode interfaces (switch as needed) ----
    # ok, info = run_single_function_tests(func_name, compile_folder)   # Single function all test cases
    # ok, info = run_builtin_tests(compile_folder)                      # Union of all function test cases

    time_total["db_test"] = time.time() - t0

    # Failed items summary (scan *.stderr under tests, filter those generated after this run)
    failed_items: List[Dict] = []
    if not ok:
        tests_root = _abs(compile_folder, "tests")
        start_ts = float(info.get("start_ts", time.time() - 1))
        for dirpath, _, filenames in os.walk(tests_root):
            for fn in filenames:
                if not fn.endswith(".stderr"):
                    continue
                fullp = os.path.join(dirpath, fn)
                try:
                    if os.path.getmtime(fullp) + 1e-6 >= start_ts:
                        base = fn[:-7]  # Remove .stderr
                        rel_dir_from_tests_parent = os.path.relpath(dirpath, os.path.join(tests_root, ".."))
                        rel_sql = os.path.join(rel_dir_from_tests_parent, base + ".sql").replace("\\", "/")
                        failed_items.append({
                            "test_file": rel_sql,
                            "stderr_path": fullp,
                            "stderr": _read_file(fullp),
                        })
                except Exception:
                    continue

    # 4) Stop
    print("==4.Starting to stop database==")
    t0 = time.time()
    if proc:
        stop_server(proc, config_xml=config_xml, backup_path=backup_path, runtime_dir=runtime_dir)
    time_total["db_stop"] = time.time() - t0

    # 5) Write JSON (only failed stderr merged; no terminal logs)
    mode_tag = "full" if not func_name else func_name
    out_json = write_failed_stderr_json(
        database="clickhouse",
        method_id=method_id,
        func_or_mode=mode_tag,
        failed_items=failed_items
    )

    if ok:
        return True, f"Testing completed (full), 0 failures. Result file: {out_json}", time_total
    else:
        return False, f"[TEST DATABASE ERROR]\nSee details: {out_json}", time_total


def eval_llm_gen_code(database, func_name, method_id, compile_folder, install_folder):
    if database == "postgresql":
        is_success, result, time_total = eval_postgresql_code(func_name, method_id,
                                                              compile_folder, install_folder)
    elif database == "sqlite":
        is_success, result, time_total = eval_sqlite_code(func_name, method_id,
                                                          compile_folder, install_folder)
    # TODO:
    elif database == "duckdb":
        is_success, result, time_total = eval_duckdb_code(func_name, method_id,
                                                          compile_folder, install_folder)
    elif database == "clickhouse":
        is_success, result, time_total = eval_clickhouse_code(func_name, method_id,
                                                              compile_folder, install_folder)
    else:
        raise NotImplementedError

    return is_success, result, time_total
