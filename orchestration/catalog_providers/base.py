"""Catalog 配置源抽象 — 默认 Git（含 GitHub），可迁移至内网 Git / 本地目录 / Nacos 等。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CatalogFetchResult:
    """一次 pull 后的本地快照目录（含 strategies/、pipelines/ 等）。"""
    source_path: str
    provider: str
    remote: str
    ref: str
    revision: str = ''
    prev_revision: str = ''


class CatalogProvider(Protocol):
    provider_id: str

    def describe(self) -> dict: ...

    def fetch(self, *, dry_run: bool = False) -> CatalogFetchResult: ...
