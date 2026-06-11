"""Legacy REST → query dispatch 薄代理；保持 {success, data} 响应形状。"""
from __future__ import annotations

from tools.query.service.dispatch import dispatch


def _invoke(action: str, params: dict | None = None) -> dict:
    return dispatch({'action': action, **(params or {})})


def _err(message: str, status: int = 400) -> tuple[dict, int]:
    return {'success': False, 'error': message}, status


def handle_post_query(data: dict | None) -> tuple[dict, int]:
    """POST /api/query — 同步 SQL 查询。"""
    try:
        out = _invoke('run', dict(data or {}))
        status = out.pop('status_code', 200 if out.get('success') else 500)
        return out, int(status)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_create_query_job(data: dict | None) -> tuple[dict, int]:
    try:
        payload = dict(data or {})
        label = (payload.pop('label', None) or payload.pop('strategy_name', None) or '').strip()
        if not str(payload.get('sql', '')).strip():
            return _err('SQL 查询语句不能为空', 400)
        out = _invoke('job.submit', {'query': payload, 'label': label})
        return {
            'success': True,
            'query_job_id': out['query_job_id'],
            'job': out['job'],
        }, 200
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(exc)}, 500


def handle_list_query_jobs(limit: int = 30, active_only: bool = False) -> tuple[dict, int]:
    try:
        out = _invoke('job.list', {'limit': limit, 'active_only': active_only})
        return {'success': True, 'jobs': out.get('jobs') or []}, 200
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_get_query_job(job_id: str) -> tuple[dict, int]:
    try:
        out = _invoke('job.get', {'job_id': job_id})
        return {'success': True, 'job': out['job']}, 200
    except ValueError:
        return _err('任务不存在', 404)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_get_query_task(task_id: str) -> tuple[dict, int]:
    try:
        out = _invoke('task.get', {'task_id': task_id})
        body = {'success': True}
        for key, val in out.items():
            if key not in ('action',):
                body[key] = val
        return body, 200
    except ValueError:
        return _err('任务不存在或缺少 result.csv', 404)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(exc)}, 500


def handle_list_strategies() -> tuple[dict, int]:
    try:
        out = _invoke('strategy.list', {'full': True})
        return {'success': True, 'data': out.get('strategies') or []}, 200
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_get_strategy(strategy_id: str) -> tuple[dict, int]:
    try:
        out = _invoke('strategy.get', {'strategy_id': strategy_id})
        return {'success': True, 'data': out['strategy']}, 200
    except ValueError:
        return _err('策略不存在', 404)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_get_strategy_variables(strategy_id: str) -> tuple[dict, int]:
    try:
        out = _invoke('strategy.variables', {'strategy_id': strategy_id})
        data = {k: v for k, v in out.items() if k not in ('action', 'strategy_id')}
        return {'success': True, 'data': data}, 200
    except ValueError as exc:
        if '不存在' in str(exc):
            return _err(str(exc), 404)
        return _err(str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_save_strategy(data: dict | None) -> tuple[dict, int]:
    try:
        payload = dict(data or {})
        sid = str(payload.get('id') or '').strip()
        if not sid:
            return _err('id 不能为空', 400)
        _invoke('strategy.save', {'strategy': payload})
        return {'success': True, 'id': sid}, 200
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_delete_strategy(strategy_id: str) -> tuple[dict, int]:
    try:
        _invoke('strategy.delete', {'strategy_id': strategy_id})
        return {'success': True}, 200
    except ValueError as exc:
        msg = str(exc)
        if '不存在' in msg:
            return _err(msg, 404)
        return _err(msg, 404)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_execute_strategy(data: dict | None) -> tuple[dict, int]:
    try:
        out = _invoke('strategy.execute', dict(data or {}))
        return {
            'success': True,
            'data': out.get('data', []),
            'count': out.get('count', 0),
            'task_id': out.get('task_id'),
            'sample_size': out.get('sample_size'),
            'random_seed': out.get('random_seed'),
            'rows_before_sample': out.get('rows_before_sample'),
            'post_sample_skipped': out.get('post_sample_skipped'),
            'input_rows': out.get('input_rows'),
            'input_cols': out.get('input_cols'),
            'output_rows': out.get('rows_before_sample'),
            'filter_mode': out.get('filter_mode', ''),
            'console_output': out.get('console_output'),
            'execution_time': out.get('execution_time'),
        }, 200
    except ValueError as exc:
        return _err(str(exc), 404)
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500


def handle_compile_strategy_pipeline(data: dict | None) -> tuple[dict, int]:
    try:
        body = dict(data or {})
        out = _invoke('strategy.compile_pipeline', body)
        return {'success': True, 'data': out.get('data')}, 200
    except Exception as exc:  # noqa: BLE001
        return {'success': False, 'error': str(exc)}, 500
