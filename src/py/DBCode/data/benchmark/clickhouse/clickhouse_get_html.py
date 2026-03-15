# -*- coding: utf-8 -*-
"""
Generate ClickHouse function doc URLs from local md files.
"""

import os
import json

ROOT = r"D:\Desktop\teach\codes\pachong_sql\ClickHousefunctions"
OUT_FILE = r"D:\Desktop\teach\codes\pachong_sql\clickhouse_function_urls.json"

def build_source(md_path: str) -> str:
    rel = os.path.relpath(md_path, ROOT).replace("\\", "/").lower()
    if rel.endswith("index.md"):
        return ""

    if rel.startswith("geo/") and rel.endswith(".md"):
        # geo 子目录，拼接 clickhouse.com 域名
        name = os.path.splitext(os.path.basename(rel))[0]
        return f"https://clickhouse.com/docs/sql-reference/functions/geo/{name}"

    # 普通情况
    name = os.path.splitext(os.path.basename(rel))[0]
    return f"https://clickhouse.com/docs/sql-reference/functions/{name}"

def main():
    urls = []
    for root, _, files in os.walk(ROOT):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            if fn.lower() == "index.md":
                continue
            md_path = os.path.join(root, fn)
            url = build_source(md_path)
            if url:
                urls.append(url)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(urls)} urls → {OUT_FILE}")

if __name__ == "__main__":
    main()
