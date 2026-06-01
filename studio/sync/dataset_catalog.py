"""Magic-Fox 数据集目录：内置 catalog + config 覆盖（供受限 Token 探测发现）。"""
import json
from pathlib import Path

_CATALOGS_DIR = Path(__file__).resolve().parent / 'catalogs'


def normalize_catalog_entry(entry):
    if not isinstance(entry, dict):
        return None
    did = entry.get('id') or entry.get('dataset_id') or entry.get('source_id')
    try:
        did = int(did)
    except (TypeError, ValueError):
        return None
    name = str(entry.get('name') or entry.get('dataset_name') or f'dataset_{did}').strip()
    return {'id': did, 'name': name}


def load_builtin_catalog(approach_id):
    path = _CATALOGS_DIR / f'approach_{int(approach_id)}.json'
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        norm = normalize_catalog_entry(item)
        if norm:
            out.append(norm)
    return out


def load_config_catalog(approach_id, config=None):
    from server.core import load_config
    cfg = config or load_config()
    raw = cfg.get('magic_fox_dataset_catalog') or {}
    if not isinstance(raw, dict):
        return []
    entries = raw.get(str(int(approach_id))) or raw.get(int(approach_id)) or []
    if not isinstance(entries, list):
        return []
    out = []
    for item in entries:
        norm = normalize_catalog_entry(item)
        if norm:
            out.append(norm)
    return out


def merge_catalog_entries(*lists):
    seen = set()
    out = []
    for items in lists:
        for item in items or []:
            did = int(item['id'])
            if did in seen:
                continue
            seen.add(did)
            out.append({'id': did, 'name': item['name']})
    return out


def resolve_dataset_candidates(approach_id, config=None, extra_ids=None, url_dataset_id=None):
    """合并内置 catalog、config catalog、URL/请求中的 dataset ID。"""
    builtin = load_builtin_catalog(approach_id)
    configured = load_config_catalog(approach_id, config)
    extras = []
    for raw in (extra_ids or []):
        norm = normalize_catalog_entry({'id': raw})
        if norm:
            extras.append(norm)
    if url_dataset_id is not None:
        norm = normalize_catalog_entry({'id': url_dataset_id})
        if norm:
            extras.append(norm)
    return merge_catalog_entries(configured, builtin, extras)
