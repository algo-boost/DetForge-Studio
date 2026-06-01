"""策略与模板 JSON 加载（供 API 与 strategy_executor 共用）。"""
from __future__ import annotations

import json
import os

from studio.paths import PROJECT_ROOT as BASE_DIR

STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies')
TEMPLATES_DIR = os.path.join(STRATEGIES_DIR, 'templates')


def _load_json_dir(directory):
    items = {}
    if not os.path.isdir(directory):
        return items
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'id' in data:
                            items[data['id']] = data
                except Exception as e:
                    print(f"⚠️ 加载失败: {fname}: {e}")
    return items


def load_templates_raw():
    return _load_json_dir(TEMPLATES_DIR)


def get_all_templates():
    from server.core import apply_categories_to_templates, get_defect_categories_bundle

    raw = load_templates_raw()
    bundle = get_defect_categories_bundle()
    return apply_categories_to_templates(raw, bundle.get('categories'))


def get_all_strategies():
    items = {}
    if not os.path.isdir(STRATEGIES_DIR):
        return items
    for entry in os.listdir(STRATEGIES_DIR):
        epath = os.path.join(STRATEGIES_DIR, entry)
        if os.path.isdir(epath) and entry == 'templates':
            continue
        if os.path.isdir(epath):
            for root, _, files in os.walk(epath):
                for fname in files:
                    if fname.endswith('.json'):
                        try:
                            with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if 'id' in data:
                                    items[data['id']] = data
                        except Exception as e:
                            print(f"⚠️ 加载策略失败: {fname}: {e}")
        elif entry.endswith('.json'):
            try:
                with open(epath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'id' in data:
                        items[data['id']] = data
            except Exception as e:
                print(f"⚠️ 加载策略失败: {entry}: {e}")
    return items


def resolve_strategy_ref(stage_spec, strategies=None):
    """解析 stage 配置 → 策略 dict。支持 strategy_id / snapshot / skip。"""
    if not stage_spec:
        raise ValueError('缺少策略配置')
    if stage_spec.get('skip'):
        return None
    if stage_spec.get('snapshot'):
        return dict(stage_spec['snapshot'])
    sid = (stage_spec.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('stage 需要 strategy_id 或 snapshot')
    strategies = strategies if strategies is not None else get_all_strategies()
    strategy = strategies.get(sid)
    if not strategy:
        raise ValueError(f'策略不存在: {sid}')
    return dict(strategy)
