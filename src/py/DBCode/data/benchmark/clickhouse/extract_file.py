import sys
import os
import re
import json
basePath='/home/gg/extract/clickhouse/'
sys.path.append('/home/gg/understand/scitools/bin/linux64/python')
import understand
import traceback

def code_dict_add(loc, code_dict):
    file_path=loc.split(':')[0]
    if file_path not in code_dict:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines=f.readlines()
            file_content="".join(lines)
        code_dict[file_path] = file_content

def get_struct_name_value(db, struct_name):
    """
    通过结构体名字查询该结构体，并获取静态成员 `name` 的值
    :param db: Understand 数据库对象
    :param struct_name: 结构体名字（例如 Log10Name）
    :return: name 的值 (如果找到) 或 None
    """
    # 查询结构体
    for struct in db.ents("function, struct"):
        if struct.name() == struct_name:
            print(f"Found struct: {struct_name}")
            # 查找静态成员 `name`
            for ref in struct.refs("Init"):
                var = ref.ent()
                if var.name() == "name":
                    return var.value()[1:-1]  # 去掉引号
    return None

def NameLocate(name):
    grep_res=os.popen(f"grep -rnw ./ClickHouse-25.7.4.11-stable -e \'{name}\' | grep -e \'using\'").read()
    if grep_res=='':
        return None
    return ":".join(grep_res.split(':')[:2])

def parse_register_function(db, func_name):
    """
    获取函数中 documentation 变量初值，以及 factory.registerFunction 的模板参数
    :param db: Understand 数据库对象
    :param func_name: 要解析的函数名
    :return: (documentation_dict, factory_param) 或 (None, None)
    """
    # 遍历函数实体
    for func in db.ents("function"):
        if func.longname() != func_name:
            continue

        documentation_dict = {}
        factory_param = []

        # 遍历函数内的变量和调用引用
        for ref in func.refs("Set"):
            var = ref.ent()
            if var.name()[0].isupper():
                continue
            if var.name() == "documentation":
                continue
            file_path = ref.file().longname()
            line_no = ref.line()
            # print(var.name(), file_path, line_no)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines=f.readlines()
                    line=lines[line_no-1].strip()
                    while ";" not in line and line_no < len(lines):
                        line_no += 1
                        line += "\n" + lines[line_no-1].strip()
                    # print(line)
                    documentation_dict[var.name()] = line.split('=')[1].strip().strip('";')
            except Exception as e:
                print(f"Error reading file {file_path} at line {line_no}: {e}")

        for ref in func.refs("Use"):
            ent=ref.ent()
            if ent.name().startswith("Function") and ent.name() != "FunctionFactory":
                factory_param.append(ent.name())


        return documentation_dict, factory_param

    return None, None


import re

def extract_content(s):
    # 查找第一个 '<' 和最后一个 '>'
    start = s.find('<')
    end = s.rfind('>')

    # 如果找到了 '<' 和 '>'，则提取其中的内容
    if start != -1 and end != -1 and start < end:
        return s[start+1:end]
    return ""  # 如果没有找到符合条件的括号，返回空字符串

def simple_extract_impl(loc, code_dict):
    if loc is None:
        return None
    file_path = loc.split(':')[0]
    line_no = int(loc.split(':')[1])
    """
    给定 using 行的位置，提取第一个模板参数 (Impl 类)
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    line = lines[line_no - 1].strip()

    # code_dict[loc] = line
    code_dict_add(loc, code_dict)

    # 匹配 using FunctionXxx = SomeTemplate<...>;
    m = re.search(r'<(.*)>', line)
    if not m:
        return None

    # 提取尖括号里的内容，并按逗号分隔
    params = [p.strip() for p in m.group(1).split(",")]

    if params:
        if params[0].endswith("Impl"):
            return params[0]   # 第一个就是 Impl 类，比如 GCDImpl
    return None

import re

def vectorized_extract_impl(loc, code_dict):
    if loc is None:
        return None
    file_path = loc.split(':')[0]
    line_no = int(loc.split(':')[1])

    """
    给定 using 行的位置，提取 UnaryFunctionVectorized 的两个模板参数
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    line = lines[line_no - 1].strip()
    # code_dict[loc] = line
    code_dict_add(loc, code_dict)

    # # 匹配 using FunctionXxx = SomeTemplate<...>;
    # m = re.search(r'<(.*)>', line)
    # if not m:
    #     return None
    # print(m)
    # # 提取尖括号里的内容
    # inside = m.group(1)

    # print(line)
    inside=extract_content(line)
    # print(inside)
    if inside:
        return inside
    return None


def get_class_source(db, class_name, code_dict):
    """
    从 Understand 数据库中提取类/结构体源码
    :param db: Understand 数据库对象
    :param class_name: 类/结构体名称（例如 GCDImpl）
    :return: 源代码字符串 或 None
    """
    for ent in db.ents("class,struct"):
        if ent.name() == class_name:
            ref = ent.ref("Definein")
            if not ref:
                continue
            file = ref.file().longname()
            start_line = ref.line()

            # 读取源文件
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # 从定义行开始，找到第一个 {
            code_lines = []
            brace_count = 0
            in_class = False
            for i in range(start_line - 1, len(lines)):
                line = lines[i]
                code_lines.append(line)

                if "{" in line:
                    brace_count += line.count("{")
                    in_class = True
                if "}" in line and in_class:
                    brace_count -= line.count("}")
                    if brace_count == 0:
                        # 找到类结尾
                        break

            # code_dict[f"./{os.path.relpath(file, basePath)}:{start_line}"] = "".join(code_lines)
            code_dict_add(f"./{os.path.relpath(file, basePath)}:{start_line}", code_dict)

import understand

def get_func_code(db, func_name, code_dict):
    """
    通过函数名获取函数源码
    :param db: understand.Database 对象
    :param func_name: 函数名（完全匹配）
    :return: 函数源码字符串，找不到返回 None
    """
    for func in db.ents("function"):
        if func.longname() == func_name:
            # 找定义位置
            ref = func.ref("definein")

            start_line = ref.line()
            file = ref.file()
            file_path = file.longname()  # 获取完整路径

            # 用 metric 获取函数长度
            metrics = func.metric(["CountLine"])
            line_count = metrics.get("CountLine", 0)
            if not line_count:
                return None

            end_line = start_line + line_count - 1

            # 读取源码
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            code = "".join(lines[start_line-1:end_line])
            # code_dict[f"./{os.path.relpath(file_path, basePath)}:{start_line}"] = code
            code_dict_add(f"./{os.path.relpath(file_path, basePath)}:{start_line}", code_dict)
            return code

    return None

def check_ifunction(db, func_name, code_dict, basePath="."):
    for func in db.ents("class, struct"):
        if func.name() == func_name:
            # 遍历类的 Define 引用
            found_def = False
            for ref in func.refs("Define"):
                found_def = True
                file_ent = ref.file()
                file_path = file_ent.longname()
                
                # 遍历类的所有成员函数
                found_impl = False
                for member in func.ents("Define", "function"):
                    if member.name().endswith("Impl"):
                        found_impl = True
                        # 获取函数起止行（用 metrics）
                        ref = member.ref("Definein")
                        
                        start_line = ref.line()
                        
                        metrics = member.metric(["CountLine"])
                        line_count = metrics.get("CountLine", 0)
                        end_line = start_line + line_count - 1

                        if start_line and end_line:
                            # 读取源码
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                            code = "".join(lines[start_line-1:end_line])

                            # 保存到字典
                            rel_path = os.path.relpath(file_path, basePath)
                            # code_dict[f"./{rel_path}:{start_line}"] = code
                            code_dict_add(f"./{rel_path}:{start_line}", code_dict)
                if not found_impl:
                    get_class_source(db, func_name, code_dict)
            if found_def:
                return True
    return False

db=understand.open(f'{basePath}ClickHouse-25.7.4.11-stable/clickhouse.udb')


JsonRes = {}
done_cnt=0
all_cnt=0

for func in db.ents("function"):
    name = func.longname()
    try:
        if "DB::registerFunction" in name:
            # print(f"Processing function: {name}")
            res, function_names = parse_register_function(db, name)
            if "syntax" in res or "doc_syntax" in res: #单个函数
                # continue
                if "syntax" in res:
                    syn = "syntax"
                else:
                    syn = "doc_syntax"

                print(f"Processing function: {name}")

                key = res[syn].split('(')[0]
                function_name = function_names[0]
                code_dict = {}

                if check_ifunction(db, function_name, code_dict):
                    done_cnt+=1
                    all_cnt+=1
                    res["Code"] = code_dict
                    res["Count"] = done_cnt
                    JsonRes[key] = res
                else:
                    loc = NameLocate(function_name)
                    # print(loc)
                    class_name = simple_extract_impl(loc, code_dict)
                    # print(class_name)
                    get_class_source(db, class_name, code_dict)
                    # print(code_text)
                    res["Code"] = code_dict
                    done_cnt+=1
                    all_cnt+=1
                    res["Count"] = done_cnt
                    JsonRes[key] = res


            elif not res:  # 向量函数
                # continue
                print(f"Processing vectorized function: {name}")

                function_name = function_names[0]
                code_dict = {}
                loc = NameLocate(function_name)
                # print(loc)
                class_name = vectorized_extract_impl(loc, code_dict)
                print(class_name)
                if not class_name:
                    continue
                if "Vectorized" in class_name:
                    # print(class_name)
                    get_class_source(db, class_name.split('<')[0], code_dict)
                    get_func_code(db, class_name.split('<')[1].split(',')[1].strip('>'), code_dict)
                    # print(code_text)
                    key = get_struct_name_value(db, class_name.split('<')[1].split(',')[0].strip('>'))
                    if not key:
                        key = class_name.split('<')[1].split(',')[0].strip('>')
                    res["Code"] = code_dict
                    done_cnt += 1
                    all_cnt+=1
                    res["Count"] = done_cnt
                    JsonRes[key] = res
                else:
                    continue

            else: #复合函数
                print(f"Processing complex function: {name}")
                print(function_names)
                for syn in res:
                    if syn.startswith("syntax"):
                        end=syn[6:]
                        sub_res={k:v for k,v in res.items() if k.endswith(end)}
                        key=res[syn].split('(')[0]
                        print(f"Key: {key}")
                        code_dict = {}
                        for function_name in function_names:
                            if key.lower() in function_name.lower():
                                print(f"  Processing sub-function: {function_name}")
                                if not check_ifunction(db, function_name, code_dict):
                                    print(f"  Not an IFuntion: {function_name}")
                                    loc = NameLocate(function_name)
                                    print(loc)
                                    class_name = simple_extract_impl(loc, code_dict)
                                    # print(class_name)
                                    get_class_source(db, class_name, code_dict)
                                    # print(code_text)

                        sub_res["Code"] = code_dict
                        done_cnt += 1
                        all_cnt+=1
                        sub_res["Count"] = done_cnt
                        JsonRes[key] = sub_res

            with open("res_file.json", "w", encoding="utf-8") as f:
                json.dump(JsonRes, f, ensure_ascii=False, indent=4)

            print("--------------------------------------------------")
            print(f"Processed {done_cnt} functions out of {all_cnt}.")
            print("--------------------------------------------------")

    except Exception as e:
        all_cnt+=1
        print(f"Error processing function {name}: {e}")
        tb = traceback.extract_tb(e.__traceback__)
        for filename, lineno, func, text in tb:
            print(f"文件: {filename}, 行: {lineno}, 函数: {func}, 代码: {text}")

with open("res_file.json", "w", encoding="utf-8") as f:
    json.dump(JsonRes, f, ensure_ascii=False, indent=4)

print("--------------------------------------------------")
print(f"Processed {done_cnt} functions out of {all_cnt}.")
print("--------------------------------------------------")

# function_name="FunctionGCD"
# file_path, line_no, def_text = get_function_def(db, function_name)
# print(file_path, line_no, def_text)
