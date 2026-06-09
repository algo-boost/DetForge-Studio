"""Catalog Provider 注册表。"""
from __future__ import annotations

from orchestration.catalog_env import catalog_local_path, catalog_provider_id
from orchestration.catalog_providers.base import CatalogProvider


def get_catalog_provider() -> CatalogProvider:
    kind = catalog_provider_id()
    if kind == 'git':
        from orchestration.catalog_providers.git import GitCatalogProvider
        return GitCatalogProvider()
    if kind == 'local':
        from orchestration.catalog_providers.local import LocalCatalogProvider
        return LocalCatalogProvider(catalog_local_path())
    if kind == 'nacos':
        raise NotImplementedError(
            'IISP_CATALOG_PROVIDER=nacos 尚未实现；请先用 git 或 local，见 docs/CATALOG_CENTER.md'
        )
    if kind == 'bundle':
        raise NotImplementedError(
            'IISP_CATALOG_PROVIDER=bundle 尚未实现；请先用 git 或 local'
        )
    raise ValueError(f'未知 IISP_CATALOG_PROVIDER: {kind}')
