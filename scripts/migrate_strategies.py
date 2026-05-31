#!/usr/bin/env python3
"""批量迁移 strategies 目录下的 JSON 策略到 filter_rules_code + python_code 拆分格式。"""
import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from studio.flow.flow_compiler import normalize_strategy
from studio.flow.flow_schema import prepare_strategy
from studio.paths import PROJECT_ROOT

HERE = PROJECT_ROOT
STRATEGIES_DIR = os.path.join(PROJECT_ROOT, 'strategies')
TEMPLATES_DIR = os.path.join(STRATEGIES_DIR, 'templates', '_builtin')


def load_templates():
    templates = {}
    if not os.path.isdir(TEMPLATES_DIR):
        return templates
    for fname in os.listdir(TEMPLATES_DIR):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(TEMPLATES_DIR, fname)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if data.get('id'):
            templates[data['id']] = data
    return templates


def iter_strategy_files(root=STRATEGIES_DIR):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != 'templates']
        for fname in filenames:
            if fname.endswith('.json'):
                yield os.path.join(dirpath, fname)


def migrate_file(path, templates, dry_run=False):
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    if 'id' not in raw or 'sql_template' not in raw:
        return None, 'skip (not a strategy)'

    before_mode = raw.get('filter_mode')
    before_py_len = len((raw.get('python_code') or ''))
    before_rules = bool((raw.get('filter_rules_code') or '').strip())

    data = prepare_strategy(raw)
    data = normalize_strategy(data, templates)
    data['updated_at'] = datetime.now().isoformat()
    for key in ('source_python_code',):
        data.pop(key, None)

    after_mode = data.get('filter_mode')
    after_py_len = len((data.get('python_code') or ''))
    after_rules = bool((data.get('filter_rules_code') or '').strip())
    changed = (
        before_mode != after_mode
        or before_py_len != after_py_len
        or before_rules != after_rules
        or raw.get('python_code') != data.get('python_code')
        or raw.get('sample_code') != data.get('sample_code')
    )

    if changed and not dry_run:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    status = 'updated' if changed else 'ok'
    return status, (
        f'{status}: mode {before_mode}->{after_mode}, '
        f'rules={after_rules}, py_len={after_py_len}'
    )


def main():
    parser = argparse.ArgumentParser(description='迁移策略 JSON 到规则/代码拆分格式')
    parser.add_argument('--dry-run', action='store_true', help='只打印变更，不写文件')
    parser.add_argument('--path', help='仅迁移指定文件')
    args = parser.parse_args()

    templates = load_templates()
    files = [args.path] if args.path else list(iter_strategy_files())
    updated = 0

    for path in sorted(files):
        rel = os.path.relpath(path, HERE)
        try:
            status, msg = migrate_file(path, templates, dry_run=args.dry_run)
            if status is None:
                print(f'  - {rel}: {msg}')
                continue
            print(f'{"[dry-run] " if args.dry_run else ""}{rel}: {msg}')
            if status == 'updated':
                updated += 1
        except Exception as e:
            print(f'  ! {rel}: ERROR {e}')

    suffix = ' (dry-run)' if args.dry_run else ''
    print(f'\nDone{suffix}: {updated} file(s) changed.')


if __name__ == '__main__':
    main()
