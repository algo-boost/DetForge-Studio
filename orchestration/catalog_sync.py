"""Catalog 同步到本地 catalog_cache（Provider 可插拔）。"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from orchestration.catalog_env import (
    CATALOG_CACHE_ROOT,
    CATALOG_PIPELINES_DIR,
    CATALOG_STRATEGIES_DIR,
    SYNC_LOG_FILE,
)
from orchestration.catalog_providers import get_catalog_provider

logger = logging.getLogger('iisp.catalog.sync')

# 兼容旧 import
from orchestration.catalog_env import catalog_local_path, catalog_ref, catalog_repo  # noqa: F401


def _append_sync_log(entry: dict) -> None:
    os.makedirs(CATALOG_CACHE_ROOT, exist_ok=True)
    with open(SYNC_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _copy_tree(src: str, dst: str) -> int:
    if not os.path.isdir(src):
        return 0
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return sum(1 for _ in Path(dst).rglob('*') if _.is_file())


def sync_catalog(*, dry_run: bool = False) -> dict:
    """从 Catalog Provider 拉取 strategies/ 与 pipelines/ 到本地缓存。"""
    started = datetime.utcnow().isoformat() + 'Z'
    provider = get_catalog_provider()
    meta = provider.describe()

    if dry_run:
        return {
            'success': True,
            'dry_run': True,
            'provider': meta.get('provider'),
            'repo': meta.get('remote'),
            'ref': meta.get('ref'),
            'local_path': meta.get('local_path'),
            'started_at': started,
        }

    try:
        fetched = provider.fetch(dry_run=False)
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'provider': meta.get('provider'),
            'started_at': started,
        }

    os.makedirs(CATALOG_CACHE_ROOT, exist_ok=True)
    source = fetched.source_path
    n_strategies = _copy_tree(os.path.join(source, 'strategies'), CATALOG_STRATEGIES_DIR)
    n_pipelines = _copy_tree(os.path.join(source, 'pipelines'), CATALOG_PIPELINES_DIR)

    summary = {
        'success': True,
        'provider': fetched.provider,
        'repo': fetched.remote,
        'ref': fetched.ref,
        'commit': fetched.revision,
        'prev_commit': fetched.prev_revision,
        'strategies_files': n_strategies,
        'pipelines_files': n_pipelines,
        'started_at': started,
        'finished_at': datetime.utcnow().isoformat() + 'Z',
    }
    _append_sync_log(summary)
    try:
        from studio.forge import forge_db
        forge_db.insert_catalog_sync_log(summary)
    except Exception as e:
        logger.warning('写入 catalog_sync_log 表失败: %s', e)
    return summary


def list_sync_logs(limit: int = 20) -> list[dict]:
    if not os.path.isfile(SYNC_LOG_FILE):
        return []
    lines = []
    with open(SYNC_LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def catalog_status() -> dict:
    """当前 Provider 与缓存概况（供 API / UI）。"""
    provider = get_catalog_provider()
    meta = provider.describe()
    return {
        **meta,
        'cache_root': CATALOG_CACHE_ROOT,
        'strategies_cached': os.path.isdir(CATALOG_STRATEGIES_DIR),
        'pipelines_cached': os.path.isdir(CATALOG_PIPELINES_DIR),
    }
