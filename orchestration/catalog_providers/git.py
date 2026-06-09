"""Git Catalog Provider — GitHub / GitLab / Gitea / 内网 bare repo。"""
from __future__ import annotations

import os
import shutil
import subprocess

from orchestration.catalog_env import (
    CATALOG_CACHE_ROOT,
    catalog_local_path,
    catalog_ref,
    catalog_repo,
)
from orchestration.catalog_providers.base import CatalogFetchResult
from studio.paths import APP_ROOT


def _run_git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(
        ['git'] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or 'git failed').strip())
    return (proc.stdout or '').strip()


def _current_commit(repo_path: str) -> str:
    try:
        return _run_git(['rev-parse', 'HEAD'], repo_path)
    except Exception:
        return ''


class GitCatalogProvider:
    provider_id = 'git'

    def describe(self) -> dict:
        repo_url = catalog_repo()
        local_repo = catalog_local_path()
        if not repo_url:
            bundled = os.path.join(APP_ROOT, 'iisp-catalog')
            if os.path.isdir(bundled):
                return {
                    'provider': self.provider_id,
                    'remote': f'local:{bundled}',
                    'ref': catalog_ref(),
                    'local_path': bundled,
                }
        return {
            'provider': self.provider_id,
            'remote': repo_url or '',
            'ref': catalog_ref(),
            'local_path': local_repo,
        }

    def fetch(self, *, dry_run: bool = False) -> CatalogFetchResult:
        repo_url = catalog_repo()
        local_repo = catalog_local_path()
        ref = catalog_ref()

        if not repo_url:
            bundled = os.path.join(APP_ROOT, 'iisp-catalog')
            if os.path.isdir(bundled):
                return CatalogFetchResult(
                    source_path=bundled,
                    provider=self.provider_id,
                    remote=f'local:{bundled}',
                    ref=ref,
                    revision=_current_commit(bundled) if os.path.isdir(os.path.join(bundled, '.git')) else 'bundled',
                )
            raise RuntimeError('未配置 IISP_CATALOG_REPO，且无内置 iisp-catalog 目录')

        if dry_run:
            return CatalogFetchResult(
                source_path=local_repo,
                provider=self.provider_id,
                remote=repo_url,
                ref=ref,
            )

        os.makedirs(CATALOG_CACHE_ROOT, exist_ok=True)
        prev = _current_commit(local_repo) if os.path.isdir(os.path.join(local_repo, '.git')) else ''

        if not repo_url.startswith('local:'):
            if os.path.isdir(os.path.join(local_repo, '.git')):
                _run_git(['fetch', 'origin', ref], local_repo)
                _run_git(['checkout', ref], local_repo)
                _run_git(['pull', '--ff-only', 'origin', ref], local_repo)
            else:
                if os.path.isdir(local_repo):
                    shutil.rmtree(local_repo)
                _run_git(['clone', '--depth', '1', '--branch', ref, repo_url, local_repo], APP_ROOT)

        commit = _current_commit(local_repo)
        return CatalogFetchResult(
            source_path=local_repo,
            provider=self.provider_id,
            remote=repo_url,
            ref=ref,
            revision=commit,
            prev_revision=prev,
        )
