import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from simhash import Simhash


def install_package(package):
    """Install the specified library"""
    subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)


def uninstall_package(package):
    """Uninstall the specified library"""
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", package], check=True)


def build_parent_map(function_list):
    """
    Build parent node mapping dictionary, storing the parent node list corresponding to each child node

    Parameters:
    function_list (list): List containing all nodes and their child nodes

    Returns:
    dict: Dictionary of parent node lists corresponding to each child node
    """
    parent_map = {}

    for function in function_list:
        for function_name, nodes_info in function.items():
            for node_info in nodes_info:
                # Get child nodes of current node
                # print(json.dumps(node_info, indent=4, ensure_ascii=False))
                if 'Child Nodes' in node_info:
                    for child_value, child_info in node_info['Child Nodes'].items():
                        # If this child node is already in the dictionary, add current parent node to parent node list
                        if child_value not in parent_map:
                            parent_map[child_value] = []
                        parent_map[child_value].append(node_info["Node Name"])
                        # Recursively handle parent-child node relationships
                        # parent_map.update(build_parent_map([{child_value: [child_info]}]))

    return parent_map


def get_parent_nodes(parent_map, target_values, parent_count):
    """
    Get parent node information for target nodes. If direct parent nodes are insufficient, continue searching for parent nodes of parent nodes until reaching the specified count or unable to search further.

    Parameters:
        parent_map (dict): Parent node relationship dictionary, each child node corresponds to a parent node list
        target_value (str): Target node value
        parent_count (int): Number of parent nodes to return

    Returns:
        list: Parent node list (at most parent_count parent nodes)
    """
    # Unify input processing as list
    targets = [target_values] if isinstance(target_values, str) else target_values.copy()

    parent_chain = []
    visited = set(t for t in targets)  # Initialize visited set

    # Initialize queue (including level information)
    queue = deque([(t, 0) for t in targets])  # (node, depth)

    # Breadth-first search (level traversal)
    while queue and len(parent_chain) < parent_count:
        current_node, current_depth = queue.popleft()

        # Get direct parent nodes of current node
        parents = parent_map.get(current_node, [])

        for parent in parents:
            if parent not in visited:
                visited.add(parent)
                parent_chain.append(parent)
                if len(parent_chain) >= parent_count:
                    break
                queue.append((parent, current_depth + 1))

    return parent_chain[:parent_count]


def build_line_map(function_list):
    """
    Build a dictionary based on line numbers, where keys are line numbers and values are corresponding nodes

    Parameters:
    function_list (list): List containing all nodes and their child nodes

    Returns:
    dict: Dictionary with line numbers as keys and nodes as values
    """
    line_map = {}

    # Iterate through nodes
    for function in function_list:
        for function_name, nodes_info in function.items():
            for node_info in nodes_info:
                # Get current node position (start line and end line)
                if 'Position' in node_info:
                    start_line = node_info['Position'].get('Start Line')
                    end_line = node_info['Position'].get('End Line')

                    # If node has valid line number information, add this node to line number mapping dictionary
                    if start_line is not None and end_line is not None:
                        for line in range(start_line, end_line + 1):
                            line_map[line] = node_info["Node Name"]

    return line_map


def get_nodes_by_line(line_map, target_lines):
    """
    Get all node information for specified line number list

    Parameters:
    line_map (dict): Dictionary with line numbers as keys and nodes as values
    target_lines (list): Target line number list

    Returns:
    list: List of target node line numbers and descriptions, first item is line number, second item is id
    """

    target_nodes = []
    # has_added = set()
    sorted_lines = line_map.keys()
    for target_line in target_lines:
        if target_line in line_map:     # Found target line number
            # if target_line not in has_added:
            #     has_added.add(target_line)
            target_nodes.append([target_line, line_map[target_line]])
        # else:       # Cannot find target line number, can only find nearest node
        #     closest_line = None
        #     for line in sorted_lines:
        #         if line < target_line:
        #             closest_line = line
        #         else:
        #             break
        #
        #     # if closest_line is not None and closest_line not in has_added:
        #     #     has_added.add(closest_line)
        #     if closest_line is not None:
        #         target_nodes.append([closest_line, line_map[closest_line]])
        #     elif closest_line is None:
        #         target_nodes.append([None, None])

    return target_nodes


def get_nodes_by_lines(line_map, target_lines):
    """
    Get all node information for specified line numbers

    Parameters:
    line_map (dict): Dictionary with line numbers as keys and nodes as values
    target_line (list): Target line number list

    Returns:
    list: Node list for target line numbers
    """
    result = []
    for target_line in target_lines:
        if target_line in line_map:
            result.append(line_map.get(target_line))

    return result


def sort_nodes_by_start_line(node_dict):
    """
    根据节点的“起始行”升序排序字典项，如果“起始行”为 None，则视为无穷大，排在后面

    参数:
      node_dict (dict): 每个项的结构类似如下：
          {
              "节点标识": {
                  "内容": "...",
                  "类型": "...",
                  "位置": {
                      "起始行": int 或 None,
                      "结束行": ...,
                      "起始列": ...,
                      "结束列": ...
                  }
              },
              ...
          }

    返回:
      dict: 一个按照“起始行”升序排列的新字典
    """
    sorted_items = sorted(
        node_dict.items(),
        key=lambda item: (item[1].get("位置", {}).get("起始行")
                          if item[1].get("位置", {}).get("起始行") is not None else float('inf'))
    )

    return dict(sorted_items)


def get_lines_from_file(file_path, line_numbers):
    """
    从指定文件中提取指定行号的内容，保留整行内容（包括最开头的空格）

    参数:
    file_path (str): 文件路径
    line_numbers (list): 行号列表，行号从 1 开始

    返回:
    list: 包含指定行号内容的列表
    """
    try:
        # 打开文件并读取所有行
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # 提取指定行号的内容
        result = []
        for line_number in line_numbers:
            # 行号从 1 开始，文件索引从 0 开始，因此需要减 1
            if 1 <= line_number <= len(lines):
                result.append(lines[line_number - 1])  # 保留整行内容，包括空格和换行符
            else:
                print(f"行号 {line_number} 超出文件范围，跳过")

        return result

    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查路径是否正确")
        return []
    except Exception as e:
        print(f"读取文件时发生错误：{e}")
        return []


def check_lines(target_lines, file_path):
    """
        判断用户输入的 target_line 是否超出最大限制，超出的话则设为最大限制

        参数:
        target_line (int): 目标行号
        file_path (str): 文件路径

        返回:
        list: 包含指定行号内容的列表
        """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        max_line = len(lines)

        return [min(line, max_line) for line in target_lines]

    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查路径是否正确")
        return []
    except Exception as e:
        print(f"读取文件时发生错误：{e}")
        return []


def get_features(content):
    """
        获取输入内容的特征

        参数:
        content (str): 输入内容

        返回:
        list: 包含输入内容的特征的列表
    """
    # 移除空格并转小写
    content = re.sub(r'\s+', '', content.lower())
    # 按3-gram生成特征
    length = 3
    return [content[i:i + length] for i in range(max(len(content) - length + 1, 1))]


def hash_content(content):
    """
        返回内容的SimHash值（64位指纹）

        参数:
        content (str): 哈希内容

        返回:
        Simhash: 哈希后的结果
    """
    features = get_features(content)
    return Simhash(features)


def build_dependency_tree(file, dependency_tree, index, epoch, check=False, lines=None):
    """
        构建依赖关系树

        参数:
        file (understand.Ent): 需要分析的文件或文件中部分内容
        dependency_tree (list): 已构建的依赖关系树
        index (SimhashIndex): 判断哈希值相似度
        batch (int): 剩余递归次数
    """
    if epoch <= 0:
        return

    dep_dict = file.depends()

    for key, deps in dep_dict.items():
        for dep in deps:
            if check and dep.line() not in lines:
                continue
            dep_ent = dep.ent()
            dep_content = dep_ent.contents()
            # print(str(key), dep_ent.name(), dep.line(), dep.kindname(), dep_content)
            # print("---------------------------")
            # dep_content = str(key)

            # 生成内容指纹
            simhash = hash_content(dep_content)
            if index.get_near_dups(simhash):
                continue
            index.add(str(id(dep_ent)), simhash)

            build_dependency_tree(dep_ent, dependency_tree, index, epoch - 1)
            dependency_tree.append(dep_content)


def build_commit_dependency_tree(file, dependency_tree, index, epoch, check=False, lines=None):
    """
        构建依赖关系树

        参数:
        file (understand.Ent): 需要分析的文件或文件中部分内容
        dependency_tree (list): 已构建的依赖关系树
        index (SimhashIndex): 判断哈希值相似度
        batch (int): 剩余递归次数
    """
    if epoch <= 0:
        return

    dep_dict = file.depends()

    for key, deps in dep_dict.items():
        for dep in deps:
            if check and dep.line() not in lines:
                continue
            dep_str = str(dep)
            dep_ent = dep.ent()
            dep_ent_name = dep_ent.name()
            dep_scope_name = dep.scope().name()
            dep_line = dep.line()
            dep_ent_kind_name = dep_ent.kindname()

            build_commit_dependency_tree(dep_ent, dependency_tree, index, epoch - 1)
            dependency_tree.append(
                (file.longname(), key.longname(), dep_str, dep_ent_name, dep_scope_name, dep_line, dep_ent_kind_name))


def get_control_and_data_dependency(project, analyze_file, target_lines, parent_count):
    """
        获取指定语句的控制和数据依赖的前文

        参数:
        project (understand.udb): 需要分析的 understand 项目
        analyze_file (str): 需要分析的文件的路径
        target_line (int): 指定语句的行号
        parent_count (int): 指定控制依赖的查找次数

        返回:
        text: 找到的相关前文
    """
    control_flow = project.get_control_flow()  # 获取控制流图
    # print(json.dumps(control_flow, indent=4, ensure_ascii=False))

    function_list = control_flow[analyze_file]  # 获取某个文件的控制流图
    # print(json.dumps(function_list, indent=4, ensure_ascii=False))

    parent_map = build_parent_map(function_list)  # 获取父节点图
    # print(json.dumps(parent_map, indent=4, ensure_ascii=False))

    line_map = build_line_map(function_list)  # 获取行数与节点的对应关系
    # print(json.dumps(line_map, indent=4, ensure_ascii=False))

    parent_nodes = []  # 父节点列表
    # middle_rows = set()  # 目标行与实际获取行之间的行号
    # middle_contents = []  # 目标行与实际获取行之间的内容

    target_lines = check_lines(target_lines, analyze_file)  # 确保 target_line 不超出范围

    nodes_nearest = get_nodes_by_line(line_map, target_lines)  # 获取指定行的节点: [行号: 内容]
    if len(nodes_nearest) != 0:
        nodes_nearest_line = []
        nodes_nearest_id = []
        for node in nodes_nearest:
            if node[0] is None:
                continue
            nodes_nearest_line.append(node[0])
            nodes_nearest_id.append(node[1])

        parent_nodes = get_parent_nodes(parent_map, nodes_nearest_id, parent_count)  # 获取该节点的指定数量的父节点
        for node in nodes_nearest_id:  # 加上它本身的节点
            parent_nodes.append(node)

        # for i in range(len(target_lines)):
        #     target_line = target_lines[i]
        #     node_nearest_line = nodes_nearest[i][0]
        #     if target_line != node_nearest_line:  # 如果获取到的节点并不是指定行的节点，说明指定行不是一个节点，所以只能得到最近的一个节点
        #         middle_rows.update(range(node_nearest_line+1, target_line))
        # middle_rows = list(middle_rows)
        # middle_contents = get_lines_from_file(analyze_file, middle_rows)

    # print(json.dumps(parent_nodes, indent=4, ensure_ascii=False))
    # print(json.dumps(middle_contents, indent=4, ensure_ascii=False))

    data_control_flow_lines = project.get_data_control_flow(analyze_file, target_lines)  # 获取数据控制图
    data_control_flow_nodes = get_nodes_by_lines(line_map, data_control_flow_lines)
    # print(json.dumps(data_control_flow_nodes, indent=4, ensure_ascii=False))

    parent_and_data_nodes = list(set(parent_nodes) | set(data_control_flow_nodes))
    # parent_and_data_nodes = list(set(data_control_flow_nodes))
    # print(json.dumps(parent_and_data_nodes, indent=4, ensure_ascii=False))

    parent_information = {}
    lines = []
    for node_name in parent_and_data_nodes:
        node_detail = next(
            (node for function in function_list for nodes in function.values() for node in nodes if node['节点名'] == node_name),
            None
        )
        if node_detail is not None:
            parent_information[node_name] = {
                "内容": node_detail["内容"],
                "类型": node_detail["类型"],
                "位置": node_detail["位置"]
            }
            lines.append(node_detail["位置"]["起始行"])
    # print(json.dumps(parent_information, indent=4, ensure_ascii=False))
    parent_information = sort_nodes_by_start_line(parent_information)
    # print(json.dumps(parent_information, indent=4, ensure_ascii=False))
    text = ""
    # print(json.dumps(parent_information, indent=4, ensure_ascii=False))
    for value in parent_information.values():
        text += value["内容"] + "\n"
    # for content in middle_contents:
    #     text += content

    return lines, text


def get_dependency(project, analyze_file, target_lines):
    """
        获取指定语句的数据依赖和跨文件依赖的前文

        参数:
        project (understand.udb): 需要分析的 understand 项目
        analyze_file (str): 需要分析的文件的路径
        target_line (int): 指定语句的行号

        返回:
        text: 找到的相关前文
    """
    control_flow = project.get_control_flow(analyze_file)  # 获取控制流图
    # print(json.dumps(control_flow, indent=4, ensure_ascii=False))

    function_list = control_flow[analyze_file]  # 获取某个文件的控制流图
    # print(json.dumps(function_list, indent=4, ensure_ascii=False))

    # parent_map = build_parent_map(function_list)  # 获取父节点图
    # print(json.dumps(parent_map, indent=4, ensure_ascii=False))

    line_map = build_line_map(function_list)  # 获取行数与节点的对应关系
    # print(json.dumps(line_map, indent=4, ensure_ascii=False))

    target_lines = check_lines(target_lines, analyze_file)  # 确保 target_line 不超出范围

    nodes_nearest = get_nodes_by_line(line_map, target_lines)  # 获取指定行的节点: [行号: 内容]
    function_nodes = []
    for node in nodes_nearest:
        if node[0] is None:
            continue
        function_nodes.append(node[1])

    data_control_flow_contents = project.get_data_control_content(analyze_file, target_lines)  # 获取数据控制图

    # parent_and_data_nodes = list(set(function_nodes))

    # parent_information = {}
    # lines = []
    # for node_name in parent_and_data_nodes:
    #     node_detail = next(
    #         (node for function in function_list for nodes in function.values() for node in nodes if node['节点名'] == node_name),
    #         None
    #     )
    #     if node_detail is not None:
    #         parent_information[node_name] = {
    #             "内容": node_detail["内容"],
    #             "类型": node_detail["类型"],
    #             "位置": node_detail["位置"]
    #         }
    #         lines.append(node_detail["位置"]["起始行"])
    # parent_information = sort_nodes_by_start_line(parent_information)
    text = ""
    # for value in parent_information.values():
    #     text += value["内容"] + "\n"
    for content in data_control_flow_contents:
        text += content + "\n"

    # return lines, text
    return text




















