#!/usr/bin/env python3
"""本地完整链路验证：查询 task → 筛选批次 → COCO 回传 → 归档 → 分包 handoff → 人工质检 handoff。

用法（需 Flask 运行在 5050）：
  python scripts/validate_handoff_chain.py
  DETFORGE_STUDIO_URL=http://127.0.0.1:5050 python scripts/validate_handoff_chain.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = os.environ.get('DETFORGE_STUDIO_URL', 'http://127.0.0.1:5050').rstrip('/')
EXPORTS = ROOT / 'exports'
DATASETS = ROOT / 'datasets' / 'training_inbox'


def _http_json(method, path, body=None, files=None):
    import urllib.error
    import urllib.request

    url = f'{BASE}{path}'
    if files:
        import mimetypes
        boundary = uuid.uuid4().hex
        buf = BytesIO()
        for name, (fname, content, ctype) in files.items():
            buf.write(f'--{boundary}\r\n'.encode())
            buf.write(f'Content-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'.encode())
            buf.write(f'Content-Type: {ctype or mimetypes.guess_type(fname)[0] or "application/octet-stream"}\r\n\r\n'.encode())
            buf.write(content)
            buf.write(b'\r\n')
        buf.write(f'--{boundary}--\r\n'.encode())
        req = urllib.request.Request(
            url, data=buf.getvalue(),
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            method=method,
        )
    elif body is not None:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'},
            method=method,
        )
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        try:
            payload = json.loads(err)
        except json.JSONDecodeError:
            payload = {'error': err}
        raise RuntimeError(f'{method} {path} → HTTP {e.code}: {payload.get("error") or err[:500]}') from e


def _png_bytes():
    """最小合法 1x1 PNG。"""
    return bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
        '0000000a49444154789c6300010000050001000d0a2db40000000049454e44ae426082'
    )


def _setup_task(task_id: str):
    task_dir = EXPORTS / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    img1 = task_dir / 'chain_sample_001.jpg'
    img2 = task_dir / 'chain_sample_002.jpg'
    png = _png_bytes()
    img1.write_bytes(png)
    img2.write_bytes(png)

    import pandas as pd
    df = pd.DataFrame([
        {'img_path': str(img1), 'product_no': 'SN-CHAIN-001', 'product_type': 'T1', 'check_status': '1', 'ext': ''},
        {'img_path': str(img2), 'product_no': 'SN-CHAIN-002', 'product_type': 'T2', 'check_status': '0', 'ext': ''},
    ])
    df.to_csv(task_dir / 'result.csv', index=False)

    coco = {
        'info': {'description': 'validate_handoff_chain'},
        'images': [
            {'id': 0, 'file_name': 'chain_sample_001.jpg', 'width': 1, 'height': 1},
            {'id': 1, 'file_name': 'chain_sample_002.jpg', 'width': 1, 'height': 1},
        ],
        'annotations': [],
        'categories': [],
    }
    (task_dir / '_annotations.coco.json').write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding='utf-8')
    (task_dir / 'query_meta.json').write_text(json.dumps({
        'strategy_id': 'daily_trawl',
        'strategy_name': 'Daily Trawl',
        'data_source': 'detail',
    }), encoding='utf-8')
    return task_dir


def _step(name):
    print(f'\n▶ {name}')


def main():
    import urllib.error
    import urllib.request

    print(f'验证目标: {BASE}')
    try:
        with urllib.request.urlopen(f'{BASE}/', timeout=5) as resp:
            if resp.status != 200:
                raise RuntimeError(f'HTTP {resp.status}')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f'✗ Flask 未运行: {e}')
        print('  请先: cd tools/DetForge-Studio && python app.py')
        return 1

    _step('1. 初始化写库表')
    r = _http_json('POST', '/api/forge/schema/init')
    print(f'  schema statements: {r.get("statements", r)}')

    task_id = f'validate-{datetime.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:6]}'
    _step(f'2. 准备查询 task ({task_id})')
    task_dir = _setup_task(task_id)
    print(f'  task_dir: {task_dir}')

    _step('3. 创建筛选批次')
    r = _http_json('POST', '/api/forge/curation', {
        'task_id': task_id,
        'strategy_id': 'daily_trawl',
        'strategy_name': 'Daily Trawl',
        'intent_type': 'daily_ng',
    })
    batch = r['data']
    bid = batch['id']
    print(f'  batch_id={bid} code={batch["batch_code"]} intent={batch.get("intent_type")}')

    _step('4. 生成出站包')
    r = _http_json('POST', f'/api/forge/curation/{bid}/export', {'include_images': True})
    export_dir = r['out_dir']
    assert os.path.isdir(export_dir), export_dir
    assert os.path.isfile(os.path.join(export_dir, '_annotations.coco.json'))
    print(f'  export_dir={export_dir} items={r.get("items")} images={r.get("images_copied")}')

    _step('5. 回传 COCO（含 disposition）')
    curated = {
        'info': {},
        'images': [{
            'id': 0,
            'file_name': 'chain_sample_001.jpg',
            'extra': {'disposition': 'need_label', 'need_platform_label': True},
        }],
        'annotations': [],
        'categories': [],
    }
    coco_bytes = json.dumps(curated, ensure_ascii=False).encode()
    r = _http_json('POST', f'/api/forge/curation/{bid}/import', files={
        'file': ('_annotations.coco.json', coco_bytes, 'application/json'),
    })
    print(f'  keep={r.get("keep")} reject={r.get("reject")} matched_keep={r.get("matched_keep")}')

    _step('6. 确认归档')
    r = _http_json('POST', f'/api/forge/curation/{bid}/archive', {'copy_images': True})
    archive_dir = r['archive_dir']
    print(f'  archive_dir={archive_dir} keep_count={r.get("keep_count")}')

    _step('7. 生成分包 handoff（both）')
    r = _http_json('POST', f'/api/forge/curation/{bid}/handoff', {'split': 'both'})
    handoff_dir = r['handoff_dir']
    all_kept = os.path.join(handoff_dir, 'all_kept', '_annotations.coco.json')
    to_label = os.path.join(handoff_dir, 'to_label', '_annotations.coco.json')
    for p in (all_kept, to_label):
        if not os.path.isfile(p):
            raise RuntimeError(f'缺少 handoff 文件: {p}')
    print(f'  handoff_dir={handoff_dir}')
    print(f'  packs={list((r.get("packs") or {}).keys())}')

    _step('8. 人工质检 → 训练 handoff')
    qc_img = EXPORTS / 'manual_qc_validate' / f'{uuid.uuid4().hex[:8]}.jpg'
    qc_img.parent.mkdir(parents=True, exist_ok=True)
    qc_img.write_bytes(_png_bytes())
    plat_img = EXPORTS / task_id / 'chain_sample_001.jpg'
    from studio.forge import forge_db
    from studio.curation.dispositions import disposition_from_qc_record
    row = {
        'product_no': 'SN-QC-HANDOFF',
        'customer_img_path': str(qc_img),
        'matched_img_path': str(plat_img),
        'qc_category': '成像不清',
        'defect_type': '脏污',
        'match_status': 'matched',
        'defect_info': {'ext': {'original_predictions': [
            {'name': '脏污', 'points': [{'x': 1, 'y': 2, 'w': 10, 'h': 10}]},
        ]}},
        'training_status': 'pending',
    }
    row['disposition'] = disposition_from_qc_record(row)
    qc_id = forge_db.insert_manual_qc(row)
    print(f'  manual_qc id={qc_id} disposition={row["disposition"]}')

    r = _http_json('POST', '/api/forge/manual-qc/handoff', {'training_status': 'pending'})
    qc_handoff = r['out_dir']
    assert os.path.isfile(os.path.join(qc_handoff, '_annotations.coco.json'))
    print(f'  qc_handoff={qc_handoff} records={r.get("record_count")}')

    _step('9. 统一筛选归档列表')
    r = _http_json('GET', '/api/forge/archive-handoff?limit=10')
    batches = r.get('curation_batches') or []
    qc_sum = r.get('manual_qc_summary') or {}
    found = any(b.get('id') == bid for b in batches)
    print(f'  curation_batches={len(batches)} found_current={found}')
    print(f'  manual_qc_summary={qc_sum}')

    _step('10. 标记 curation 已交接')
    r = _http_json('POST', f'/api/forge/curation/{bid}/handoff-done', {'note': 'validate_handoff_chain'})
    print(f'  status={r["data"].get("status")}')

    print('\n✓ 完整链路验证通过')
    print(f'  task:       {task_dir}')
    print(f'  archive:    {archive_dir}')
    print(f'  handoff:    {handoff_dir}')
    print(f'  qc_handoff: {qc_handoff}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
