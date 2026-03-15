import os
import shutil
import subprocess
import sys
import time
import json
import glob

from code_utils.constants import cpu_num, user_name

# ================ Configuration Paths ================
BUILD_DIR = "build"
SQLITE_DIR = "."  # Current directory is sqlite directory
SQLITE3_BIN = os.path.join(BUILD_DIR, "sqlite3")
TESTFIXTURE_BIN = os.path.join(BUILD_DIR, "testfixture")
TCL_LIBRARY_PATH = f"/home/{user_name}/anaconda3/lib/"  # Modify according to actual TCL installation path
# Test configuration
TEST_TXT_PATH = "sqlite_tests.txt"  # txt file for which tests to run, one test name per line
TEST_RESULTS_JSON = "sqlite_test_results.json"  # Test results save path
TEST_TIMEOUT = 300  # 5 minutes

# Batch test types
BATCH_TEST_TYPES = {
    "devtest": "Development test (srctree-check + source code check)",
    "releasetest": "Release test (excluding srctree-check and source code check)",
    "quicktest": "Quick test (including partial tcl tests, excluding exception, fuzzy and soak tests)",
    "tcltest": "tcl test"
}


# ================ Functional Functions ================

def run_cmd(cmd, cwd=None, shell=True, env=None, timeout=600):
    print(f"[Execute] {cmd}")
    proc = subprocess.run(cmd, cwd=cwd, shell=shell, env=env,
                          capture_output=True,  # Capture stdout and stderr
                          text=True,  # Return as string (not bytes)
                          timeout=timeout,  # Set timeout
                          )
    if proc.returncode != 0:
        print(f"[Failed] {cmd}\n{proc.stderr}")
        raise Exception(proc.stderr)
        # sys.exit(proc.returncode)

    return proc.stdout


def compile_sqlite(compile_folder, timeout=600):
    """Complete SQLite compilation"""
    try:
        out = str()

        print("[2/6] Creating build folder...")
        os.makedirs(f"{compile_folder}/{BUILD_DIR}", exist_ok=True)

        print("[3/6] Configuring SQLite...")
        # configure_path = [
        #     # f"../configure --prefix={install_folder} --with-tcl={install_folder}/lib",
        #     f"../configure --with-tcl={TCL_LIBRARY_PATH}",
        #     f"make sqlite3 -j{cpu_num}",
        #     f"make tclextension-install -j{cpu_num}"
        # ]
        configure_path = [
            f"../configure",
            f"make sqlite3 -j{cpu_num}",
            f"make tclextension -j{cpu_num}"
        ]
        out += run_cmd(" && ".join(configure_path), cwd=f"{compile_folder}/{BUILD_DIR}", timeout=timeout)

        # print("[4/6] Compiling sqlite3...")
        # out += run_cmd(, cwd=f"{compile_folder}/{BUILD_DIR}")
        #
        # print("[5/6] Installing TCL extension...")
        # out += run_cmd(, cwd=f"{compile_folder}/{BUILD_DIR}")

        print("[6/6] Compilation completed!")
        return True, out
    except Exception as e:
        print(f"Compile error occurs {e}")
        if "timed out" in str(e).lower():
            return True, ""
        return False, str(e)


def incremental_build():
    """Incremental compilation"""
    print("[1/1] Incremental compilation of sqlite3...")
    run_cmd("make sqlite3", cwd=BUILD_DIR)

    print("[1/1] Incremental compilation completed!")


def run_batch_test(compile_folder, test_type="quicktest"):
    """Run batch tests"""
    print(f"[Batch Test] Running {test_type}")
    if not os.path.exists(f"{compile_folder}/{BUILD_DIR}"):
        print(f"Error: Cannot find build directory {compile_folder}/{BUILD_DIR}")
        # sys.exit(1)
        return False, f"Error: Cannot find build directory {compile_folder}/{BUILD_DIR}"

    # Run specified batch test
    try:
        out = run_cmd(f"make {test_type} -j{cpu_num}", cwd=f"{compile_folder}/{BUILD_DIR}")
        print(f"[Batch Test] {test_type} completed")
        return True, out
    except Exception as e:
        print(f"Test error occurs {e}")
        return False, str(e)


def build_testfixture(compile_folder):
    """Build testfixture (TCL interpreter)"""
    print("[Build] testfixture...")

    out = run_cmd(f"make testfixture -j{cpu_num}", cwd=f"{compile_folder}/{BUILD_DIR}")

    # if not os.path.exists(TESTFIXTURE_BIN):
    #     print(f"Error: testfixture build failed {TESTFIXTURE_BIN}")
    #     sys.exit(1)

    print("[Build] testfixture build successful")
    return out


def run_single_tests(compile_folder, txt_path=None):
    """Run single TCL test"""
    if txt_path is None:
        txt_path = TEST_TXT_PATH

    if not os.path.isfile(txt_path):
        print(f"File not found: {txt_path}")
        return

    # Ensure testfixture is built
    testfixture_bin = f"{compile_folder}/{BUILD_DIR}/testfixture"
    if not os.path.exists(testfixture_bin):
        print("[Prepare] Building testfixture...")
        build_testfixture(compile_folder)

    with open(txt_path, 'r', encoding='utf-8') as f:
        test_files = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    results = []
    passed_count = 0
    failed_count = 0

    print(f"Starting to run {len(test_files)} single tests...")
    for i, test_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] {test_file} ...", end=" ")

        # Check if test file exists
        if not os.path.exists(test_file):
            print("文件不存在")
            failed_count += 1
            results.append({
                "test_file": test_file,
                "passed": False,
                "reason": "测试文件不存在"
            })
            continue

        # 运行单条测试 - 使用相对于build目录的路径
        cmd = ["./testfixture", os.path.join("..", test_file)]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=TEST_TIMEOUT, cwd=BUILD_DIR)
            passed = (result.returncode == 0)
            reason = "" if passed else result.stderr.decode(errors="ignore")
        except subprocess.TimeoutExpired:
            passed = False
            reason = f"超时（超过{TEST_TIMEOUT // 60}分钟）"
        except Exception as e:
            passed = False
            reason = str(e)

        if passed:
            print("通过")
            passed_count += 1
        else:
            print("未通过")
            failed_count += 1
            if reason:
                print(f"    原因: {reason[:100]}...")

        results.append({
            "test_file": test_file,
            "passed": passed,
            "reason": reason
        })

    # 保存测试结果
    with open(TEST_RESULTS_JSON, "w", encoding="utf-8") as jf:
        json.dump(results, jf, ensure_ascii=False, indent=2)

    print(f"测试完成：通过 {passed_count} 个，未通过 {failed_count} 个，总数 {len(test_files)}")
    print(f"详细结果已保存到 {TEST_RESULTS_JSON}")


def run_sqlite_function_tests(compile_folder):
    """运行函数相关的测试"""
    function_tests = [
        "changes2.test", "coalesce.test", "ctime.test", "dbdata.test", "e_totalchanges.test",
        "exprfault.test", "fts3rank.test", "func.test", "func2.test", "func3.test",
        "func4.test", "func5.test", "func6.test", "func7.test", "func8.test",
        "func9.test", "init.test", "main.test", "notnullfault.test", "percentile.test",
        "substr.test", "vtab1.test", "whereL.test", "window9.test", "windowD.test",
        "windowerr.test", "windowfault.test"
    ]

    # Ensure testfixture is built
    testfixture_bin = f"{compile_folder}/{BUILD_DIR}/testfixture"
    if not os.path.exists(testfixture_bin):
        print("[Prepare] Building testfixture...")
        build_testfixture(compile_folder)

    # results = []
    # passed_count = 0
    # failed_count = 0

    out = str()
    print(f"开始运行 {len(function_tests)} 个函数测试...")
    for i, test_file in enumerate(function_tests):
        print(f"[{i}/{len(function_tests)}] {test_file} ...")

        # 构建完整的测试文件路径
        test_path = f"{compile_folder}/test/{test_file}"
        # Check if test file exists
        # if not os.path.exists(test_path):
        #     print("文件不存在")
        #     failed_count += 1
        #     results.append({
        #         "test_file": test_file,
        #         "passed": False,
        #         "reason": "测试文件不存在"
        #     })
        #     continue

        # 运行单条测试 - 使用相对于build目录的路径
        cmd = ["./testfixture", test_path]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=TEST_TIMEOUT, cwd=f"{compile_folder}/{BUILD_DIR}")
            if result.returncode != 0:
                err = result.stderr.decode(errors="ignore")
                if len(err) == 0:
                    err = result.stdout.decode(errors="ignore")
                return False, err

            if "0 errors out of" not in result.stdout.decode(errors="ignore"):
                return False, result.stdout.decode(errors="ignore")

            out += result.stdout.decode(errors="ignore") + "\n"
        except subprocess.TimeoutExpired:
            # passed = False
            reason = f"超时（超过 {TEST_TIMEOUT // 60} 分钟）"
            return False, reason
        except Exception as e:
            # passed = False
            reason = str(e)
            return False, reason

        # if passed:
        #     print("通过")
        #     passed_count += 1
        # else:
        #     print("未通过")
        #     failed_count += 1
        #     if reason:
        #         print(f"    原因: {reason[:100]}...")

        # results.append({
        #     "test_file": test_file,
        #     "passed": passed,
        #     "reason": reason
        # })

    # 保存测试结果
    # function_results_json = "sqlite_function_test_results.json"
    # with open(function_results_json, "w", encoding="utf-8") as jf:
    #     json.dump(results, jf, ensure_ascii=False, indent=2)

    # print(f"函数测试完成：通过 {passed_count} 个，未通过 {failed_count} 个，总数 {len(function_tests)}")
    # print(f"详细结果已保存到 {function_results_json}")
    return True, out


def main():
    print("SQLite 编译和测试脚本")
    print("=" * 50)

    compile_folder = "compile_folder"
    install_folder = "install_folder"

    # 选择编译方式
    try:
        # 1. 完整编译
        compile_sqlite(compile_folder=compile_folder, install_folder=install_folder)

        # 2. 增量编译
        # incremental_build()
    except Exception as e:
        print(f"Compile error occurs {e}")
        return False, str(e)

    # 选择测试方式
    try:
        # 1. 批量测试（选择测试类型）
        run_batch_test("releasetest")  # quicktest, devtest, releasetest, tcltest

        # 2. 单条测试（使用默认路径）
        # run_single_tests()

        # 3. 单条测试（自定义路径）
        # 如果有测试文件列表，运行单条测试
        # if os.path.exists(TEST_TXT_PATH):
        # rint("\n" + "=" * 50)
        # run_single_tests()
        # run_single_tests("custom/path/to/tests.txt")

        # 4. 函数测试
        # run_function_tests()
    except Exception as e:
        print(f"Test error occurs {e}")
        return False, str(e)

    print("\n全部流程完成！")
    return True,


if __name__ == "__main__":
    main()
