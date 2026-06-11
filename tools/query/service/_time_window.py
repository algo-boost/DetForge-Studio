"""time_window / env 解析（execute 与 preview 共用）。"""
from __future__ import annotations

from studio.curation.replay_run_service import resolve_time_window


def build_query_context(params: dict) -> dict:
    tw = params.get('time_window')
    if isinstance(tw, str):
        try:
            import json
            tw = json.loads(tw)
        except (TypeError, ValueError):
            tw = {'preset': tw}
    if not isinstance(tw, dict):
        tw = {}
    start, end = resolve_time_window(tw)
    ctx = {'START_TIME': start, 'END_TIME': end}
    env = params.get('env') or {}
    if isinstance(env, dict):
        ctx.update(env)
    return ctx
