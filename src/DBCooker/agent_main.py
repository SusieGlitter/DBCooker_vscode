# -*- coding: utf-8 -*-
# @Project: DBCode
# @Module: agent_main
# @Author: Anonymous
# @Time: 2025/9/13 15:55

import os
import json
import shlex
import shutil
import subprocess
import time

import pandas as pd
from tqdm import tqdm
from datetime import datetime

import sys

sys.path.append("/data/user/program/DBCode")

from trae_agent.cli import run as trae_run

from code_agent.cli import run as code_run
from code_agent.agent import BaseAgent
from code_agent.prompt.agent_prompt import USER_PROMPT_VIBE_CODING

from code_utils.sample import eval_llm_gen_code
from code_utils.fileControl import replace_compile_with_backup, process_list_data
from code_utils.constants import agent_type, compile_folder, backup_folder, install_folder, database, MODEL_NAME, \
    db_name


def prepare_directory(origin_code):
    # TODO: to be modified with declaration.
    origin_gen_code = [origin_code, []]
    replace_compile_with_backup(compile_folder, backup_folder, database=None)
    processed_files = process_list_data(origin_gen_code, database)
    print("==File modification completed==")

    return processed_files


def get_git_diff(compile_folder, result_folder) -> (str, list):
    """Get the git diff of the project."""
    # pwd = os.getcwd()
    if not os.path.isdir(compile_folder):
        return "", []

    os.chdir(compile_folder)
    try:
        _ = subprocess.check_output(["git", "add", "."]).decode()
        code_changes = subprocess.check_output(["git", "--no-pager", "diff", "--staged"]).decode()

        file_list = subprocess.check_output(["git", "--no-pager", "diff",
                                             "--staged", "--name-only"]).decode().splitlines()
        for file in file_list:
            file = file.split("\t")[-1]
            src = os.path.join(compile_folder, file)
            dst = os.path.join(result_folder, file)
            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))

            shutil.copyfile(src, dst)

        # if not self.base_commit:
        #     stdout = subprocess.check_output(["git", "--no-pager", "diff"]).decode()
        # else:
        #     stdout = subprocess.check_output(
        #         ["git", "--no-pager", "diff", self.base_commit, "HEAD"]
        #     ).decode()
    except (subprocess.CalledProcessError, FileNotFoundError):
        code_changes = ""
        file_list = []

    # finally:
    #     os.chdir(pwd)

    return code_changes, file_list


def run_code_agent(task, working_dir, config_file, must_patch,
                   patch_path, trajectory_file, console_type, agent_type):
    is_success, response, execution_time = code_run(
        task=task,
        file_path=None,
        working_dir=working_dir,
        config_file=config_file,
        # model: str | None = None,
        # model_base_url: str | None = None,
        # api_key: str | None = None,
        # max_steps: int | None = None,
        must_patch=must_patch,
        patch_path=patch_path,
        trajectory_file=trajectory_file,
        console_type=console_type,
        agent_type=agent_type,
    )

    return is_success, response, execution_time


def main():
    timeout = 300

    fdp_load = (f"/data/user/program/DBCode/data/benchmark/{database}/"
                f"{database}_functions_with_testcase_code_understand.json")
    with open(fdp_load, "r", encoding="utf-8") as rf:
        fdp = json.load(rf)

    model_name = MODEL_NAME

    # [result_data[func_name] for func_name in result_data if result_data[func_name]['is_success']]
    result_data = dict()
    result_folder = f"/data/user/program/DBCode/results/{database}/{agent_type}_{model_name.split('/')[-1]}"
    result_load = f"{result_folder}/{database}_{agent_type}_{model_name.split('/')[-1]}_results.json"
    print("result_load", result_load)
    if os.path.exists(result_load):
        with open(result_load, "r", encoding="utf-8") as rf:
            result_data = json.load(rf)

    for no, details in tqdm(enumerate(fdp)):
        print("result_load", result_load)
        func_name = details["keyword"]

        # 1.
        origin_code = dict()
        for item in details["code"].values():
            for file, content in item[1].items():
                if file not in origin_code.keys():
                    origin_code[file] = list()
                origin_code[file].append(content)
        prepare_directory(origin_code)

        # 2.
        description = "\n".join(details["description"]) if (
            isinstance(details["description"], list)) else details["description"]
        example = "\n".join(details["example"]) if (
            isinstance(details["example"], list)) else details["example"]
        category = details["category"]
        file_path = "\n".join(origin_code.keys())
        task = {
            "database": database, "db_name": db_name, "directory": compile_folder,
            "func_name": func_name, "category": category, "description": description,
            "example": str(example), "file_path": file_path,
            "compile_folder": compile_folder, "result_folder": result_folder,
            "backup_folder": backup_folder, "origin_code": origin_code,
            "spec_file": {
                "postgresql": "/data/user/program/DBCode/data/benchmark/postgresql/"
                              "postgresql_functions_with_testcase_code_understand.json",
                "sqlite": "/data/user/program/DBCode/data/benchmark/sqlite/"
                          "sqlite_functions_with_testcase_code_understand.json",
                "duckdb": "/data/user/program/DBCode/data/benchmark/duckdb/"
                          "duckdb_functions_with_testcase_code_understand.json",
            }
        }

        config_file = "/data/user/program/DBCode/code_config.yaml"
        # TODO: to be modified (NONE).
        console_type = "simple"
        # console_type = None

        must_patch = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patch_path = (f"{result_folder}/{func_name}/"
                        f"{database}_{agent_type}_{model_name.split("/")[-1]}_{func_name}_{timestamp}_patch.txt")
        trajectory_file = (f"{result_folder}/{func_name}/"
                            f"{database}_{agent_type}_{model_name.split("/")[-1]}_{func_name}_{timestamp}_trajectory.json")
        if not os.path.exists(os.path.dirname(patch_path)):
            os.makedirs(os.path.dirname(patch_path))

        user_prompt = task
        is_success, response, execution_time = run_code_agent(task, compile_folder, config_file, must_patch,
                                                                patch_path, trajectory_file, console_type, agent_type)

        gen_code, file_changes = "", []
        if is_success:
            gen_code, file_changes = get_git_diff(compile_folder, f"{result_folder}/{func_name}")
        result_data[func_name] = {
            "prompt": user_prompt, "origin_code": origin_code,
            "is_success": is_success, "execution_time": execution_time, "response": response,
            "gen_code": gen_code, "file_changes": file_changes
        }

        if not os.path.exists(os.path.dirname(result_load)):
            os.makedirs(os.path.dirname(result_load))

        with open(result_load, "w", encoding="utf-8") as wf:
            json.dump(result_data, wf, indent=4)



if __name__ == "__main__":
    main()
