"""Tool Contract v1 响应格式（Kestra / 编排侧）。"""
from __future__ import annotations

from dataclasses import asdict

from capabilities.base import Artifact, CapabilityResult


def result_to_v1(result: CapabilityResult) -> dict:
    artifacts = []
    for item in result.artifacts or []:
        if isinstance(item, Artifact):
            artifacts.append(asdict(item))
        elif isinstance(item, dict):
            artifacts.append(item)
        else:
            artifacts.append({'kind': 'unknown', 'uri': str(item), 'meta': {}})
    return {
        'status': result.status,
        'outputs': dict(result.outputs or {}),
        'artifacts': artifacts,
        'error': result.reason if result.status == 'failed' else None,
    }


def failed_v1(message: str, *, status: str = 'failed') -> dict:
    return {
        'status': status,
        'outputs': {},
        'artifacts': [],
        'error': message,
    }
