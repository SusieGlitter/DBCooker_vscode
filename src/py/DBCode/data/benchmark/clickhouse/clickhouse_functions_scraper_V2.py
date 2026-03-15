# -*- coding: utf-8 -*-
"""
ClickHouse 函数文档批量爬虫 → JSON
- 常规：h2 为分组，h3 为函数；过滤 “Overview” 等非函数标题。
- 特例：/array-join 只有一个函数 arrayJoin，位于 <header><h1> 中，正文是 <header> 的后续兄弟节点。
- tree：仅当检测到“Syntax”标签后紧随的代码块；否则置空。
- description：从函数标题后开始，连续收集 <p>/<ul>/<ol> 的文字，直到遇到下一段落标签（Syntax/Arguments/Returned value/Examples/...），保留完整文本（不截断）。
- detail：尽量“补全”关键信息，组合 [DESCRIPTION] + [SYNTAX] + [ARGUMENTS] + [RETURN] + [ALIASES] + [DEMO]。
- example：优先只收集 Examples 区域里的 Query/Response（或 Result/Output）对；若缺失则回退到通用代码块过滤（仅 SQL 与结果）。
- link：把页面 URL 填入数组；不输出 source 字段。
依赖：requests beautifulsoup4 lxml
"""

import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup

# ========= 绝对路径配置 =========
URL_LIST_PATH = r"clickhouse_function_urls.json"
OUT_JSON      = r"clickhouse_functions_all.json"
# =================================

HEADERS       = {"User-Agent": "Mozilla/5.0 (ClickHouseCrawler/2.4)"}
TIMEOUT       = 30
RETRY         = 3
SLEEP_RANGE   = (0.3, 0.9)

SQL_LEADS = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "EXPLAIN")
EXCLUDE_TITLES = {"overview"}  # 非函数小节标题（大小写不敏感）

# 规范化与识别标签
LABELS = {
    "syntax": {"syntax"},
    "arguments": {"arguments", "argument", "parameters", "parameter"},
    "return": {"returned value", "returned values", "return value", "return values", "returns"},
    "examples": {"example", "examples"},
    "query": {"query", "queries"},
    "response": {"response", "result", "results", "output"},
    "aliases": {"alias", "aliases"},
    "notes": {"note", "notes"},
    "impl": {"implementation details", "implementation"},
    "perf": {"performance", "performance considerations", "performance notes"},
    "see": {"see also", "see also:"},
}

SECTION_STOPS = set().union(
    LABELS["syntax"], LABELS["arguments"], LABELS["return"],
    LABELS["examples"], LABELS["aliases"], LABELS["notes"],
    LABELS["impl"], LABELS["perf"], LABELS["see"]
)

def _clean(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u200b", "").replace("\ufeff", "").replace("\u2060", "")
    return re.sub(r"\s+", " ", s).strip()

def _normalize_keyword(s: str) -> str:
    s = _clean(s)
    low = s.lower()
    if low.endswith(" function"):
        s = s[:-(len(" function"))]
    return s.strip()

def _label_name(node) -> str:
    if node is None:
        return ""
    # 兼容 <p><strong>Label</strong></p> / <h4>Label</h4> / 纯文本
    text = _clean(node.get_text(" ", strip=True)).rstrip(":").lower()
    for key, variants in LABELS.items():
        if text in variants:
            return key
    return ""

def _collect_until(start_node, stop_tags):
    buf = []
    for sib in start_node.next_siblings:
        name = getattr(sib, "name", None)
        if name in stop_tags:
            break
        buf.append(sib)
    return buf

def _first_code_after(nodes, start_index: int):
    for j in range(start_index + 1, len(nodes)):
        n = nodes[j]
        code = None
        if getattr(n, "name", None) == "pre":
            code = n.find("code")
        if code is None and hasattr(n, "select"):
            found = n.select("pre > code")
            if found:
                code = found[0]
        if code:
            return code.get_text("\n", strip=True)
    return ""

def _first_code_or_text_after(nodes, start_index: int):
    # 用于 “Response/Result/Output” 后没有 code 的情况，退回到下一个段落文字
    for j in range(start_index + 1, len(nodes)):
        n = nodes[j]
        code = None
        if getattr(n, "name", None) == "pre":
            code = n.find("code")
        if code is None and hasattr(n, "select"):
            found = n.select("pre > code")
            if found:
                code = found[0]
        if code:
            return code.get_text("\n", strip=True)
        if getattr(n, "name", None) in ("p", "div"):
            txt = _clean(n.get_text("\n", strip=True))
            if txt:
                return txt
    return ""

def _gather_all_codes(nodes):
    codes = []
    for n in nodes:
        if hasattr(n, "select"):
            for code in n.select("pre > code"):
                txt = code.get_text("\n", strip=True)
                if txt:
                    codes.append(txt)
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def _looks_like_response_block(text: str) -> bool:
    if any(ch in text for ch in "┌┐└┘│─"):
        return True
    if re.search(r"^\s*[-+|]{2,}\s*$", text, flags=re.M):
        return True
    # 也允许非常短小的标量输出（如 “10”）
    if text.strip() and "\n" not in text and len(text.strip()) <= 32 and not _looks_like_sql_block(text):
        return True
    return False

def _looks_like_sql_block(text: str) -> bool:
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    return any(first.upper().startswith(kw) for kw in SQL_LEADS)

def _filter_examples_general(examples, tree_text):
    filtered = []
    tree_norm = (tree_text or "").strip()
    for ex in examples:
        ex_stripped = ex.strip()
        if tree_norm and ex_stripped == tree_norm:
            continue
        if _looks_like_sql_block(ex_stripped) or _looks_like_response_block(ex_stripped):
            filtered.append(ex)
    return filtered

def _extract_description(fn_nodes):
    """收集标题后到第一个分节标签（Syntax/Arguments/...）之前的 <p>/<ul>/<ol> 文本"""
    chunks = []
    for n in fn_nodes:
        tag = getattr(n, "name", None)
        if tag in ("h2", "h3", "h4"):
            # 小节内部又出现新标题，停止
            break
        label = _label_name(n)
        if label and (label in SECTION_STOPS):
            break
        if tag == "p":
            t = _clean(n.get_text(" ", strip=True))
            if t:
                chunks.append(t)
        elif tag in ("ul", "ol"):
            items = []
            for li in n.find_all("li", recursive=False):
                t = _clean(li.get_text(" ", strip=True))
                if t:
                    items.append(f"- {t}")
            if items:
                chunks.append("\n".join(items))
    return "\n".join(chunks).strip()

def _extract_block_text_after(fn_nodes, start_i):
    """提取一个分节（Arguments/Returned/Aliases 等）后的连续段落与列表，直到下一个分节或标题"""
    parts = []
    for j in range(start_i + 1, len(fn_nodes)):
        n = fn_nodes[j]
        tag = getattr(n, "name", None)
        if tag in ("h2", "h3", "h4"):
            break
        label = _label_name(n)
        if label and (label in SECTION_STOPS or label in ("query", "response")):
            break
        if tag == "p":
            t = _clean(n.get_text(" ", strip=True))
            if t:
                parts.append(t)
        elif tag in ("ul", "ol"):
            items = []
            for li in n.find_all("li", recursive=False):
                t = _clean(li.get_text(" ", strip=True))
                if t:
                    items.append(f"- {t}")
            if items:
                parts.append("\n".join(items))
        elif tag == "pre":
            code = n.find("code")
            if code:
                parts.append(code.get_text("\n", strip=True))
        elif hasattr(n, "select"):
            # 兜底：如果容器内有 code
            found = n.select("pre > code")
            if found:
                parts.extend([c.get_text("\n", strip=True) for c in found])
    return "\n".join([p for p in parts if p]).strip()

def _extract_examples_from_examples_section(fn_nodes):
    """优先从 Examples 区域按 Query/Response 成对提取"""
    examples = []
    in_examples = False
    i = 0
    while i < len(fn_nodes):
        n = fn_nodes[i]
        label = _label_name(n)
        if not in_examples:
            if label == "examples":
                in_examples = True
                i += 1
                continue
        else:
            # 到下一个分节/标题则停止
            if getattr(n, "name", None) in ("h2", "h3", "h4"):
                break
            if label and (label in SECTION_STOPS):
                break

            if label == "query":
                q = _first_code_or_text_after(fn_nodes, i)
                if q:
                    examples.append(q)
            elif label == "response":
                r = _first_code_or_text_after(fn_nodes, i)
                if r:
                    examples.append(r)
        i += 1
    return examples

# ----------------- 新增：基于章节与关键字推断类别 -----------------
CATEGORY_MAP = {
    # 常见英文片段 -> 归一化类别
    "math": "math",
    "mathematical": "math",
    "arithmetic": "math",
    "date": "date_time",
    "time": "date_time",
    "datetime": "date_time",
    "date-time": "date_time",
    "string": "string",
    "text": "string",
    "char": "string",
    "character": "string",
    "array": "array",
    "json": "json",
    "aggregate": "aggregate",
    "aggregation": "aggregate",
    "conditional": "conditional",
    "conversion": "conversion",
    "bit": "bitwise",
    "bitwise": "bitwise",
    "ip": "ip",
    "ipv4": "ip",
    "ipv6": "ip",
    "geo": "geo",
    "uuid": "uuid",
    "hash": "hash",
    "url": "url",
    # 中文常见词也支持
    "数学": "math",
    "日期": "date_time",
    "时间": "date_time",
    "字符串": "string",
    "数组": "array",
    "聚合": "aggregate",
    "条件": "conditional",
}

def infer_category(keyword: str, description: str, section_title: str = "", url: str = "") -> str:
    """
    优先通过章节标题判断类别（section_title），若无法判断则回退到 URL、函数名与描述中的关键词检查。
    返回归一化类别字符串，比如 'math','date_time','string','array','json','aggregate','conditional','other' 等。
    """
    low_section = (section_title or "").lower()
    low_key = (keyword or "").lower()
    low_desc = (description or "").lower()
    low_url = (url or "").lower()

    # 1) 章节优先判断：查找 CATEGORY_MAP 中的键是否在章节标题中出现
    for k, v in CATEGORY_MAP.items():
        if k in low_section:
            return v

    # 2) 次优：URL 路径中含关键片段
    for k, v in CATEGORY_MAP.items():
        if k in low_url:
            return v

    # 3) 函数名/描述中的关键字判断（常用缩写/关键词）
    math_keys = {"abs", "sqrt", "round", "pow", "log", "sin", "cos", "tan", "ceil", "floor", "mod", "div", "trunc"}
    if any(tok in low_key for tok in math_keys) or any(tok in low_desc for tok in ["math", "absolute", "sqrt", "logarithm"]):
        return "math"

    if any(tok in low_key for tok in ["date", "time", "timestamp"]) or any(tok in low_desc for tok in ["date", "time", "timestamp"]):
        return "date_time"

    if "json" in low_key or "json" in low_desc:
        return "json"

    if "array" in low_key or "array" in low_desc:
        return "array"

    if any(tok in low_key for tok in ["substr", "concat", "split", "lower", "upper", "trim"]) or any(tok in low_desc for tok in ["string", "substring", "character"]):
        return "string"

    if "uuid" in low_key or "uuid" in low_desc:
        return "uuid"

    if "ip" in low_key or "ip" in low_desc:
        return "ip"

    if any(tok in low_key for tok in ["if", "case", "when", "coalesce"]) or any(tok in low_desc for tok in ["conditional", "if", "case"]):
        return "conditional"

    if any(tok in low_key for tok in ["agg", "group", "sum", "avg", "min", "max"]) or "aggregate" in low_desc:
        return "aggregate"

    # 回退为 other
    return "other"
# ----------------- /新增 -----------------

# ----------------- 特例：单函数 h1 页面（/array-join） -----------------
def _parse_single_h1_function(container: BeautifulSoup, url: str):
    header = container.select_one("header h1")
    if not header:
        return []

    header_tag = header.parent if header and getattr(header, "parent", None) else None
    if not header_tag or header_tag.name != "header":
        return []

    keyword = _normalize_keyword(header.get_text(" ", strip=True))
    fn_nodes = _collect_until(header_tag, {"header"})  # 从 <header> 之后到文末

    description = _extract_description(fn_nodes)

    # tree（Syntax）
    tree = ""
    for i, n in enumerate(fn_nodes):
        if _label_name(n) == "syntax":
            syntax_text = _first_code_after(fn_nodes, i)
            if syntax_text:
                tree = syntax_text.strip()
            break

    # Arguments / Return / Aliases / Examples
    arguments = return_val = aliases = ""
    for i, n in enumerate(fn_nodes):
        label = _label_name(n)
        if label == "arguments":
            arguments = _extract_block_text_after(fn_nodes, i)
        elif label == "return":
            return_val = _extract_block_text_after(fn_nodes, i)
        elif label == "aliases":
            aliases = _extract_block_text_after(fn_nodes, i)

    ex_from_examples = _extract_examples_from_examples_section(fn_nodes)
    if ex_from_examples:
        examples = ex_from_examples
    else:
        all_codes = _gather_all_codes(fn_nodes)
        examples = _filter_examples_general(all_codes, tree)

    parts = []
    if description:
        parts.append(f"[DESCRIPTION]: {description}")
    if tree:
        parts.append(f"[SYNTAX]: {tree}")
    if arguments:
        parts.append(f"[ARGUMENTS]: {arguments}")
    if return_val:
        parts.append(f"[RETURN]: {return_val}")
    if aliases:
        parts.append(f"[ALIASES]: {aliases}")
    if examples:
        parts.append("[DEMO]: " + " ; ".join([e.splitlines()[0] for e in examples[:3]]))
    detail = "<sep>".join(parts)

    # 新增 category 字段，优先用 header 文本判断，回退到关键字/描述
    section_title = header.get_text(" ", strip=True)
    category = infer_category(keyword, description, section_title, url)

    return [{
        "type": "function",
        "keyword": keyword,
        "tree": tree,
        "description": description,
        "detail": detail,
        "example": examples,
        "link": [url],
        "category": category
    }]

# ----------------- 解析单页（通用 + 特例） -----------------
def parse_clickhouse_doc(url: str):
    html = None
    for attempt in range(1, RETRY + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            html = resp.text
            break
        except Exception as e:
            if attempt >= RETRY:
                print(f"[ERROR] Fetch failed after {RETRY} tries: {url} | {e}")
                return []
            time.sleep(0.5 * attempt)

    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one(".theme-doc-markdown, article, main") or soup

    # 特例：/array-join
    if "/array-join" in url.rstrip("/"):
        items = _parse_single_h1_function(container, url)
        if items:
            return items

    results = []
    h2s = container.find_all("h2")
    groups = h2s if h2s else [container]

    for g in groups:
        # 提取章节标题（供 category 推断优先使用）
        section_title = _clean(g.get_text(" ", strip=True)) if getattr(g, "name", None) == "h2" else ""
        section_nodes = _collect_until(g, {"h2"}) if getattr(g, "name", None) == "h2" else list(container.children)
        h3s = [n for n in section_nodes if getattr(n, "name", None) == "h3"]

        if h3s:
            headers = h3s
            stop_tags = {"h3", "h2"}
        else:
            if getattr(g, "name", None) == "h2":
                headers = [g]
                stop_tags = {"h2"}
            else:
                continue

        for h in headers:
            keyword = _normalize_keyword(h.get_text(" ", strip=True))
            if not keyword or _clean(keyword).lower() in EXCLUDE_TITLES:
                continue

            fn_nodes = _collect_until(h, stop_tags)

            # description：函数说明（多段收集）
            description = _extract_description(fn_nodes)

            # tree（Syntax）
            tree = ""
            for i, n in enumerate(fn_nodes):
                if _label_name(n) == "syntax":
                    syntax_text = _first_code_after(fn_nodes, i)
                    if syntax_text:
                        tree = syntax_text.strip()
                    break

            # Arguments / Return / Aliases
            arguments = return_val = aliases = ""
            for i, n in enumerate(fn_nodes):
                label = _label_name(n)
                if label == "arguments":
                    arguments = _extract_block_text_after(fn_nodes, i)
                elif label == "return":
                    return_val = _extract_block_text_after(fn_nodes, i)
                elif label == "aliases":
                    aliases = _extract_block_text_after(fn_nodes, i)

            # Examples：优先从 Examples 区域提取 Query/Response；否则回退到通用过滤
            ex_from_examples = _extract_examples_from_examples_section(fn_nodes)
            if ex_from_examples:
                examples = ex_from_examples
            else:
                all_codes = _gather_all_codes(fn_nodes)
                examples = _filter_examples_general(all_codes, tree)

            parts = []
            if description:
                parts.append(f"[DESCRIPTION]: {description}")
            if tree:
                parts.append(f"[SYNTAX]: {tree}")
            if arguments:
                parts.append(f"[ARGUMENTS]: {arguments}")
            if return_val:
                parts.append(f"[RETURN]: {return_val}")
            if aliases:
                parts.append(f"[ALIASES]: {aliases}")
            if examples:
                parts.append("[DEMO]: " + " ; ".join([e.splitlines()[0] for e in examples[:3]]))
            detail = "<sep>".join(parts)

            # 新增 category 字段：优先使用章节标题（section_title），否则回退到 keyword/description/url 的关键词判断
            category = infer_category(keyword, description, section_title, url)

            results.append({
                "type": "function",
                "keyword": keyword,
                "tree": tree,
                "description": description,
                "detail": detail,
                "example": examples,
                "link": [url],
                "category": category
            })
    return results

# ----------------- 批量执行 -----------------
def main():
    if not os.path.exists(URL_LIST_PATH):
        raise SystemExit(f"URL list not found: {URL_LIST_PATH}")

    with open(URL_LIST_PATH, "r", encoding="utf-8") as f:
        urls = json.load(f)
    if not isinstance(urls, list):
        raise SystemExit("URL list file must contain a JSON array of URLs.")

    all_items = []
    seen = set()
    for idx, url in enumerate(urls, 1):
        if not isinstance(url, str) or not url.strip():
            continue
        print(f"[{idx}/{len(urls)}] Crawling: {url}")
        items = parse_clickhouse_doc(url.strip())
        print(f"    -> {len(items)} functions parsed from {url}")
        for it in items:
            key = (it.get("keyword", ""), (it.get("link") or [""])[0])
            if key not in seen:
                all_items.append(it)
                seen.add(key)
        time.sleep(random.uniform(*SLEEP_RANGE))

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Parsed {len(all_items)} function entries from {len(urls)} URLs → {OUT_JSON}")

if __name__ == "__main__":
    main()
