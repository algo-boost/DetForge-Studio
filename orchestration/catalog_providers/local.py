"""本地目录 / NAS 共享路径 Catalog Provider。"""
from __future__ import annotations

import os

from orchestration.catalog_providers.base import CatalogFetchResult


class LocalCatalogProvider:
    provider_id = 'local'

    def __init__(self, path: str):
        self._path = path.strip()

    def describe(self) -> dict:
        return {
            'provider': self.provider_id,
            'remote': f'file:{self._path}',
            'ref': '-',
            'local_path': self._path,
        }

    def fetch(self, *, dry_run: bool = False) -> CatalogFetchResult:
        if not self._path or not os.path.isdir(self._path):
            raise RuntimeError(f'IISP_CATALOG_LOCAL 不是有效目录: {self._path}')
        return CatalogFetchResult(
            source_path=self._path,
            provider=self.provider_id,
            remote=f'file:{self._path}',
            ref='-',
            revision='local',
        )
