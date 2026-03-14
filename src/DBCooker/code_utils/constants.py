# -*- coding: utf-8 -*-
# @Project: index_test
# @Module: constants
# @Author: Anonymous
# @Time: 2025/8/16 18:50

# ------------ SYSTEM CONFIGURATION ------------

# BASE_URL = ""

cpu_num = 32

agent_type = "code_agent"  # llm, code_agent, qwen_code, claude_code, gemini_cli, trae_agent

# ------------ DATABASE CONFIGURATION ------------

database = "sqlite"  # postgresql, sqlite, duckdb, clickhouse
port = {
    "postgresql": 5433,
    "sqlite": 5532,
    "duckdb": 5434,
}

if_dep = False
if_cache = True

# backup_folder = "/data/user/program/source/postgres"
backup_folder = f"/data/user/source/{database}"
# backup_folder = "/data/user/program/source/postgres-REL9_5_STABLE"

compile_folder = f"/data/user/code/{agent_type}_{database}{port[database]}"
install_folder = f"/data/user/db/{agent_type}_{database}{port[database]}"
data_folder = f"{install_folder}/{database}_data"

# compile_folder = f"/data/user/code/postgres"
# compile_folder = f"/data/user/code/{database}"
#
# install_folder = f"/data/user/db/{database}"

# compile_folder = "/data/user/code/duckdb_test"
# install_folder = "/data/user/db/duckdb_test"

# Postgresql
# data_folder = f"{install_folder}/pg_data"

test_suffix = {
    "postgresql": ["diffs", "out"]
}

# ------------ EXPERIMENT CONFIGURATION ------------

lang_dict = {
    "postgresql": "C++",
    "sqlite": "C++",
    "duckdb": "C++"
}

db_name = {
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite",
    "duckdb": "DuckDB"
}

# understand_dir = "/path/to/SciTools\\bin\\pc-win64"
understand_dir = "/home/user/software/scitools/bin/linux64"

# LD_LIBRARY_PATH=/home/user/software/scitools/bin/linux64
# PATH=/home/user/software/scitools/bin/linux64
# PYTHONPATH=/home/user/software/scitools/bin/linux64/Python

# bash_path = r"D:\msys64\usr\bin\bash.exe"
bash_path = "/bin/bash"
