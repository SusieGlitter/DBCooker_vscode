import git
import os
import re
import pandas as pd
from git import RemoteProgress


# Progress bar class
class CloneProgress(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        percent = (cur_count / max_count * 100) if max_count else 0
        print(f"\rCloning repository... {percent:.2f}% {message}", end="", flush=True)


def get_commit_type(message):
    """
    Extract type from commit message (strictly match keywords at beginning or end)

    Parameters:
    message (str): commit content

    Returns:
    str: The type corresponding to this commit
    """
    COMMIT_TYPES = ["feat", "fix", "docs", "style", "refactor", "test", "chore", "perf", "build", "ci", "revert"]
    # Build regex expression, type must strictly appear at beginning or end, as independent word
    types_pattern = "|".join(COMMIT_TYPES)
    # Regex divided into three parts: entire string is type, type at beginning followed by content, content followed by type at end
    COMMIT_TYPE_REGEX = rf"^({types_pattern})$|^({types_pattern})\s+.*|.*\s+({types_pattern})$"

    message_lower = message.lower().strip()
    match = re.match(COMMIT_TYPE_REGEX, message_lower)

    if match:
        # Return first non-empty capture group (corresponding to type matched at beginning, middle, or end)
        return next((group for group in match.groups() if group is not None), "unknown")
    return "unknown"


def get_modified_files_and_lines(diff_text):
    """
    Parse git diff output, get modified file list and corresponding line numbers

    Parameters:
    diff_text (str): git diff text

    Returns:
    modified_files (list): Modified file list
    modified_lines (list): Modified file corresponding line number list
    """
    modified_files = []
    modified_lines = []
    current_file = None

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Extract file name
            match = re.search(r'b/(.+)', line)
            if match:
                current_file = match.group(1)
                modified_files.append(current_file)
                modified_lines.append([])

        elif line.startswith("@@"):
            # Parse line number
            match = re.search(r"\+(\d+),?(\d+)?", line)
            if match and current_file:
                start_line = int(match.group(1))
                num_lines = int(match.group(2)) if match.group(2) else 1
                modified_lines[-1].extend(range(start_line, start_line + num_lines))  # Add line numbers

    return modified_files, modified_lines


def get_commits(repo_url, local_path, branch_name):
    """
    Clone a repository and get commit information from it

    Parameters:
    repo_url (str): Repository URL
    local_path (str): Repository save path
    branch_name (str): Repository specified branch

    Returns:
    commits (list): List of all commits
    repo (Repo): Repository object
    """
    if os.path.exists(local_path):
        print("\nRepository already exists, opening directly...")
        repo = git.Repo(local_path)
    else:
        print("\nCloning repository...")
        repo = git.Repo.clone_from(repo_url, local_path, branch=branch_name, progress=CloneProgress())
        print("\nCloning completed!")

    repo.git.checkout(branch_name)
    default_branch = repo.active_branch
    print("Current branch:", default_branch)

    # Get all commits sorted by time
    commits = list(repo.iter_commits(branch_name))

    lenth = len(commits)
    print(f"Repository has {lenth} commits")

    return commits, repo


def get_commits_dep(project, commits, number, repo):
    """
    Get dependency relationships for specified number of commits in project

    Parameters:
    project (understand): Repository understand object
    commits (list): Commit list
    number (int): Number of commits to get
    repo (Repo): Repository object
    """
    commit_data = []

    count = 0
    # Iterate through commits and record data
    for i, commit in enumerate(commits):
        commit_message = commit.message.strip()
        commit_type = get_commit_type(commit_message)  # Get commit type

        print(f"\nSwitching to commit {i + 1}:")
        print(f"  ➤ Hash: {commit.hexsha}")
        print(f"  ➤ Type: {commit_type}")
        print(f"  ➤ Commit message: {commit_message}")
        print(f"Current repository HEAD points to: {repo.head.commit.hexsha}")

        # Switch to this commit and force local file state rollback
        repo.git.checkout(commit.hexsha, detach=True)
        repo.git.reset("--hard")  # **Ensure local files rollback to this commit's state**

        # Get files modified by this commit relative to the previous commit
        lenth = len(commits)
        if i == lenth - 1:
            modified_files_list = []
            modified_lines_list = []
        else:
            diff_text = repo.git.diff(commits[i + 1].hexsha, commit.hexsha, unified=0)
            modified_files_list, modified_lines_list = get_modified_files_and_lines(diff_text)

        file_count = len(modified_files_list)

        print(f"  ➤ Modified files count: {file_count}")
        print(f"  ➤ Modified files: {modified_files_list}")

        # Record data
        if commit_type == "fix":
            # Record data
            commit_data.append([commit.hexsha, commit_type, commit_message, file_count, modified_files_list])

            commit_dep = project.commit_dependency(modified_files_list, 3, modified_lines_list)
            df = pd.DataFrame(commit_dep,
                              columns=["Source File", "Dependency File", "Dependency Description", "Dependency Source", "Dependency Item", "Dependency Line Number", "Dependency Type"])
            commit_path = f"../../{project.project_name}/commits"
            excel_path = commit_path + f"/{commit.hexsha}.xlsx"
            os.makedirs(commit_path, exist_ok=True)
            df.to_excel(excel_path, index=False)

            count += 1
            if count == number:
                break

    # Create DataFrame and save to Excel
    df = pd.DataFrame(commit_data,
                      columns=["Commit Hash", "Commit Type", "Commit Message", "File Count", "Modified Files"])

    excel_path = f"../../{project.project_name}/commit_modifications.xlsx"
    df.to_excel(excel_path, index=False)

    print(f"\nAll commit modification information saved to {excel_path}")

    repo.git.checkout("master")
    repo.git.reset("--hard")  # Restore local files to latest master branch state
    print("Switched back to master branch and restored to latest state")


def get_commits_dep_file(project):
    project_dir = f"../../{project.project_name}"
    full_dir = f"{project_dir}/commit_modifications.xlsx"

    try:
        df = pd.read_excel(full_dir)
    except FileNotFoundError:
        print(f"File {full_dir} not found, please check if the path is correct")
        exit()

    commit_hashes = df["Commit Hash"]
    dep_list = []
    dep_num = []
    for commit_hash in commit_hashes:
        dep = set()
        commit_dep = pd.read_excel(f"../../{project.project_name}/commits/{commit_hash}.xlsx")
        commit_dep_files = commit_dep["依赖文件"]
        for dep_file in commit_dep_files:
            dep.add(dep_file)
        dep_list.append(list(dep))
        dep_num.append(len(dep))

    df["依赖文件"] = dep_list
    df["依赖文件数"] = dep_num
    df.to_excel(full_dir, index=False)

    print(f"Data saved to {full_dir}")











