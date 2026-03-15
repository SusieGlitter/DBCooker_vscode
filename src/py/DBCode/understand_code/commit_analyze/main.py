from datetime import datetime

import git

from understand_code.model import UnderstandRepo
from understand_code.commit_analyze.utils import get_commits, get_commits_dep, get_commits_dep_file, \
    get_modified_files_and_lines

# Set repository address and local storage path
repo_url = "https://github.com/postgres/postgres"  # GitHub repository address
local_path = "/path/to/pythonProjects\\postgres"  # Local storage path
branch_name = "master"  # Repository branch
lang = "C++"    # Repository language
number = 1000    # Number of commits to fetch
project = UnderstandRepo(lang, local_path)
project.get_db()

# Get all repository commits
commits, repo = get_commits(repo_url, local_path, branch_name)

# Get specific dependency relationships of modified files for each commit of specified quantity
get_commits_dep(project, commits, number, repo)

# Get dependency file list and dependency file count for each commit in all saved commits
get_commits_dep_file(project)

# Analyze LCA of modified files
file_type = "Modified Files"
project.find_lca(file_type)

# Analyze LCA of dependency files
file_type = "Dependency Files"
project.find_lca(file_type)

