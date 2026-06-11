"""Tool Contract v1 — CLI stdin/stdout 与退出码。"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Type

from capabilities.base import Artifact, Capability, CapabilityResult, RunContext
from server.gateway.contract import result_to_v1

_OK_STATUSES = frozenset({'done', 'skipped', 'waiting_human'})


def read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        return {}
    return json.loads(raw)


def write_result(result: CapabilityResult) -> int:
    print(json.dumps(result_to_v1(result), ensure_ascii=False))
    return 0 if result.status in _OK_STATUSES else 1


def run_capability_main(capability_cls: Type[Capability]) -> None:
    payload = read_payload()
    ctx = RunContext(
        run_id=payload.get('run_id'),
        step_id=payload.get('step_id'),
        params=payload.get('params') or {},
        inputs=payload.get('inputs') or {},
    )
    result = capability_cls().execute(ctx)
    raise SystemExit(write_result(result))


def artifacts_from_outputs(outputs: dict, kinds: list[str] | None = None) -> list[Artifact]:
    arts: list[Artifact] = []
    task_id = outputs.get('task_id')
    if task_id and (not kinds or 'csv' in kinds):
        arts.append(Artifact(kind='csv', uri=f'exports/{task_id}/result.csv', meta={'task_id': task_id}))
    return arts
