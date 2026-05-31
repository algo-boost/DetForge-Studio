#!/usr/bin/env python3
"""
从 ai.magic-fox.com 训练平台抓取所有模型训练记录，输出 CSV

用法:
    python fetch_training_models.py --url "https://www.ai.magic-fox.com/#/training?approachId=598&subjectId=190"
    python fetch_training_models.py --url "..." --out ./results
    python fetch_training_models.py --url "..." --no-headless   # 显示浏览器窗口

依赖:
    pip install playwright
    playwright install chromium
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COLUMNS = ["train_id", "创建时间", "模型版本", "模型类型", "训练时长", "创建人", "训练进度",  "数据集快照", "备注"]

BASE_URL = "https://www.ai.magic-fox.com/"
NAV_FIRST_TIMEOUT_MS = 120_000
NAV_TRAIN_TIMEOUT_MS = 120_000
TABLE_WAIT_MS = 90_000

def _auth_search_roots() -> list:
    """脚本在任意仓库根目录，或位于 skill 的 scripts/ 子目录时，向上查找认证文件。"""
    d = Path(__file__).resolve().parent
    roots = [d]
    if d.name == "scripts":
        roots.append(d.parent)
    return roots


def _load_auth_storage() -> dict:
    """优先 .local_storage.json，否则 .token；均无则读环境变量 MAGIC_FOX_TOKEN / MAGIC_FOX_ACCESS_TOKEN。"""
    for root in _auth_search_roots():
        ls_file = root / ".local_storage.json"
        token_file = root / ".token"
        if ls_file.exists():
            return json.loads(ls_file.read_text(encoding="utf-8"))
        if token_file.exists():
            return {"token": token_file.read_text().strip()}
    env_tok = (os.getenv("MAGIC_FOX_TOKEN") or os.getenv("MAGIC_FOX_ACCESS_TOKEN") or "").strip()
    if env_tok:
        return {"token": env_tok}
    return {}


EXTRACT_JS = """() => {
    const rows = document.querySelectorAll('tr.ant-table-row');
    return Array.from(rows).map(r => ({
        id: r.getAttribute('data-row-key'),
        cells: Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim())
    }));
}"""

TOTAL_JS = """() => {
    const el = Array.from(document.querySelectorAll('li')).find(
        li => li.innerText && li.innerText.includes('共') && li.innerText.includes('条')
    );
    if (!el) return 0;
    const m = el.innerText.match(/共\\s*(\\d+)\\s*条/);
    return m ? parseInt(m[1]) : 0;
}"""

NEXT_PAGE_JS = """() => {
    const btn = document.querySelector('li.ant-pagination-next:not(.ant-pagination-disabled)');
    if (btn) { btn.click(); return true; }
    return false;
}"""


def normalize_version(ver: str) -> str:
    import re
    def replace(m):
        base = m.group(1)
        count = len(re.findall(r"_plus", m.group(2)))
        return f"{base}_{count}plus"
    return re.sub(r"(V\w+?)(_plus(?:_plus)*)", replace, ver)


def parse_approach_id(url: str) -> str:
    fragment = urlparse(url).fragment or ""
    query = fragment.split("?", 1)[1] if "?" in fragment else ""
    qs = parse_qs(query)
    return qs.get("approachId", ["unknown"])[0]


_DOM_ORDER = ["模型版本", "模型类型", "备注", "数据集快照", "训练时长", "创建人", "创建时间", "训练进度"]


def rows_to_records(raw_rows: list) -> list:
    records = []
    for row in raw_rows:
        cells = row["cells"][:8]
        cells += [""] * (8 - len(cells))
        rec = {"train_id": row["id"]}
        for col, val in zip(_DOM_ORDER, cells):
            rec[col] = val
        rec["模型版本"] = normalize_version(rec["模型版本"])
        # 按 COLUMNS 顺序输出
        records.append({col: rec.get(col, "") for col in COLUMNS})
    return records


def scrape(url: str, headless: bool) -> list:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "请先安装依赖（在 backend 目录执行）:\n"
            "  pip install -r requirements.txt\n"
            "  python -m playwright install chromium"
        )

    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )

        # 读取 localStorage 认证数据（优先用 .local_storage.json，退而求其次用 .token）
        ls_data = _load_auth_storage()

        page = ctx.new_page()

        # 先访问首页建立同源 origin，再写入 localStorage，最后跳转目标页
        print("正在注入认证信息...")
        last_err = None
        for attempt in range(1, 4):
            try:
                page.goto(BASE_URL, wait_until="commit", timeout=NAV_FIRST_TIMEOUT_MS)
                break
            except Exception as e:
                last_err = e
                print(f"  首页加载重试 {attempt}/3: {e}")
                if attempt == 3:
                    raise last_err
                page.wait_for_timeout(2000)

        for key, val in ls_data.items():
            # val 可能是字符串或对象，统一序列化为字符串存入
            stored = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
            page.evaluate(f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(stored)});")

        print(f"正在访问: {url}")
        page.goto(url, wait_until="load", timeout=NAV_TRAIN_TIMEOUT_MS)
        page.wait_for_selector("tr.ant-table-row", timeout=TABLE_WAIT_MS)

        total = page.evaluate(TOTAL_JS)
        print(f"共 {total} 条，开始逐页抓取...")

        page_num = 1
        while True:
            rows = page.evaluate(EXTRACT_JS)
            all_rows.extend(rows)
            print(f"  第 {page_num} 页：{len(rows)} 条（累计 {len(all_rows)}）")

            if not page.evaluate(NEXT_PAGE_JS):
                break
            page_num += 1
            page.wait_for_timeout(1500)
            page.wait_for_selector("tr.ant-table-row", timeout=15000)

        browser.close()

    return rows_to_records(all_rows)


def save_csv(records: list, path: Path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    print(f"已保存: {path}  （{len(records)} 条）")


def main():
    parser = argparse.ArgumentParser(description="抓取魔狸训练平台模型列表")
    parser.add_argument("--url", required=True, help="训练页面 URL，如 https://www.ai.magic-fox.com/#/training?approachId=598&subjectId=190")
    parser.add_argument("--out", default=".", help="输出目录（默认当前目录，与 --csv 二选一时使用）")
    parser.add_argument(
        "--csv",
        dest="csv_file",
        default=None,
        help="输出 CSV 的完整路径（若指定则优先使用，供后端子进程调用）",
    )
    parser.add_argument("--no-headless", dest="headless", action="store_false", default=True, help="显示浏览器窗口")
    args = parser.parse_args()

    approach_id = parse_approach_id(args.url)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = scrape(args.url, headless=args.headless)

    print(f"\n共获取 {len(records)} 条记录")
    if args.csv_file:
        csv_path = Path(args.csv_file)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        csv_path = out_dir / f"training_models_{approach_id}.csv"
    save_csv(records, csv_path)


if __name__ == "__main__":
    main()
