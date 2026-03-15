# -*- coding: utf-8 -*-
# @Project: index_test
# @Module: constants
# @Author: Anonymous
# @Time: 2025/8/16 18:50

# ------------ SYSTEM CONFIGURATION ------------

# BASE_URL = ""

import os

# Use EXTENSION_PATH if available (set by the extension), otherwise use relative path from this file
extension_path = os.environ.get('EXTENSION_PATH')
if not extension_path:
    # Fallback to extension root assuming we are in src/py/DBCode/code_utils/
    extension_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

# Root of the Python project
dbcode_root = os.path.join(extension_path, "src", "py", "DBCode")

user_name = os.environ.get('USER') or os.environ.get('USERNAME')
user = user_name if user_name else "default_user"

# Define a workspace directory within the extension
workspace_dir = os.path.join(extension_path, "workspace")
if not os.path.exists(workspace_dir):
    os.makedirs(workspace_dir, exist_ok=True)

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

# Use paths within the workspace directory
backup_folder = os.path.join(workspace_dir, "source", database)
compile_folder = os.path.join(workspace_dir, "code", f"{agent_type}_{database}{port[database]}")
install_folder = os.path.join(workspace_dir, "db", f"{agent_type}_{database}{port[database]}")
data_folder = os.path.join(install_folder, f"{database}_data")

# compile_folder = f"/data/{user_name}/code/postgres"
# compile_folder = f"/data/{user_name}/code/{database}"
#
# install_folder = f"/data/{user_name}/db/{database}"

# compile_folder = "/data/{user_name}/code/duckdb_test"
# install_folder = "/data/{user_name}/db/duckdb_test"

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
understand_dir = f"/home/{user_name}/software/scitools/bin/linux64"

# LD_LIBRARY_PATH=/home/{user_name}/software/scitools/bin/linux64
# PATH=/home/{user_name}/software/scitools/bin/linux64
# PYTHONPATH=/home/{user_name}/software/scitools/bin/linux64/Python

# bash_path = r"D:\msys64\usr\bin\bash.exe"
bash_path = "/bin/bash"

API_KEY = ""
BASE_URL = ""
MODEL_NAME = ""