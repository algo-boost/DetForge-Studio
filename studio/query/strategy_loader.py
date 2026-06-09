"""策略与模板 JSON 加载（供 API 与 strategy_executor 共用）。"""
from __future__ import annotations

import json
import os

from studio.paths import APP_ROOT as BASE_DIR, resource_path

STRATEGIES_DIR = resource_path('strategies')
CATALOG_STRATEGIES_DIR = os.path.join(BASE_DIR, 'catalog_cache', 'strategies')


def effective_strategies_dir() -> str:
    """优先 Catalog 同步目录，回退本地 strategies/。"""
    if os.environ.get('IISP_CATALOG_STRATEGIES', '1').lower() not in ('0', 'false', 'no'):
        if os.path.isdir(CATALOG_STRATEGIES_DIR) and os.listdir(CATALOG_STRATEGIES_DIR):
            return CATALOG_STRATEGIES_DIR
    return STRATEGIES_DIR
TEMPLATES_DIR = os.path.join(STRATEGIES_DIR, 'templates')
# 块模板库目录（非「预设策略」）
TEMPLATE_LIBRARY_DIRS = ('_presets', '_library', '_builtin')

LEGACY_BUILTIN_DIR = os.path.join(STRATEGIES_DIR, '_builtin')

# 历史 strategy_id → 当前策略 id（兼容旧任务/本地缓存）
LEGACY_STRATEGY_ALIASES = {
    'daily_trawl': 'daily_trawl',
    'preset_daily_trawl': 'daily_trawl',
    'preset_ok_history_predict': 'ok_history_predict',
    'preset_ok_predict_filter': 'ok_predict_filter',
}

STRATEGY_SKIP_DIRS = frozenset({'templates', '_presets', '_builtin'})


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


def _normalize_strategy_record(data: dict) -> dict:
    """去掉已废弃的预设策略标记。"""
    out = dict(data)
    out.pop('is_preset', None)
    out.pop('_preset', None)
    if out.get('category') == '预设':
        out['category'] = '推荐'
    return out


def load_templates_raw():
    items = {}
    if not os.path.isdir(TEMPLATES_DIR):
        return items
    items.update(_load_json_dir(TEMPLATES_DIR))
    for lib in TEMPLATE_LIBRARY_DIRS:
        lib_dir = os.path.join(TEMPLATES_DIR, lib)
        if os.path.isdir(lib_dir):
            items.update(_load_json_dir(lib_dir))
    return items


def get_all_templates():
    from server.core import apply_categories_to_templates, get_defect_categories_bundle

    raw = load_templates_raw()
    bundle = get_defect_categories_bundle()
    return apply_categories_to_templates(raw, bundle.get('categories'))


def is_preset_strategy(strategy: dict | None) -> bool:
    """已取消「预设策略」概念，一律返回 False（保留 API 兼容）。"""
    return False


def _strategy_file_id_matches(file_id: str | None, target_id: str) -> bool:
    """文件内 id 是否对应要删的策略（含 LEGACY_STRATEGY_ALIASES 别名）。"""
    if not file_id or not target_id:
        return False
    if file_id == target_id:
        return True
    if LEGACY_STRATEGY_ALIASES.get(file_id) == target_id:
        return True
    if LEGACY_STRATEGY_ALIASES.get(target_id) == file_id:
        return True
    return False


def _remove_strategy_json(fpath: str) -> bool:
    try:
        if os.path.isfile(fpath):
            os.remove(fpath)
            return True
    except OSError:
        pass
    return False


def delete_strategy_by_id(strategy_id: str) -> tuple[bool, str | None]:
    """删除策略 JSON 文件。返回 (成功, 错误信息)。"""
    strategy_id = str(strategy_id or '').strip()
    if not strategy_id:
        return False, 'id 不能为空'

    if strategy_id not in get_all_strategies():
        return False, '策略不存在'

    direct = os.path.join(STRATEGIES_DIR, f'{strategy_id}.json')
    if _remove_strategy_json(direct):
        return True, None

    if os.path.isdir(STRATEGIES_DIR):
        for fname in os.listdir(STRATEGIES_DIR):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(STRATEGIES_DIR, fname)
            if fpath == direct:
                continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    if _strategy_file_id_matches(json.load(f).get('id'), strategy_id):
                        if _remove_strategy_json(fpath):
                            return True, None
            except Exception:
                continue

        for entry in os.listdir(STRATEGIES_DIR):
            epath = os.path.join(STRATEGIES_DIR, entry)
            if not os.path.isdir(epath) or entry == 'templates':
                continue
            for root, _, files in os.walk(epath):
                for fname in files:
                    if not fname.endswith('.json'):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            if _strategy_file_id_matches(json.load(f).get('id'), strategy_id):
                                if _remove_strategy_json(fpath):
                                    return True, None
                    except Exception:
                        continue
    return False, '未找到策略文件'


def get_preset_strategies():
    """已废弃：不再区分预设策略。"""
    return {}


def get_all_strategies():
    items = {}
    strategies_root = effective_strategies_dir()

    if os.path.isdir(strategies_root):
        for entry in os.listdir(strategies_root):
            if entry.endswith('.json'):
                try:
                    with open(os.path.join(strategies_root, entry), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        sid = data.get('id')
                        if sid in LEGACY_STRATEGY_ALIASES and LEGACY_STRATEGY_ALIASES[sid] in items:
                            continue
                        if sid and sid not in items:
                            items[sid] = _normalize_strategy_record(data)
                except Exception as e:
                    print(f"⚠️ 加载策略失败: {entry}: {e}")

        for entry in os.listdir(strategies_root):
            epath = os.path.join(strategies_root, entry)
            if not os.path.isdir(epath) or entry in STRATEGY_SKIP_DIRS:
                continue
            for root, _, files in os.walk(epath):
                for fname in files:
                    if not fname.endswith('.json'):
                        continue
                    try:
                        with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            sid = data.get('id')
                            if sid in LEGACY_STRATEGY_ALIASES and LEGACY_STRATEGY_ALIASES[sid] in items:
                                continue
                            if sid and sid not in items:
                                items[sid] = _normalize_strategy_record(data)
                    except Exception as e:
                        print(f"⚠️ 加载策略失败: {fname}: {e}")

    _ensure_legacy_strategy_aliases(items)
    return items


def _ensure_legacy_strategy_aliases(items: dict):
    """旧 _builtin 策略文件缺失时，按别名补全。"""
    if not os.path.isdir(LEGACY_BUILTIN_DIR):
        return
    legacy = _load_json_dir(LEGACY_BUILTIN_DIR)
    for old_id, canonical_id in LEGACY_STRATEGY_ALIASES.items():
        if canonical_id in items or old_id == canonical_id:
            continue
        if old_id in legacy:
            data = dict(legacy[old_id])
            data['id'] = canonical_id
            items[canonical_id] = _normalize_strategy_record(data)


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
        canonical = LEGACY_STRATEGY_ALIASES.get(sid)
        if canonical:
            strategy = strategies.get(canonical)
    if not strategy:
        raise ValueError(f'策略不存在: {sid}')
    return dict(strategy)


def merge_strategy_for_execution(strategy: dict | None, request_data: dict | None = None) -> dict | None:
    """合并请求体中的 pipeline / presets，使 Python 命名空间与实跑代码一致。"""
    data = request_data or {}
    if not strategy and not data:
        return None
    out = dict(strategy) if strategy else {}
    for key in (
        'process_pipeline', 'python_presets', 'preset_functions',
        'flow', 'filter_rules_code', 'filter_mode', 'sample_code', 'python_code',
    ):
        val = data.get(key)
        if val is None or val == '' or val == []:
            continue
        out[key] = val
    return out or None
