#!/usr/bin/env python3
"""批量登记人工质检案卷（调用 DefectLoop API）。

示例::

    python scripts/manual_qc_intake.py --api http://127.0.0.1:5050 entries.json

entries.json::

    {
      "batch_id": "2026-06-03",
      "entries": [
        {"product_no": "SN001", "customer_img_path": "E:/uploads/a.jpg", "note": "optional"},
        {"product_no": "SN002", "customer_img_path": "E:/uploads/b.jpg", "external_ref": "row-2"}
      ]
    }

也可从 CSV（product_no,customer_img_path,note,external_ref）导入::

    python scripts/manual_qc_intake.py --api http://127.0.0.1:5050 --csv batch.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request


def _post_json(url: str, payload: dict, token: str = '') -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-API-Token'] = token
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            err = json.loads(body)
            raise SystemExit(err.get('error') or body) from e
        except json.JSONDecodeError:
            raise SystemExit(body) from e


def load_entries_from_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = (row.get('product_no') or row.get('sn') or '').strip()
            if not sn:
                continue
            rows.append({
                'product_no': sn,
                'customer_img_path': (row.get('customer_img_path') or row.get('path') or '').strip() or None,
                'note': (row.get('note') or '').strip() or None,
                'external_ref': (row.get('external_ref') or '').strip() or None,
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description='批量登记人工质检案卷')
    parser.add_argument('json_file', nargs='?', help='JSON 文件（含 entries 数组）')
    parser.add_argument('--api', default='http://127.0.0.1:5050', help='DefectLoop 根 URL')
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('--batch-id', help='批次 ID')
    parser.add_argument('--token', default='', help='API Token（若已配置）')
    args = parser.parse_args()

    entries = []
    batch_id = args.batch_id
    if args.csv:
        entries = load_entries_from_csv(args.csv)
    elif args.json_file:
        with open(args.json_file, encoding='utf-8') as f:
            doc = json.load(f)
        entries = doc.get('entries') or doc
        batch_id = batch_id or doc.get('batch_id')
    else:
        parser.error('请提供 json_file 或 --csv')

    if not entries:
        print('无有效条目', file=sys.stderr)
        sys.exit(1)

    url = args.api.rstrip('/') + '/api/forge/manual-qc/intake'
    payload = {'entries': entries, 'batch_id': batch_id, 'source': 'script'}
    result = _post_json(url, payload, token=args.token)
    if not result.get('success'):
        print(result, file=sys.stderr)
        sys.exit(1)
    summary = result.get('summary') or {}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get('errors'):
        sys.exit(2)


if __name__ == '__main__':
    main()
