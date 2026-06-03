"""验证 job 11 预测结果筛选：编译语义 + 预览行数。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5050'

USER_RULES = [
    {
        'categories': [
            '其他', '凹坑', '划伤', '压痕', '发亮', '异物外漏', '异色', '抛线', '拼接间隙',
            '擦伤', '断线', '未开孔', '杂质', '水渍', '漏墨', '焊丝', '爆线', '破损', '碰伤',
            '红标签', '纹理缺失', '线头', '缺料', '胶水', '脏污', '色差', '褶皱（重度）', '针眼',
            '飞边', '麻点', '鼓包',
        ],
        'confidence_range': [0, 0.25],
        'random_drop_ratio': 1,
    },
    {
        'categories': ['其他', '异色', '水渍', '焊丝', '脏污'],
        'confidence_range': [0, 1],
        'random_drop_ratio': 1,
    },
    {'categories': ['线头'], 'confidence_range': [0, 1], 'random_drop_ratio': 1},
]


def post(path, payload):
    req = urllib.request.Request(
        f'{BASE}{path}',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode('utf-8'))


def build_flow():
    import uuid

    def uid():
        return 'n' + uuid.uuid4().hex[:8]

    body = [
        {
            'id': uid(),
            'type': 'builtin.filter_df_by_ext',
            'params': {'bind_loop_rule': 'loop_rule'},
        },
        {'id': uid(), 'type': 'builtin.remove_empty_ext_rows', 'params': {}},
    ]
    return {
        'version': 2,
        'nodes': [{
            'id': uid(),
            'type': 'control.loop',
            'params': {
                'loop_mode': 'rules',
                'rules_semantics': 'prune_boxes',
                'rules': USER_RULES,
            },
            'body': body,
        }],
    }


def main():
    flow = build_flow()
    comp = post('/api/flow/compile', {'flow': flow, 'target': 'filter_rules'})
    if not comp.get('success'):
        print('COMPILE_FAIL', comp.get('error'))
        return 1
    code = comp.get('python_code') or ''
    print('--- compile apply_filter_rules ---')
    print(code[:800] + ('...' if len(code) > 800 else ''))
    ok_compile = 'filter_df_by_ext' in code and 'select_df_rows_by_rules_union' not in code
    print('compile_ok:', ok_compile)

    process_code = (
        'def process_data(df):\n'
        '    df = apply_filter_rules(df)\n'
        '    return df\n'
    )
    preview = post('/api/preview-filter', {
        'sql': 'SELECT * FROM `detforge`.`predict_result`\nWHERE job_id = 11',
        'data_source': 'predict_result',
        'predict_job_id': 11,
        'filter_mode': 'flow',
        'flow': flow,
        'filter_rules_code': code,
        'python_code': process_code,
        'preview_mode': 'full',
    })
    if not preview.get('success'):
        print('PREVIEW_FAIL', preview.get('error'))
        return 1
    sql_rows = preview.get('sql_rows')
    filter_rows = preview.get('filter_rows')
    print('--- preview-filter ---')
    print(f'SQL {sql_rows} 行 -> 筛选后 {filter_rows} 行')
    if preview.get('filter_warnings'):
        print('warnings:', preview['filter_warnings'])
    ok_preview = filter_rows is not None and sql_rows is not None and filter_rows < sql_rows
    print('preview_rows_reduced:', ok_preview)
    return 0 if ok_compile and ok_preview else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print('SERVER_DOWN', e)
        sys.exit(3)
