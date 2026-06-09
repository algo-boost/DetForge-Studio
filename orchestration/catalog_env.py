"""Catalog 环境变量与路径（Provider 无关）。"""
from __future__ import annotations

import os

from studio.paths import APP_ROOT

CATALOG_CACHE_ROOT = os.path.join(APP_ROOT, 'catalog_cache')
CATALOG_STRATEGIES_DIR = os.path.join(CATALOG_CACHE_ROOT, 'strategies')
CATALOG_PIPELINES_DIR = os.path.join(CATALOG_CACHE_ROOT, 'pipelines')
SYNC_LOG_FILE = os.path.join(CATALOG_CACHE_ROOT, 'sync_log.jsonl')


def catalog_provider_id() -> str:
    return (os.environ.get('IISP_CATALOG_PROVIDER') or 'git').strip().lower()


def catalog_repo() -> str:
    return (os.environ.get('IISP_CATALOG_REPO') or '').strip()


def catalog_ref() -> str:
    return (os.environ.get('IISP_CATALOG_REF') or 'main').strip()


def catalog_local_path() -> str:
    custom = (os.environ.get('IISP_CATALOG_LOCAL') or '').strip()
    if custom and os.path.isdir(custom):
        return custom
    return os.path.join(CATALOG_CACHE_ROOT, 'repo')
