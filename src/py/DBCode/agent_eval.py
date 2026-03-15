# -*- coding: utf-8 -*-
# @Project: DBCode
# @Module: agent_eval
# @Author: Anonymous
# @Time: 2025/9/26 14:42

import os
import json
import re
import shutil
import subprocess
import time
import traceback

from tqdm import tqdm

from code_utils.sample import eval_llm_gen_code
from code_utils.fileControl import replace_compile_with_backup, process_list_data
from code_utils.constants import agent_type, compile_folder, install_folder, backup_folder, database, MODEL_NAME, dbcode_root


def prepare_directory(origin_code, file_changes, result_folder):
    # TODO: to be modified with declaration.
    origin_gen_code = [origin_code, []]
    replace_compile_with_backup(compile_folder, backup_folder, database)
    # processed_files = set()
    processed_files = process_list_data(origin_gen_code, database)

    for file in file_changes:
        if "logs/" in file:
            continue

        src = os.path.join(result_folder, file)
        dst = os.path.join(compile_folder, file)

        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))

        shutil.copyfile(src, dst)
        print(f"Copy file from {src} to {dst}")
        processed_files.add(dst)

    print("==File modification completed==")

    return processed_files


def prepare_directory_json(origin_gen_code):
    # TODO: to be modified with declaration.
    replace_compile_with_backup(compile_folder, backup_folder, database)
    processed_files = process_list_data(origin_gen_code, database)
    print("==File modification completed==")

    return processed_files


def parse_code_output(llm_output) -> (bool, str):
    try:
        if "```json" in llm_output:
            pattern = r"```json\s*([\s\S]*?)\s*```"
        else:
            pattern = r"```\s*([\s\S]*?)\s*```"

        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = json.loads(match.group(1).strip())["Code"]
        else:
            code = json.loads(llm_output.replace("```json", "")
                              .replace("```", "").strip())["Code"]

        return True, code
    except Exception as e:
        print(f"Invalid JSON format: {e}")
        return False, {"Error": str(e)}


def eval_single_func(agent_type, func_name, origin_code, file_changes, result_folder):
    result_folder = os.path.join(result_folder, func_name)
    # 1. prepare
    if agent_type in ["llm", "llm_dep", "code_agent"]:
        processed_files = prepare_directory_json(origin_code)
    else:
        processed_files = prepare_directory(origin_code, file_changes, result_folder)

    # 2. eval
    is_success, result, time_total = eval_llm_gen_code(database, func_name, agent_type,
                                                       compile_folder, install_folder)

    return is_success, result, time_total


def eval_agent():
    model_name = MODEL_NAME

    suffix = ""  # _declare

    result_data = dict()
    result_folder = os.path.join(dbcode_root, f"results/{database}/{agent_type}_{model_name.split('/')[-1]}")
    result_load = f"{result_folder}/{database}_{agent_type}_{model_name.split('/')[-1]}_results{suffix}.json"
    print("result_load", result_load)
    if os.path.exists(result_load):
        with open(result_load, "r", encoding="utf-8") as rf:
            result_data = json.load(rf)

    # [item for item in list(result_data.values())[:100] if item["is_success"] ]
    # [{func_name: result_data[func_name]} for func_name in result_data if not result_data[func_name]['is_success']]
    for no, (func_name, details) in tqdm(enumerate(result_data.items())):
        print("result_load", result_load)

        if details["response"] is None or len(details["response"]) == 0:
            result_data[func_name]["result_file"] = "LLM Generation Error!"
            result_data[func_name]["time_file"] = -1
            result_data[func_name]["time_total_file"] = -1
            continue

        print(f"== Starting to test function {func_name} ==")
        time_start = time.time()

        is_success = False
        try:
            origin_code = details["origin_code"]

            file_changes = details.get("file_changes", "")
            is_success, result, time_total = eval_single_func(agent_type, func_name,
                                                              origin_code, file_changes, result_folder)

            time_end = time.time()

            result_data[func_name]["is_success_file"] = is_success
            result_data[func_name]["result_file"] = result
            result_data[func_name]["time_file"] = time_end - time_start
            result_data[func_name]["time_total_file"] = time_total

        except Exception as e:
            traceback.print_exc()
            result_data[func_name]["is_success_file"] = is_success
            result_data[func_name]["result_file"] = str(e)
            result_data[func_name]["time_file"] = time.time() - time_start
            result_data[func_name]["time_total_file"] = time.time() - time_start

        finally:
            with open(result_load, "w", encoding="utf-8") as wf:
                json.dump(result_data, wf, indent=4)


if __name__ == "__main__":
    eval_agent()
