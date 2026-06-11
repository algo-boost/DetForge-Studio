"""查询域 service 包。"""
from tools.query.service.dispatch import dispatch, resolve_action, run

__all__ = ['dispatch', 'resolve_action', 'run']
