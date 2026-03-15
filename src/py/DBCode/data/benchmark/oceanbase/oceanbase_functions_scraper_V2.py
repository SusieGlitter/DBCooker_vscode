# -*- coding: utf-8 -*-
"""
Extract OceanBase V4.3.5 Reference (cut) → function JSON.
- tree 使用 Syntax 小节的内容
- description: Purpose/Description 的简短摘要
- detail: 包含描述 + 语法 + 示例
- example: 保留 Example 小节的全部内容（SQL + 输出）
- source: 固定为 "OceanBase-Database-V4.3.5-Reference.pdf"
"""

import re
import json
from pdfminer.high_level import extract_text

# ---- CONFIG ----
PDF_PATH = r"OceanBase-Database-V4.3.5-Reference-cut.pdf"
OUT_JSON = r"oceanbase_v435_functions.json"
SOURCE_TAG = "OceanBase-Database-V4.3.5-Reference.pdf"
# ----------------

LABELS = {"syntax", "purpose", "description", "examples", "parameters", "note", "notes"}
CATEGORY_MAP = {
    "string": ["string functions", "character functions"],
    "math": ["mathematical functions", "numeric functions"],
    "date-time": ["date functions", "time functions", "datetime functions"],
    "aggregate": ["aggregate functions", "group functions"],
    "conversion": ["conversion functions", "cast functions"],
}

def load_lines(pdf_path):
    """读取 PDF 并切分成行，清理掉页眉页脚噪声"""
    txt = extract_text(pdf_path).replace("\r", "")
    lines = [ln.strip() for ln in txt.split("\n")]
    cleaned = []
    for ln in lines:
        if not ln:
            cleaned.append("")
            continue
        if ln.startswith("ReferenceOceanBase Database"):
            continue
        cleaned.append(ln)
    return cleaned

def is_func_heading(lines, i):
    """判断某一行是否是函数标题"""
    head = lines[i].strip()
    if not re.fullmatch(r"[A-Z0-9_]{2,64}", head):
        return False
    # 检查后续几行是否有 Syntax 标签
    for j in range(i+1, min(i+4, len(lines))):
        if lines[j].strip().lower() == "syntax":
            return True
    return False

def collect_blocks(lines):
    """收集每个函数块的起止行号"""
    starts = [i for i in range(len(lines)) if is_func_heading(lines, i)]
    for k, si in enumerate(starts):
        ei = starts[k + 1] if k + 1 < len(starts) else len(lines)
        yield si, ei

def find_first_idx(block, label):
    """在函数块中找到某标签的首行索引"""
    lab = label.lower()
    for idx, ln in enumerate(block):
        if ln.strip().lower() == lab:
            return idx
    return None

def slice_until_label(block, start, stop_labels):
    """从 start 开始收集文本，直到遇到 stop_labels"""
    end = len(block)
    for idx in range(start, len(block)):
        if block[idx].strip().lower() in stop_labels:
            end = idx
            break
    seg = [x for x in block[start:end] if x.strip()]
    return " ".join(seg).strip()

def gather_example_block(block, start_idx):
    """收集 Example 小节的完整内容"""
    end = len(block)
    for idx in range(start_idx+1, len(block)):
        if block[idx].strip().lower() in LABELS:
            end = idx
            break
    return [ln for ln in block[start_idx+1:end] if ln.strip()]

def guess_category_from_chapter(chapter_title: str):
    """根据章节名判断分类"""
    if not chapter_title:
        return None
    title = chapter_title.lower()
    for cat, keys in CATEGORY_MAP.items():
        if any(k in title for k in keys):
            return cat
    return None

def classify_function(name, description, syntax_txt, chapter_title):
    """两级分类：先章节，后关键词"""
    # 1. 优先章节
    cat = guess_category_from_chapter(chapter_title)
    if cat:
        return cat

    # 2. fallback 关键词规则
    text = f"{name} {description} {syntax_txt}".lower()
    if any(k in text for k in ["add", "sub", "round", "abs", "sqrt", "math"]):
        return "math"
    if any(k in text for k in ["char", "substr", "concat", "string", "length"]):
        return "string"
    if any(k in text for k in ["date", "time", "timestamp", "year", "month"]):
        return "date-time"
    if any(k in text for k in ["cast", "convert", "to_"]):
        return "conversion"
    if any(k in text for k in ["count", "sum", "avg", "min", "max", "group"]):
        return "aggregate"
    return "other"

# ---- 收集函数块时带章节信息 ----
def collect_blocks(lines):
    """收集每个函数块的起止行号 + 上方章节名"""
    starts = []
    current_chapter = None
    for i, line in enumerate(lines):
        # 判断章节
        if re.search(r"Functions$", line, re.IGNORECASE):
            current_chapter = line.strip()
        # 判断函数
        if is_func_heading(lines, i):
            starts.append((i, current_chapter))

    for k, (si, chap) in enumerate(starts):
        ei = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        yield si, ei, chap

# ---- 解析单个函数块 ----
def parse_block(block, chapter_title):
    name = block[0].strip()

    # Syntax
    idx_syntax = find_first_idx(block, "Syntax")
    syntax_txt = ""
    if idx_syntax is not None:
        syntax_txt = slice_until_label(block, idx_syntax+1, LABELS)

    # Description
    description = ""
    idx_purpose = find_first_idx(block, "Purpose")
    idx_desc = find_first_idx(block, "Description")
    if idx_purpose is not None:
        description = slice_until_label(block, idx_purpose+1, LABELS)
    elif idx_desc is not None:
        description = slice_until_label(block, idx_desc+1, LABELS)

    # Examples
    examples = []
    idx_examples = find_first_idx(block, "Examples")
    if idx_examples is not None:
        examples = gather_example_block(block, idx_examples)

    # detail
    parts = []
    if description:
        parts.append(f"[DESCRIPTION]: {description}")
    if syntax_txt:
        parts.append(f"[SYNTAX]: {syntax_txt}")
    if examples:
        parts.append("[DEMO]: " + " ; ".join(examples[:3]))
    detail = "<sep>".join(parts)

    short_desc = description[:100] if description else "No description available."

    # 🔑 分类
    category = classify_function(name, description, syntax_txt, chapter_title)

    return {
        "type": "function",
        "keyword": name,
        "tree": syntax_txt or "(functionCall ...)",
        "description": short_desc,
        "detail": detail,
        "example": examples,
        "source": SOURCE_TAG,
        "category": category,
    }

def main():
    lines = load_lines(PDF_PATH)
    items = []
    seen = set()
    for si, ei, chap in collect_blocks(lines):
        block = lines[si:ei]
        try:
            item = parse_block(block, chap)
            if item["keyword"] not in seen:
                items.append(item)
                seen.add(item["keyword"])
        except Exception as e:
            items.append({
                "type": "function",
                "keyword": (block[0].strip() if block else "UNKNOWN"),
                "tree": "(functionCall ...)",
                "description": "Parse error.",
                "detail": str(e),
                "example": [],
                "source": SOURCE_TAG,
                "category": "other",
            })
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Parsed {len(items)} functions → {OUT_JSON}")

if __name__ == "__main__":
    main()
