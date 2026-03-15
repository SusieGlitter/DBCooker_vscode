import sys
import os
import re
import json
basePath='/home/gg/extract/sqlite/'
sys.path.append('/home/gg/understand/scitools/bin/linux64/python')
import understand
import traceback

db = understand.open(basePath+'sqlite-src-3500400/sqlite.udb')

def get_xFunc(func_name):
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
            code_dict = {f'{file_path}:{start_line}': code}
            return {"impl_function": func_name, "code": code_dict}

    return None

get_define_pos_memorization = {}
def get_define_pos(define_str):
    if define_str in get_define_pos_memorization:
        return get_define_pos_memorization[define_str]
    result = os.popen(f"grep -rn {basePath}sqlite-src-3500400/ -e \'#define {define_str}\'").read().split('\n')[0]
    # return result.split(define_str, 1)[1]
    ret={}
    pre_zName = result.split("zName",1)[0]
    zName_pos = pre_zName.count(',')
    ret['zName'] = zName_pos
    pre_xFunc = result.split("xFunc",1)[0]
    xFunc_pos = pre_xFunc.count(',')
    ret['xFunc'] = xFunc_pos
    get_define_pos_memorization[define_str] = ret
    return ret

def decode_define(s):
    # PURE_DATE(julianday,        -1, 0, 0, juliandayFunc ),
    # 先取出PURE_DATE，再找到define，确定zName和xFunc位置，再返回zName和xFunc

    define_str = s.split('(')[0].strip()
    pos_dict = get_define_pos(define_str)
    ret={}
    for k,v in pos_dict.items():
        ret[k] = s.split('(',1)[1].rsplit(')',1)[0].split(',')[v].strip()
    return ret

def get_register_function_mapping_unit(s):
    # /home/gg/extract/sqlite/sqlite-src-3500400/src/window.c:611:  static FuncDef aWindowFuncs[] = {
    file_path = s.split(':',2)[0]
    line_number = int(s.split(':',2)[1])
    ret = {}
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        lines = lines[line_number:]
        for i, line in enumerate(lines):
            line = line.strip() + '\n'
            if '};' in line:
                break
            if '(' in line and line.endswith('),\n'):
                print(line)
                decode_define_res = decode_define(line)
                ret[decode_define_res['zName']] = get_xFunc(decode_define_res['xFunc'])
            elif '(' in line and line.endswith(',\n'):
                j = i
                while j + 1 < len(lines) and (lines[j].strip().endswith('),') or lines[j].strip().endswith(')')) is False:
                    j += 1
                    line_next = lines[j]
                    line = line.strip() + line_next.strip() + '\n'
                print(line)
                decode_define_res = decode_define(line)
                ret[decode_define_res['zName']] = get_xFunc(decode_define_res['xFunc'])
    return ret
                
    

def get_register_function_mapping(path):
    cnt = 0
    result = os.popen(f"grep -rn {path} -e \' FuncDef \' | grep -e \'\\[\\]\' | grep -e \'=\'").read().split('\n')[:-1]
    print(result)
    ret = {}
    for r in result:
        category = r.split('FuncDef ',1)[1].split('[]',1)[0].strip()
        ret_unit = get_register_function_mapping_unit(r)
        # ret[key] = ret_unit
        for k,v in ret_unit.items():
            cnt+=1
            if v is None:
                ret[k] = {
                    'category': category,
                    'impl_function': None,
                    'code': {},
                    'error': 'no xFunc'
                }
                continue
            ret[k] = {
                'category': category,
                'impl_function': v['impl_function'],
                'code': v['code']
            }
    print(f"total {cnt} functions")
    return ret

if __name__ == "__main__":
    # print(get_define_pos('PURE_DATE'))
    # print(decode_define('PURE_DATE(julianday,        -1, 0, 0, juliandayFunc ),'))
    # print(get_register_function_mapping_unit('/home/gg/extract/sqlite/sqlite-src-3500400/src/window.c:611:  static FuncDef aWindowFuncs[] = {'))
    ret = get_register_function_mapping(basePath+'sqlite-src-3500400/')
    with open(basePath+ 'res.json', 'w') as f:
        json.dump(ret, f, indent=4)