import os
import re
import stat

import shutil
import subprocess
import time
from datetime import datetime

# TODO: to be removed
from code_utils.constants import compile_folder, agent_type

LOG_FILE = "modification_log.txt"


def on_rm_error_v1(func, path, exc_info):
    """
    Callback function for handling read-only file deletion failures.
    """
    if not os.access(path, os.W_OK):
        # Change file permissions to writable
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise Exception("rm file error.")


def on_rm_error(func, path, exc_info):
    """
    Error handling callback function for shutil.rmtree
    Attempts to resolve deletion failures caused by postgres occupation or read-only permissions
    """
    # Step 1: Print original error (optional)
    print(f"⚠️ Deletion failed: {path} -> {exc_info[1]}")

    # Step 2: Try to terminate postgres processes occupying this path
    try:
        # Use lsof to check if any processes are occupying this file/directory
        result = subprocess.run(
            ['lsof', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        if result.returncode == 0 and 'postgres' in result.stdout:
            print(f"🔒 Detected postgres occupation: {path}")

            # Extract PID and kill -9
            lines = result.stdout.strip().split('\n')[1:]
            pids = [line.split()[1] for line in lines if line]
            if pids:
                outputs = []
                for pid in pids:
                    outputs.append(subprocess.check_output(["ps", "-fp", pid]).decode('utf-8'))
                out = '\n'.join(outputs)
                print(out)

                print(f"💀 Force terminating postgres process PID: {pids}")
                subprocess.run(['kill', '-9'] + pids)

                # Wait for resource release
                time.sleep(1)
    except Exception as e:
        print(f"❌ Failed to terminate process: {e}")

    # Step 3: Fix permissions (for read-only files)
    try:
        os.chmod(path, 0o755)
        print(f"🔧 Fixed permissions: {path}")
    except Exception as e:
        print(f"❌ Failed to modify permissions: {e}")

    # Step 4: Try the original operation again (delete file or directory)
    try:
        func(path)  # Try os.remove or os.rmdir again
        print(f"✅ Successfully deleted: {path}")
    except Exception as e:
        print(f"❌ Still unable to delete {path}: {e}")
        raise  # If you still want rmtree to throw an exception, re-raise


def replace_compile_with_backup(compile_dir, backup_dir, database=None):
    """
    Delete the compile_dir folder, then copy the backup_dir folder to the source_dir location and rename it to source_dir.

    :param compile_dir: Original source folder path
    :param backup_dir: Backup postgres folder path
    """
    if database == "duckdb":
        cmd = ["git", "add", "."]
        _ = subprocess.run(
            cmd,
            cwd=compile_folder,
            check=True,
            text=True,
            capture_output=True
        )

        cmd = ["git", "reset", "--hard"]
        _ = subprocess.run(
            cmd,
            cwd=compile_folder,
            check=True,
            text=True,
            capture_output=True
        )
        print("Already reset the repository")

    else:
        # Ensure path exists
        if os.path.exists(compile_dir):
            print(f"Deleting folder: {compile_dir}")
            shutil.rmtree(compile_dir, onerror=on_rm_error)
            # shutil.rmtree(compile_dir)
            # subprocess.check_call(['rm', '-rf', compile_dir])
        else:
            print(f"Source folder does not exist: {compile_dir}")

        # Target path, i.e., the folder path after copying and renaming to source
        target_dir = compile_dir
        if os.path.exists(backup_dir):
            shutil.copytree(backup_dir, target_dir, symlinks=True)
            print(f"Copied folder {backup_dir} to {target_dir}")
        else:
            print(f"Backup folder does not exist: {backup_dir}")


def replace_files_with_backup(positions: set, source_dir: str, backup_dir: str):
    for position in positions:
        # Get relative path: relative to source_dir
        relative_path = os.path.relpath(position, start=source_dir)

        # Build the complete path of the corresponding file in backup_dir
        backup_file_path = os.path.join(backup_dir, relative_path)
        print(f"Preparing to replace: {position} and {backup_file_path}")

        # Replace file: copy backup file to overwrite the original file location
        shutil.copy2(backup_file_path, position)

        print(f"Replaced {position} with backup file {backup_file_path}")


class Tee:
    def __init__(self, *targets):
        self.targets = targets

    def write(self, data):
        for t in self.targets:
            t.write(data)

    def flush(self):
        for t in self.targets:
            t.flush()


# --------20250816---------


def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def write_file(file_path, content):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)


def log_action(action, file_path, content, position=None):
    with open(LOG_FILE, 'a+', encoding='utf-8') as log:
        log.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
        log.write(f"ACTION: {action}\n")
        log.write(f"FILE: {file_path}\n")
        if position is not None:
            log.write(f"POSITION: {position}\n")
        log.write("CONTENT:\n")
        log.write(content.strip() + '\n')
        log.write("=" * 50 + '\n')


def delete_content(file_path, content):
    file_data = read_file(file_path)

    # Normalize line breaks and remove whitespace on both sides
    # print(content)
    # print("=================================================")
    content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
    file_data_normalized = file_data.replace('\r\n', '\n').replace('\r', '\n')
    # print(file_path)
    # print("=================================================")
    # print(repr(content))
    # print("=================================================")
    # print(repr(file_data_normalized))
    # print("=================================================")

    start_index = file_data_normalized.find(content)
    if start_index == -1:
        print(f"[Skip] No exact match found, file: {file_path}")
        return -1

    # Precisely delete this segment of content
    end_index = start_index + len(content)

    # Remove extra blank lines before and after
    before = file_data_normalized[:start_index].rstrip('\n')
    after = file_data_normalized[end_index:].lstrip('\n')
    new_data = before + '\n' + after  # Ensure format remains clean after deletion

    write_file(file_path, new_data)
    deleted_start_line = file_data_normalized[:start_index].count('\n')

    print("file_path", file_path)
    # log_action("DELETE_BLOCK", file_path, content, deleted_start_line)
    print(f"[Delete] Deleted complete code block from {file_path}, starting line {deleted_start_line}")

    return deleted_start_line


def insert_content(file_path, content, line_number=None, database=None):
    # # TODO: to be removed.
    # content = content.replace("res = make_result(&const_zero);", "res = make_result(&const_nan);")
    # content = content.replace("res = num;", "res = make_result(&const_nan);")
    # content = content.replace("PG_RETURN_INT64(res);", "PG_RETURN_INT64(DirectFunctionCall1(int4_numeric, Int32GetDatum(42)));")

    # TODO: new file, to be removed
    if os.path.exists(file_path):
        file_data = read_file(file_path)
        file_lines = file_data.splitlines(keepends=True)  # Keep \n

        # Existing include lines in the file (remove spaces)
        existing_includes = {
            line.strip()
            for line in file_lines
            if line.strip().startswith("#include")
        }

        # TODO: check, extract include lines from insertion content
        include_lines = re.findall(r'^\s*#include\s+[<"].+[>"]', content, re.MULTILINE)
        include_lines = [line.strip() for line in include_lines]

        # Only insert includes that don't already exist
        unique_includes = [line for line in include_lines if line not in existing_includes]

        # Find the line number of the last include line
        last_include_line = -1
        for i, line in enumerate(file_lines):
            if line.strip().startswith("#include"):
                last_include_line = i

        # Build the line list after inserting includes
        if unique_includes:
            include_to_insert = [line + "\n" for line in unique_includes]
            insert_pos = last_include_line + 1 if last_include_line >= 0 else 0
            file_lines = file_lines[:insert_pos] + include_to_insert + file_lines[insert_pos:]

            write_file(file_path, "".join(file_lines))
            # log_action("INSERT_INCLUDE", file_path, "\n".join(unique_includes))
            print(f"Inserted #include into {file_path}")

        # Process non-include parts
        content_lines = content.splitlines(keepends=True)
        other_lines = [
            line for line in content_lines
            if line.strip() not in include_lines
        ]

        other_code = "".join(other_lines).strip()
        if other_code:
            insert_lines = other_code.splitlines(keepends=False)
            if line_number is not None:
                file_lines = read_file(file_path).splitlines(keepends=True)
                file_lines = file_lines[:line_number] + [line + '\n' for line in insert_lines] + file_lines[
                                                                                                 line_number:]
                write_file(file_path, ''.join(file_lines))
                # log_action("RESTORE", file_path, other_code, line_number)
                print(f"Restored original content at line {line_number} in {file_path}")

            elif database == "sqlite":
                file_lines = read_file(file_path).splitlines(keepends=True)
                line_number = len(file_lines)
                for no, line in enumerate(file_lines):
                    if "void sqlite3Register" in line:
                        line_number = no
                        break
                file_lines = file_lines[:line_number] + [line + '\n' for line in insert_lines] + ['\n'] + file_lines[
                                                                                                          line_number:]
                write_file(file_path, ''.join(file_lines))
                # log_action("INSERT_OTHER", file_path, other_code, line_number)
                print(f"[Middle ({line_number})] Inserted non-include content to {file_path}")

            # TODO: to be removed.
            elif database == "duckdb":
                file_content = read_file(file_path)
                file_lines = file_content.splitlines(keepends=True)
                line_number = len(file_lines)
                for no, line in enumerate(file_lines):
                    if "namespace duckdb {" in line:
                        line_number = no
                        break
                file_lines = file_lines[:line_number] + [line + '\n' for line in insert_lines] + ['\n'] + file_lines[
                                                                                                          line_number:]
                file_lines.append('\n' + '\n'.join(insert_lines) + '\n')
                write_file(file_path, ''.join(file_lines))
                print(f"[Middle ({line_number})] Inserted non-include content to {file_path}")

            else:
                file_lines = read_file(file_path).splitlines(keepends=True)
                file_lines.append('\n' + '\n'.join(insert_lines) + '\n')
                # file_lines.append('\n' + '\n'.join(insert_lines[:-10]) + '\n')
                write_file(file_path, ''.join(file_lines))
                # log_action("INSERT_OTHER", file_path, other_code)
                print(f"[End] Inserted non-include content to {file_path}")
    else:
        # Check if the path is relative to some known roots or absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(compile_folder, file_path)
            
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        write_file(file_path, content)
    return 0


def remove_inserted_content(file_path, inserted_content):
    file_lines = read_file(file_path).splitlines(keepends=False)
    inserted_lines = [line.strip() for line in inserted_content.splitlines() if line.strip()]

    new_file_lines = []
    skip_mode = False

    for i, line in enumerate(file_lines):
        stripped_line = line.strip()

        if stripped_line in inserted_lines:
            skip_mode = True
            continue

        if skip_mode and stripped_line == '':
            continue

        skip_mode = False
        new_file_lines.append(line)

    write_file(file_path, '\n'.join(new_file_lines) + '\n')
    # log_action("REMOVE_INSERTED", file_path, inserted_content)
    print(f"Cleaned inserted content (with empty lines) from {file_path}")


def process_list_data(data_list, database):
    assert isinstance(data_list, list) and len(data_list) == 2
    delete_data, insert_data = data_list
    processed_files = set()
    for file_path, contents in delete_data.items():
        file_path = file_path.replace("\\", "/")
        # Convert absolute legacy paths to relative to compile_folder if they look like they belong there
        if "/data/user/code/" in file_path or "/data/user/program/DBCode/code/" in file_path:
            file_path = os.path.join(compile_folder, os.path.basename(file_path))
        
        processed_files.add(file_path)
        for content in set(contents):
            line = delete_content(file_path, content)
            if line == -1:
                print(f"Failed to delete the function content in `{file_path}`.")
                # raise Exception(f"Failed to delete the function content in `{file_path}`.")

    if len(insert_data) > 0:
        for file_path, content in insert_data.items():
            # TODO: to be removed.
            if database == "duckdb":
                path = [key for key in delete_data.keys() if key.endswith(file_path.split(".")[-1])]
                if len(path) > 0:
                    file_path = path[0]

            file_path = file_path.replace("\\", "/")
            # Convert absolute legacy paths to relative to compile_folder
            if "/data/user/code/" in file_path or "/data/user/program/DBCode/code/" in file_path:
                file_path = os.path.join(compile_folder, os.path.basename(file_path))

            processed_files.add(file_path)
            print(f"Processed content of `{file_path}`")

            # TODO: to be removed.
            if database == "duckdb":
                content = content.replace("namespace duckdb {", "")
                content = content.replace("} // namespace duckdb", "")

            line = insert_content(file_path, content, database=database)
            if line == -1:
                print(f"Failed to insert the function content in `{file_path}`.")

    return processed_files


def restore_list_data(data_list, positions):
    assert isinstance(data_list, list) and len(data_list) == 2
    insert_data, delete_data = data_list
    for file_path, content in insert_data.items():
        remove_inserted_content(file_path, content)
    for file_path, content in delete_data.items():
        position = positions.get(file_path, None)
        if position is not None and position != -1:
            # log_action("RESTORE", file_path, content, position)
            insert_content(file_path, content, line_number=position)


# Example entry point (can be replaced with your own data dictionary)
if __name__ == "__main__":
    data = [
        {
            "/path/to/test\\111.txt": "#include \"postgresql.h\"\n222111#define CHECKFLOATVAL do { if (isinf(val) && !(inf_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg(\"value out of range: overflow\"))); if ((val) == 0.0 && !(zero_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg(\"value out of range: underflow\"))); } while(0)",
            "/path/to/test\\222.txt": "#define pg_unreachable __assume(0)",
            "/path/to/test\\333.txt": "#define PG_FUNCTION_ARGS FunctionCallInfo fcinfo\n#define PG_GETARG_DATUM (fcinfo->arg[n])\n#define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))\n#define PG_RETURN_FLOAT8 return Float8GetDatum(x)",
        },
        {
            "/path/to/test\\111.txt": "#define pg_unreachable __assume(0)"
        }
    ]

    print("=== Starting processing ===")
    POSITIONS = process_list_data(data)

    # Restore
    restore_list_data(data, POSITIONS)
