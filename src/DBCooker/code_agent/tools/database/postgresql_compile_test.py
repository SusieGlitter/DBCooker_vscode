import os
import shutil
import subprocess

from code_utils.constants import database, port, user, cpu_num, bash_path


def compile_postgresql(compile_folder, install_folder, timeout=600):
    # Delete existing folder at target path
    if os.path.exists(install_folder):
        shutil.rmtree(install_folder)

    # Construct bash commands to execute, /path/to/PostgreSQL/build/REL9_5_0
    commands = r"""
    cd {compile_folder}
    ./configure --prefix={install_folder}
    make clean
    make uninstall
    make -j{cpu_num} -s
    make install
    exit
    """.format(compile_folder=compile_folder, cpu_num=cpu_num, install_folder=install_folder)

    # Call bash and run commands, explicitly set encoding to 'utf-8'
    proc = subprocess.Popen(
        [bash_path, '-l'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # or universal_newlines=True
        encoding='utf-8'  # Explicitly set UTF-8 encoding
    )

    # Send commands and get output (out is stdout, err is stderr)
    try:
        out, warn_err = proc.communicate(commands, timeout=timeout)
        # print("-----------------------------")
        # print("out:", out)
        # print("-----------------------------")
        # print("warn_err:", warn_err)
        # print("-----------------------------")

        # if "error" in warn_err:
        if "error" in warn_err.lower():
            return False, warn_err

        return True, out
    except subprocess.TimeoutExpired as e:
        partial_out = e.stdout  # Already output part
        proc.kill()  # Don't forget to kill child process
        return True, partial_out

def init_postgresql(install_folder, data_folder):
    try:
        # Execute initdb command in /path/to/REL9_5_0/bin directory to initialize database
        # initdb_cmd = r'/path/to/REL9_5_0/bin/initdb --pgdata=/path/to/pgsql/pgdata95 --username=user --auth=trust'
        initdb_cmd = f"{install_folder}/bin/initdb --pgdata={data_folder} --username={user} --auth=trust"
        res = subprocess.run(initdb_cmd, shell=True, check=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # print("init_postgresql:", res)
        return True, str(res)
    except Exception as e:
        print(f"初始化 PostgreSQL 失败: {e}")
        return False, str(e)


def start_postgresql(install_folder, data_folder):
    # 启动 PostgreSQL
    try:
        cmd_stop = f'{install_folder}/bin/pg_ctl start -D {data_folder} -o "-p {port[database]}"'
        res = subprocess.run(cmd_stop, shell=True, check=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # print("start_postgresql:", res)
        return True, str(res)
    except Exception as e:
        print(f"启动 PostgreSQL 失败: {e}")
        return False, str(e)


def stop_postgresql(install_folder, data_folder):
    # 停止 PostgreSQL
    try:
        cmd_stop = f'{install_folder}/bin/pg_ctl stop -D {data_folder} -o "-p {port[database]}"'
        res = subprocess.run(cmd_stop, shell=True, check=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # print("stop_postgresql:", type(res), res)
        return True, str(res)
    except Exception as e:
        print(f"停止 PostgreSQL 失败: {e}")
        return False, str(e)


def status_postgresql(install_folder, data_folder):
    # 探测 PostgreSQL
    try:
        cmd_stop = f'{install_folder}/bin/pg_ctl status -D {data_folder} -o "-p {port[database]}"'
        res = subprocess.run(cmd_stop, shell=True, check=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, str(res)
    except Exception as e:
        print(f"探测 PostgreSQL 失败: {e}")
        return False, str(e)


def installcheck_postgresql(compile_folder):
    """
    使用 MSYS2 bash 执行 make installcheck，并捕获输出。
    """
    commands = r"""
    cd {compile_folder}
    make installcheck PGUSER={user} PGPORT={port}
    exit
    """.format(compile_folder=compile_folder, user=user, port=port[database])
    try:
        proc = subprocess.Popen(
            [bash_path, '-l'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )

        out, warn_err = proc.communicate(commands)
        # print("------ 标准输出 ------")
        # print(type(out))
        # print("out:", out)
        # print("------ 错误输出 ------")
        # print(warn_err)

        if "failed" in warn_err.lower():
            out = warn_err
        return True, out
    except Exception as e:
        print(f"执行 installcheck 失败: {e}")
        return False, str(e)


if __name__ == "__main__":
    compile_folder, data_folder = "", ""
    init_postgresql(compile_folder, data_folder)
    installcheck_postgresql(compile_folder)
