import os
import re
import clang.cindex
from clang.cindex import Index, CursorKind, TranslationUnit
clang.cindex.Config.set_library_path("/usr/lib/llvm-14/lib")
import csv
import json

def NameLocate(name):
    grep_res=os.popen(f"grep -rnw ./duckdb-1.3.0/ -e \'\"{name}\"\' | grep -e \'*Name\'").read()
    return grep_res.split(':')[:2]
def ClassLocate(name):
    grep_res=os.popen(f"grep -rnw ./duckdb-1.3.0/ -e \'{name}\'").read()
    return grep_res.split(':')[:2]
def OpLocate(name):
    grep_res=os.popen(f"grep -rnw ./duckdb-1.3.0/ -e \'struct {name}\'").read()
    return grep_res.split(':')[:2]



def Name2Class(loc):
    file_path=loc[0]
    line_number=int(loc[1])
    # 初始化 Clang 并解析文件
    index = clang.cindex.Index.create()
    args = ['-x', 'c++', '-std=c++17']
    tu = index.parse(file_path, args=args)
    
    # 遍历 AST 查找目标行号的节点
    for node in tu.cursor.walk_preorder():
        # 确保节点有位置信息且文件匹配
        if (node.location.file is not None and 
            node.location.file.name == file_path and 
            node.location.line == line_number):
            
            parent = node
            while parent is not None:
                # 找到类/结构体定义
                if parent.kind in (clang.cindex.CursorKind.CLASS_DECL, 
                                    clang.cindex.CursorKind.STRUCT_DECL):
                    # 检查是否存在别名定义
                    alias_target = None
                    for child in parent.get_children():
                        # 查找 using ALIAS = xxx 的声明
                        if (child.kind == clang.cindex.CursorKind.TYPE_ALIAS_DECL and
                            child.spelling == "ALIAS"):
                            # 提取别名目标类型
                            tokens = list(child.get_tokens())
                            alias_target=tokens[3].spelling
                    
                    # 如果找到别名，递归解析目标类型
                    if alias_target:
                        # 定位别名目标类型的定义位置
                        alias_loc = OpLocate(alias_target)
                        if alias_loc and alias_loc[0]:
                            # 递归解析别名目标
                            return Name2Class(alias_loc)
                    
                    class_name = parent.spelling


                    # 收集静态常量字符串成员
                    static_members = {}
                    for child in parent.get_children():
                        if (child.kind == clang.cindex.CursorKind.VAR_DECL and
                            child.storage_class == clang.cindex.StorageClass.STATIC):
                            
                            # 获取初始化表达式的令牌
                            tokens = list(child.get_tokens())
                            # print([token.spelling for token in tokens])
                            if len(tokens)>=7 and tokens[3].spelling=='char' and tokens[7].spelling!='""':
                                static_members[tokens[5].spelling]=tokens[7].spelling[1:-1]
                    
                    # 在类中查找 GetFunction 或 GetFunctions
                    function_name = None
                    for child in parent.get_children():
                        if child.kind == clang.cindex.CursorKind.CXX_METHOD:
                            if child.spelling == "GetFunction":
                                function_name = "GetFunction"
                                break
                            elif child.spelling == "GetFunctions":
                                function_name = "GetFunctions"
                                break
                    # 返回结果
                    if function_name:
                        return f"{class_name}::{function_name}()",static_members
                    else:
                        return f"{class_name}::(未找到GetFunction或GetFunctions)",None
                
                parent = parent.lexical_parent
    
    return "未找到匹配的类"


def Class2Op(loc):
    file_path=loc[0]
    line_number=int(loc[1])
    # 初始化Clang索引
    index = Index.create()
    
    # 设置编译参数
    args = [
        '-x', 'c++',
        '-std=c++17',
        '-I./duckdb-1.3.0/src/include',
        '-I./duckdb-1.3.0/third_party',
        '-I./duckdb-1.3.0/extension/core_functions/include',
        '-Wno-everything'
    ]
    
    # 解析文件
    tu = index.parse(file_path, args=args, 
                     options=TranslationUnit.PARSE_INCOMPLETE | 
                             TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
    
    # 查找目标节点（函数或结构体）
    target_node = None
    for node in tu.cursor.walk_preorder():
        loc = node.location
        if loc.file and loc.file.name.endswith(file_path) and loc.line == line_number:
            # 支持多种节点类型
            if (node.kind == CursorKind.CXX_METHOD or 
                node.kind == CursorKind.FUNCTION_DECL or
                node.kind == CursorKind.CLASS_DECL or
                node.kind == CursorKind.STRUCT_DECL):
                target_node = node
                break
    
    if not target_node:
        return []
    
    # 收集所有以"Op"结尾的类名
    op_classes = set()
    
    # 根据节点类型确定遍历范围
    if target_node.kind in (CursorKind.CXX_METHOD, CursorKind.FUNCTION_DECL):
        # 函数节点：遍历整个函数体
        search_scope = target_node
    else:
        # 结构体/类节点：遍历整个结构体定义
        search_scope = target_node
    
    # 遍历目标范围内的所有节点
    for child in search_scope.walk_preorder():
        # 只处理目标文件中的节点
        if child.location.file and child.location.file.name.endswith(file_path):
            # 检查模板参数中的类型引用
            if child.kind == CursorKind.TEMPLATE_REF:
                if child.spelling.endswith("Op") or child.spelling.endswith("Operator"):
                    op_classes.add(child.spelling)
            
            # 检查类型引用
            elif child.kind == CursorKind.TYPE_REF:
                type_name = child.spelling
                # 处理限定名（如Namespace::ClassName）
                if "::" in type_name:
                    type_name = type_name.split("::")[-1]
                if type_name.endswith("Op") or type_name.endswith("Operator"):
                    op_classes.add(type_name)
    
    return sorted(list(op_classes))

def GetCode(loc):
    file_path=loc[0]
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return "".join(lines)
def test():
    name="array_negative_inner_product"
    res1=NameLocate(name=name)
    print(res1)
    res2=Name2Class(loc=res1)
    print(res2)
    res3=ClassLocate(name=res2)
    print(res3)
    res4=Class2Op(loc=res3)
    print(res4)
    res5=OpLocate(name=res4[0])
    print(res5)
    res6=Class2Op(loc=res5)
    print(res6)

JsonRes={}
target="target.csv"
miss="miss.csv"
error="error.csv"

targetcnt=0
misscnt=0
errorcnt=0

def download(row):
    global targetcnt
    global misscnt
    targetcnt+=1
    print(f"--------{targetcnt}--------")
    related_class_and_functions=[]

    def add_related_class_and_functions(res):
        temp=[res[0]]
        for r in related_class_and_functions:
            if r[0]==res[0]:
                return
        temp.append(GetCode(res))
        related_class_and_functions.append(temp)

    res0=row[0] # 函数名
    print("res0: ",res0)
    res1=NameLocate(name=res0) # struct位置
    print("res1: ",res1)
    res2,res=Name2Class(loc=res1) # getfunction名 TODO 函数别名重定位 DONE
    # TODO 获取struct对应的函数描述与函数示例 DONE
    print("res2: ",res2)
    res3=ClassLocate(name=res2) # getfunction位置
    print("res3: ",res3)
    add_related_class_and_functions(res3)
    res4=Class2Op(loc=res3) # op名称列表
    print("res4: ",res4)

    res4s=[] # 记忆化

    if len(res4)==0:
        misscnt+=1
        with open(miss, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows([row])
        raise Exception("miss: find no operator")

    def aux(names): # 递归搜索
        for res4i in names:
            if res4i in res4s:
                continue
            res4s.append(res4i)
            res5=OpLocate(name=res4i)
            print("res5: ",res5)
            add_related_class_and_functions(res5)
            res6=Class2Op(loc=res5)
            print("res6: ",res6)
            aux(res6)

    aux(res4)

    res['Code']={pair[0]:pair[1]  for pair in related_class_and_functions}

    print(res)
    print()

    JsonRes[res0]=res


def CSV2Json():
    global targetcnt
    global misscnt
    global errorcnt
    with open(miss,'r')as f:
        pass
    with open(error,'r')as f:
        pass
    dealt=[]
    with open(target,'r')as f:
        reader=csv.reader(f)
        for row in reader:
            # 重复排除
            if row in dealt:
                continue
            dealt.append(row)

            # 下载
            try:
                download(row)
            except Exception as e:
                errorcnt+=1
                print(f"Error processing row {row}: {e}")
                with open(error, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerows([row])
            print(f"error:\t {errorcnt}/{targetcnt}={errorcnt/targetcnt:.2f}")
            print(f"miss:\t {misscnt}/{targetcnt}={misscnt/targetcnt:.2f}")
            print(f"done:\t {targetcnt-errorcnt}/{targetcnt}={(targetcnt-errorcnt)/targetcnt:.2f}")

            with open('res_file.json', 'w', encoding='utf-8') as f:
                json.dump(JsonRes, f, ensure_ascii=False, indent=4)
    print(f"error:\t {errorcnt}/{targetcnt}={errorcnt/targetcnt}")
    print(f"miss:\t {misscnt}/{targetcnt}={misscnt/targetcnt}")
    print(f"done:\t {targetcnt-errorcnt}/{targetcnt}={(targetcnt-errorcnt)/targetcnt:.2f}")


# test()
CSV2Json()

# print(JsonRes)


with open('res_file.json', 'w', encoding='utf-8') as f:
    json.dump(JsonRes, f, ensure_ascii=False, indent=4)
print(f"error:\t {errorcnt}/{targetcnt}={errorcnt/targetcnt}")
print(f"miss:\t {misscnt}/{targetcnt}={misscnt/targetcnt}")
print(f"done:\t {targetcnt-errorcnt}/{targetcnt}={(targetcnt-errorcnt)/targetcnt:.2f}")