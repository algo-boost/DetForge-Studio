"""组合编排运行级 env 推导：内置模板注册表。"""
from __future__ import annotations

TIME_PRESET_SCRIPT = '''def compute_env(now, inputs, ctx):
    preset = str(inputs.get('preset') or 'yesterday')
    start, end = resolve_time_window({'preset': preset})
    return {'START_TIME': start, 'END_TIME': end}
'''

TIME_OFFSET_DAYS_SCRIPT = '''def compute_env(now, inputs, ctx):
    offset = int(inputs.get('offset_days') or 1)
    sh = int(inputs.get('start_hour') if inputs.get('start_hour') is not None else 0)
    eh = int(inputs.get('end_hour') if inputs.get('end_hour') is not None else 23)
    day = (now - timedelta(days=offset)).replace(hour=sh, minute=0, second=0, microsecond=0)
    end = day.replace(hour=eh, minute=59, second=59, microsecond=0)
    return {
        'START_TIME': format_datetime(day),
        'END_TIME': format_datetime(end),
    }
'''

TIME_ABSOLUTE_SCRIPT = '''def compute_env(now, inputs, ctx):
    start = str(inputs.get('start_time') or '').strip()
    end = str(inputs.get('end_time') or '').strip()
    if not start or not end:
        raise ValueError('start_time / end_time 必填')
    return {'START_TIME': start, 'END_TIME': end}
'''

RUN_ENV_TEMPLATES: dict[str, dict] = {
    'time_preset': {
        'id': 'time_preset',
        'label': '快捷时段',
        'description': '昨日 / 当日 / 近 7 天等 preset，每次运行按当前时间重算',
        'param_schema': [
            {
                'key': 'preset',
                'label': '时段',
                'type': 'select',
                'default': 'yesterday',
                'options': [
                    {'value': 'yesterday', 'label': '昨日'},
                    {'value': 'today', 'label': '当日'},
                    {'value': 'last_7d', 'label': '近 7 天'},
                ],
            },
        ],
        'outputs': ['START_TIME', 'END_TIME'],
        'script': TIME_PRESET_SCRIPT,
    },
    'time_offset_days': {
        'id': 'time_offset_days',
        'label': '相对时段（按天偏移）',
        'description': '以当前时间为基准，向前偏移 N 天并指定起止小时',
        'param_schema': [
            {'key': 'offset_days', 'label': '向前天数', 'type': 'number', 'default': '1'},
            {'key': 'start_hour', 'label': '开始小时', 'type': 'number', 'default': '0'},
            {'key': 'end_hour', 'label': '结束小时', 'type': 'number', 'default': '23'},
        ],
        'outputs': ['START_TIME', 'END_TIME'],
        'script': TIME_OFFSET_DAYS_SCRIPT,
    },
    'time_absolute': {
        'id': 'time_absolute',
        'label': '固定绝对时段',
        'description': '固定 START_TIME / END_TIME（适合一次性补跑）',
        'param_schema': [
            {'key': 'start_time', 'label': '开始时间', 'type': 'text', 'default': '', 'placeholder': '2026-06-01 00:00:00'},
            {'key': 'end_time', 'label': '结束时间', 'type': 'text', 'default': '', 'placeholder': '2026-06-01 23:59:59'},
        ],
        'outputs': ['START_TIME', 'END_TIME'],
        'script': TIME_ABSOLUTE_SCRIPT,
    },
}


def list_run_env_templates(*, include_script=False):
    rows = []
    for tpl in RUN_ENV_TEMPLATES.values():
        row = {
            'id': tpl['id'],
            'label': tpl['label'],
            'description': tpl.get('description'),
            'param_schema': tpl.get('param_schema') or [],
            'outputs': tpl.get('outputs') or [],
        }
        if include_script:
            row['script'] = tpl.get('script') or ''
        rows.append(row)
    return rows


def get_run_env_template(template_id):
    tpl = RUN_ENV_TEMPLATES.get(str(template_id or ''))
    if not tpl:
        return None
    return dict(tpl)
