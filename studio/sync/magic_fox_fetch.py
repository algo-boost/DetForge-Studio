"""Magic-Fox 数据集分页拉取（dataset_items/page）。"""
from typing import Any, Dict, List

from studio.sync import magic_fox_bridge as mf

# 平台 skip>0 时分页失效；单次 limit 可拉至 total_count（实测 6146 条一次返回）
_MAX_SINGLE_LIMIT = 100_000


def _page_params(dataset_id: int, limit: int, skip: int = 0) -> Dict[str, Any]:
    return {
        'dataset_id': int(dataset_id),
        'limit': int(limit),
        'skip': int(skip),
        'annotator_id': 0,
        'sort_type': 'm_time',
        'fuzzy_name': '',
    }


def fetch_dataset_items_all_pages(base_url: str, token: str, dataset_id: int) -> List[Dict[str, Any]]:
    """
    底库数据集全量：GET /dataset_items/page
    须带 annotator_id / sort_type；用 limit=total_count 一次取全（skip 分页不可用）。
    """
    m = mf.ensure_moli_module()
    base = base_url.rstrip('/')
    session = m._api_session()
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Origin': 'https://www.ai.magic-fox.com',
        'Referer': 'https://www.ai.magic-fox.com/',
    }
    proxies = m._direct_proxies()

    probe = session.get(
        f'{base}/dataset_items/page',
        params=_page_params(dataset_id, limit=100, skip=0),
        headers=headers,
        proxies=proxies,
        timeout=300,
    )
    probe.raise_for_status()
    probe_data = probe.json()
    if probe_data.get('code') != 200 and not probe_data.get('success'):
        msg = probe_data.get('msg') or probe_data.get('message') or probe_data
        raise RuntimeError(f'dataset_items/page 失败: {msg}')

    payload = probe_data.get('data') or {}
    total = int(payload.get('total_count') or 0)
    if total <= 0:
        return []

    if total <= 100:
        return list(payload.get('dataset_items') or [])

    fetch_limit = min(total, _MAX_SINGLE_LIMIT)
    if fetch_limit > 100:
        r = session.get(
            f'{base}/dataset_items/page',
            params=_page_params(dataset_id, limit=fetch_limit, skip=0),
            headers=headers,
            proxies=proxies,
            timeout=600,
        )
        r.raise_for_status()
        data = r.json()
        if data.get('code') != 200 and not data.get('success'):
            msg = data.get('msg') or data.get('message') or data
            raise RuntimeError(f'dataset_items/page 全量拉取失败: {msg}')
        items = (data.get('data') or {}).get('dataset_items') or []
    else:
        items = list(payload.get('dataset_items') or [])

    if total > _MAX_SINGLE_LIMIT:
        raise RuntimeError(
            f'数据集 {dataset_id} 共 {total} 条，超过单次上限 {_MAX_SINGLE_LIMIT}，请联系管理员扩展拉取策略'
        )
    if len(items) < total:
        raise RuntimeError(
            f'数据集 {dataset_id} 期望 {total} 条，实际仅拉取 {len(items)} 条，请检查平台 API'
        )
    return items
