# -*- coding: utf-8 -*-
# @Project: DBCode
# @Module: benchmark_utils
# @Author: Anonymous
# @Time: 2025/9/28 22:43

import json


def merge_code_testcase():
    # code_load = "/data/user/program/DBCode/data/benchmark/sqlite/sqlite_functions_with_code.json"
    code_load = "/data/user/program/DBCode/data/benchmark/postgresql/pg14_functions_with_code.json"
    with open(code_load, "r") as rf:
        code_data = json.load(rf)

    # testcase_load = "/data/user/program/DBCode/data/benchmark/sqlite/sqlite_functions_with_testcase.json"
    testcase_load = "/data/user/program/DBCode/data/benchmark/postgresql/pg14_functions_with_testcase.json"
    with open(testcase_load, "r") as rf:
        testcase_data = json.load(rf)

    code_testcase_data = list()
    for code_item in code_data:
        func_name = code_item["keyword"]
        for testcase_item in testcase_data:
            if testcase_item["keyword"] == func_name:
                testcase_item["code"] = code_item["code"]
                code_testcase_data.append(testcase_item)
                break

    with open(testcase_load.replace(".json", "_code.json"), "w") as wf:
        json.dump(code_testcase_data, wf, indent=4)


if __name__ == "__main__":
    merge_code_testcase()
