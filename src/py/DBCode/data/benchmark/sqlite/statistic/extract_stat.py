import sys
import os
import re
import json
basePath='/home/gg/extract/sqlite/'
sys.path.append('/home/gg/understand/scitools/bin/linux64/python')
import understand
import traceback
import subprocess
import requests
import time
import zipfile
import shutil

# db = understand.open(basePath+'sqlite-src-3500400/sqlite.udb')

def get_xFunc(func_name, db):
    return None

get_define_pos_memorization = {}
def get_define_pos(define_str, path):
    if define_str in get_define_pos_memorization:
        return get_define_pos_memorization[define_str]
    result = os.popen(f"grep --binary-files=without-match -rn {path} -e \'#define {define_str}\'").read().split('\n')[0]
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

def decode_define(s, path):
    # PURE_DATE(julianday,        -1, 0, 0, juliandayFunc ),
    # 先取出PURE_DATE，再找到define，确定zName和xFunc位置，再返回zName和xFunc

    define_str = s.split('(')[0].strip()
    pos_dict = get_define_pos(define_str, path)
    ret={}
    args = s.split('(',1)[1].rsplit(')',1)[0].split(',')
    for k,v in pos_dict.items():
        ret[k] = args[min(v, len(args)-1)].strip()
    return ret

def get_register_function_mapping_unit(s, path, db):
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
                # print(line)
                decode_define_res = decode_define(line, path)
                ret[decode_define_res['zName']] = get_xFunc(decode_define_res['xFunc'], db)
            elif '(' in line and line.endswith(',\n'):
                j = i
                while j + 1 < len(lines) and (lines[j].strip().endswith('),') or lines[j].strip().endswith(')')) is False:
                    j += 1
                    line_next = lines[j]
                    line = line.strip() + line_next.strip() + '\n'
                # print(line)
                decode_define_res = decode_define(line, path)
                ret[decode_define_res['zName']] = get_xFunc(decode_define_res['xFunc'], db)
    return ret
                

def get_register_function_mapping(path, db):
    print(f'Dealing path: {path}')
    cnt = 0
    result = os.popen(f"grep --binary-files=without-match -rn {path} -e \' FuncDef \' | grep -e \'\\[\\]\' | grep -e \'=\'").read().split('\n')[:-1]
    # print(result)
    ret = {}
    for r in result:
        category = r.split('FuncDef ',1)[1].split('[]',1)[0].strip()
        print(f'\r\033[KDealing category: {category}', end='', flush=True)
        ret_unit = get_register_function_mapping_unit(r, path, db)
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
        print(f'\r\033[K', end='', flush=True)
    # print(f"total {cnt} functions")
    return ret, cnt

def understand_create(name,path):
    if os.path.exists(os.path.join("./", name + ".udb")):
        return
    print(f"understanding {name}...", end='', flush=True)
    kwargs = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
    subprocess.run(['und', 'create', '-db', name, "-languages", "c++"], **kwargs)
    subprocess.run(['und', '-db', name, 'add', path], **kwargs)
    subprocess.run(['und', '-db', name, 'analyze'], **kwargs)
    # subprocess.run(['und', 'create', '-db', name, "-languages", "c++"])
    # subprocess.run(['und', '-db', name, 'add', path])
    # subprocess.run(['und', '-db', name, 'analyze'])
    print("\r\033[K", end='', flush=True)

stat_memorization = {}
def stat(path):
    name = path.split('/')[-1]
    understand_create(name, path)
    db = understand.open(os.path.join("./", name + ".udb"))
    ret, cnt = get_register_function_mapping(path, db)
    print(f"{cnt} functions")

    stat_memorization[name] = {
        "cnt": cnt
    }
    with open(f"res_cnt.json", "w", encoding="utf-8") as f:
        json.dump(stat_memorization, f, ensure_ascii=False, indent=4, sort_keys=True)


def stat_all():
    for entry in os.listdir('.'):
        if os.path.isdir(entry) and entry.startswith('sqlite'):
            print(f"Processing directory: {entry}")
            print(f"Current working directory: {os.path.abspath(entry)}")
            stat(os.path.abspath(entry))

if __name__ == "__main__":
    stat_all()