"""已合并至 tools.query.service — 保留模块路径兼容。"""
from tools.query.service.dispatch import dispatch


def run(params, *, run_id=None):
    return dispatch(params, run_id=run_id)


__all__ = ['run']
