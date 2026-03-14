import json
import os

import requests
import pandas as pd
from bs4 import BeautifulSoup, Tag
from typing import List, Union, Dict


def fetch_html(url: str, headers: dict | None = None, timeout: int = 10) -> str:
    """Send GET request and return HTML string"""
    headers = headers or {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def save_to_csv(rows: List[Dict[str, str]],
                path: str = "functions.csv",
                mode: str = "a") -> None:
    """
    Append (mode='a') or overwrite (mode='w') rows to CSV
    """
    if not rows:
        return

    df_new = pd.DataFrame(rows, columns=["name", "describe", "example", "url", "tested"])

    # If file doesn't exist, write directly; if exists and appending, remove header
    file_exists = os.path.isfile(path)
    header = not (mode == "a" and file_exists)
    df_new.to_csv(path, mode=mode, header=header, index=False, encoding="utf-8")


def parse(html: str, url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    divs: List[Tag] = soup.find_all("div", class_="table-contents")

    rows_dict: Dict[str, Dict] = {}

    for div in divs:
        table = div.find("table")
        if not table:
            continue

        summary = table.get("summary", "")
        if "function" not in summary.lower():
            continue

        tbody = table.find("tbody") or table

        for tr in tbody.find_all("tr"):
            td = tr.find("td")
            if not td:
                continue

            ps = td.find_all("p")
            if not ps:
                continue

            sig_texts, desc_texts, ex_texts = [], [], []
            first_sig_token = None

            for p_tag in ps:
                text = p_tag.get_text(" ", strip=True)
                classes = p_tag.get("class", [])

                # ---------- Function Signature ----------
                if "func_signature" in classes:
                    sig_texts.append(text)
                    if first_sig_token is None and text.split():
                        first_sig_token = text.split()[0]          # to_char
                    continue

                # ---------- Other Paragraphs ----------
                has_literal = p_tag.find("code", class_="returnvalue") is not None
                is_example = has_literal or ("→" in text)

                if is_example:
                    ex_texts.append(text)                           # Example
                else:
                    desc_texts.append(text)                         # Description

            if not first_sig_token or ("(" not in " ".join(sig_texts)):
                continue

            # ---------- Aggregation ----------
            entry = rows_dict.setdefault(
                first_sig_token,
                {"name": "", "describe": "", "example": "", "url": url, "tested": 0}
            )

            # a) name
            for sig in sig_texts:
                if sig not in entry["name"].splitlines():
                    entry["name"] += ("\n" if entry["name"] else "") + sig

            # b) describe
            if desc_texts:
                entry["describe"] += (" " if entry["describe"] else "") + " ".join(desc_texts)

            # c) example
            if ex_texts:
                entry["example"] += ("\n" if entry["example"] else "") + "\n".join(ex_texts)

    return list(rows_dict.values())


def crawl(df: pd.DataFrame) -> List[List[dict]]:
    results = []

    for idx, url in df["url"].items():          # idx = line number
        if str(df.at[idx, "success"]) == "1":
            print(f"[↷] Skip (already success): {url}")
            continue
        try:
            print(f"Crawling: {url}")
            html = fetch_html(url)
            data = parse(html, url)
            save_to_csv(data)
            results.append(data)
            df.at[idx, "success"] = 1
            print(f"[✓] Done: {url}")
        except Exception as e:
            print(f"[×] Failed: {url}  =>  {e}")

    return results


if __name__ == "__main__":
    df_urls = pd.read_csv("urls.csv")
    res = crawl(df_urls)
    df_urls.to_csv("urls.csv", index=False, encoding="utf-8")
    print(json.dumps(res, indent=4))
