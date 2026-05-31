"""从 Magic-Fox URL 发现项目下的数据集与训练快照。"""
import re
from urllib.parse import parse_qs, urlparse

from studio.sync import magic_fox_bridge as mf

MF_ORIGIN = 'https://www.ai.magic-fox.com'
_PAGE_TYPES = ('datasets', 'training', 'enhance', 'datasets/dataView')


def parse_magic_fox_url(url):
    """解析 Magic-Fox 前端 URL，返回 approach_id、subject_id、page。"""
    raw = str(url or '').strip()
    if not raw:
        raise ValueError('请提供 Magic-Fox URL')

    fragment = raw
    if '#' in raw:
        fragment = raw.split('#', 1)[1]
    elif raw.startswith('/'):
        fragment = raw.lstrip('/')

    path_part = fragment.split('?', 1)[0].strip('/')
    page = path_part or 'datasets'

    query = fragment.split('?', 1)[1] if '?' in fragment else ''
    if not query and '?' in raw:
        query = urlparse(raw).query
    params = parse_qs(query)

    def _int(key):
        vals = params.get(key) or params.get(key.lower()) or []
        for v in vals:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return None

    approach_id = _int('approachId') or _int('approach_id')
    subject_id = _int('subjectId') or _int('subject_id')
    dataset_id = _int('datasetId') or _int('dataset_id')

    if approach_id is None:
        raise ValueError('URL 中缺少 approachId，无法识别项目')

    return {
        'approach_id': approach_id,
        'subject_id': subject_id,
        'dataset_id': dataset_id,
        'page': page,
        'source_url': raw if raw.startswith('http') else f'{MF_ORIGIN}/#{fragment}',
    }


def build_page_urls(approach_id, subject_id=None):
    """根据 approach/subject 推导数据集、训练、增强页 URL。"""
    base = MF_ORIGIN
    q = f'approachId={int(approach_id)}'
    if subject_id is not None:
        q += f'&subjectId={int(subject_id)}'
    return {
        'datasets': f'{base}/#/datasets?{q}',
        'training': f'{base}/#/training?{q}',
        'enhance': f'{base}/#/enhance?{q}',
    }


def build_data_view_url(approach_id, dataset_id, subject_id=None):
    q = (
        f'approachId={int(approach_id)}'
        f'&datasetId={int(dataset_id)}'
        f'&enhanceDatasetId={int(dataset_id)}'
    )
    if subject_id is not None:
        q += f'&subjectId={int(subject_id)}'
    q += '&fuzzy_name=&sort_type=m_time'
    return f'{MF_ORIGIN}/#/datasets/dataView?{q}'


def build_snapshot_data_view_url(approach_id, snapshot_id, dataset_id, subject_id=None):
    """训练快照在平台的 dataView（enhanceDatasetId=快照 id）。"""
    q = (
        f'approachId={int(approach_id)}'
        f'&datasetId={int(dataset_id)}'
        f'&enhanceDatasetId={int(snapshot_id)}'
    )
    if subject_id is not None:
        q += f'&subjectId={int(subject_id)}'
    q += '&fuzzy_name=&sort_type=m_time'
    return f'{MF_ORIGIN}/#/datasets/dataView?{q}'


def _subject_id_from_url(url):
    if not url:
        return None
    from urllib.parse import parse_qs
    fragment = str(url).split('#', 1)[-1]
    query = fragment.split('?', 1)[-1] if '?' in fragment else ''
    params = parse_qs(query)
    for key in ('subjectId', 'subject_id'):
        vals = params.get(key) or []
        for v in vals:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return None


def _slug(name, max_len=56):
    s = re.sub(r'[^\w\u4e00-\u9fff\-]+', '_', str(name or '').strip())
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        return 'item'
    return s[:max_len]


def _api_session_and_headers(config=None):
    base, token = mf.get_api_token(config)
    m = mf.ensure_moli_module()
    session = m._api_session()
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    proxies = m._direct_proxies()
    return base.rstrip('/'), session, headers, proxies


def _check_api_response(data, context='Magic-Fox API'):
    code = data.get('code')
    if code == 200:
        return
    msg = data.get('message') or data.get('msg') or str(data)
    if code == 1000000001 or '权限' in str(msg):
        raise RuntimeError(
            f'{context} 权限不足（{msg}）。'
            '请在「设置 → Magic-Fox 训练平台」改用账号密码模式，或更换有项目访问权限的 Token。'
        )
    raise RuntimeError(f'{context} 失败: {msg}')


def fetch_all_datasets(approach_id, subject_id=None, config=None):
    base, session, headers, proxies = _api_session_and_headers(config)
    rows = []
    offset = 0
    limit = 100
    total = None
    while True:
        params = {'approach_id': int(approach_id), 'offset': offset, 'limit': limit}
        if subject_id is not None:
            params['subject_id'] = int(subject_id)
        r = session.get(f'{base}/datasets/page', headers=headers, params=params, proxies=proxies, timeout=60)
        r.raise_for_status()
        data = r.json()
        _check_api_response(data, '拉取数据集列表')
        payload = data.get('data') or {}
        chunk = payload.get('datasets') or []
        if total is None:
            total = int(payload.get('total_count') or 0)
        rows.extend(chunk)
        if not chunk or (total and len(rows) >= total):
            break
        offset += len(chunk)
    return _normalize_datasets(rows, approach_id, subject_id)


def fetch_all_snapshots(approach_id, config=None):
    base, session, headers, proxies = _api_session_and_headers(config)
    rows = []
    seen = set()
    offset = 0
    limit = 100
    total = None
    while True:
        params = {
            'approach_id': int(approach_id),
            'sort_type': 'm_time',
            'fuzzy_name': '',
            'offset': offset,
            'limit': limit,
        }
        r = session.get(
            f'{base}/generate_datasets/page',
            headers=headers,
            params=params,
            proxies=proxies,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        _check_api_response(data, '拉取训练快照列表')
        payload = data.get('data') or {}
        chunk = payload.get('gen_datasets') or []
        if total is None:
            total = int(payload.get('total_count') or 0)
        added = 0
        for item in chunk:
            eid = item.get('id')
            if eid in seen:
                continue
            seen.add(eid)
            rows.append(item)
            added += 1
        if not chunk or added == 0 or (total and len(rows) >= total):
            break
        offset += len(chunk)
    return _normalize_snapshots(rows)


def _normalize_datasets(rows, approach_id, subject_id):
    out = []
    for x in rows:
        if not isinstance(x, dict):
            continue
        did = x.get('id')
        if did is None:
            continue
        name = x.get('dataset_name') or x.get('show_name') or x.get('name') or f'dataset_{did}'
        out.append({
            'id': int(did),
            'name': str(name),
            'count': x.get('count') if x.get('count') is not None else x.get('total_count'),
            'm_time': x.get('m_time'),
            'data_view_url': build_data_view_url(approach_id, did, subject_id),
            'source_type': 'dataset',
            'source_id': int(did),
        })
    return out


def _normalize_snapshots(rows):
    out = []
    for x in rows:
        if not isinstance(x, dict):
            continue
        eid = x.get('id')
        if eid is None:
            continue
        name = x.get('show_name') or x.get('name') or f'snapshot_{eid}'
        out.append({
            'enhance_id': int(eid),
            'name': str(name),
            'dataset_id': x.get('dataset_id'),
            'count': x.get('count'),
            'm_time': x.get('m_time'),
            'source_type': 'snapshot',
            'source_id': int(eid),
        })
    return out


def discover_resources(
    url=None,
    approach_id=None,
    subject_id=None,
    include_datasets=True,
    include_snapshots=True,
    config=None,
):
    """发现 Magic-Fox 项目资源。"""
    parsed = {}
    if url:
        parsed = parse_magic_fox_url(url)
        approach_id = parsed['approach_id']
        if subject_id is None:
            subject_id = parsed.get('subject_id')
    if approach_id is None:
        raise ValueError('请提供 Magic-Fox URL 或 approach_id')

    approach_id = int(approach_id)
    if subject_id is not None:
        subject_id = int(subject_id)

    pages = build_page_urls(approach_id, subject_id)
    source_url = parsed.get('source_url') or pages['datasets']

    datasets = fetch_all_datasets(approach_id, subject_id, config) if include_datasets else []
    snapshots = fetch_all_snapshots(approach_id, config) if include_snapshots else []

    return {
        'approach_id': approach_id,
        'subject_id': subject_id,
        'source_url': source_url,
        'pages': pages,
        'datasets': datasets,
        'snapshots': snapshots,
        'counts': {
            'datasets': len(datasets),
            'snapshots': len(snapshots),
        },
    }


def import_discovered_items(
    items,
    *,
    project_id=None,
    project_name=None,
    approach_id=None,
    subject_id=None,
    training_page_url=None,
    local_root=None,
    write_db=True,
    strip_prefix=True,
    split_subdirs=False,
):
    """批量导入发现结果到 sync_project / sync_dataset。"""
    from studio.forge import forge_db

    if not items:
        raise ValueError('未选择任何数据集或快照')

    approach_id = int(approach_id) if approach_id is not None else None
    pages = build_page_urls(approach_id, subject_id) if approach_id else {}

    project = None
    if project_id:
        project = forge_db.get_sync_project(int(project_id))
        if not project:
            raise ValueError(f'项目不存在: {project_id}')
    else:
        name = str(project_name or '').strip() or (f'项目-{approach_id}' if approach_id else 'Magic-Fox 项目')
        payload = {
            'name': name,
            'approach_id': approach_id,
            'training_page_url': training_page_url or pages.get('training'),
            'local_root': local_root or (f'approach_{approach_id}' if approach_id else ''),
            'enabled': 1,
        }
        pid = forge_db.upsert_sync_project(payload)
        project = forge_db.get_sync_project(pid)

    prefix = str(local_root or project.get('local_root') or '').strip()
    if not prefix and approach_id:
        prefix = f'approach_{approach_id}'

    created = []
    updated = []
    for item in items:
        source_type = str(item.get('source_type') or 'dataset').strip().lower()
        if source_type not in ('dataset', 'snapshot'):
            continue
        source_id = item.get('source_id')
        if source_id is None:
            continue
        name = str(item.get('name') or f'{source_type}_{source_id}')
        sub = _slug(name)
        local_dir = str(item.get('local_dir') or '').strip()
        if not local_dir:
            local_dir = f'{prefix}/{sub}_{source_id}' if prefix else f'{sub}_{source_id}'

        payload = {
            'project_id': project['id'],
            'name': name,
            'source_type': source_type,
            'source_id': int(source_id),
            'data_view_url': item.get('data_view_url') or _default_data_view_url(
                source_type, approach_id, source_id, item.get('dataset_id'), subject_id,
            ),
            'local_dir': local_dir,
            'split_subdirs': 1 if split_subdirs else 0,
            'strip_prefix': 1 if strip_prefix else 0,
            'write_db': 1 if write_db else 0,
            'remote_count': item.get('count') or 0,
            'enabled': 1,
        }
        existing = [
            d for d in forge_db.list_sync_datasets(project_id=project['id'])
            if d.get('source_type') == source_type and int(d.get('source_id') or 0) == int(source_id)
        ]
        if existing:
            payload['id'] = existing[0]['id']
        did = forge_db.upsert_sync_dataset(payload)
        (updated if existing else created).append(forge_db.get_sync_dataset(did))

    return {
        'project': project,
        'created': created,
        'updated': updated,
        'imported_count': len(created) + len(updated),
    }


def _default_data_view_url(source_type, approach_id, source_id, dataset_id, subject_id):
    if not approach_id:
        return ''
    if source_type == 'dataset':
        return build_data_view_url(approach_id, source_id, subject_id)
    if source_type == 'snapshot' and dataset_id:
        return build_snapshot_data_view_url(approach_id, source_id, dataset_id, subject_id)
    return build_page_urls(approach_id, subject_id).get('enhance', '')
