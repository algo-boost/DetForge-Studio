"""Pipeline / Kestra Flow 统一校验（CLI + MCP）。"""
from __future__ import annotations

from orchestration.kestra_graph import parse_tool_id_from_uri
from orchestration.loader import load_pipeline_yaml, validate_pipeline


def _walk_kestra_tasks(tasks: list | None, visit) -> None:
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        visit(task)
        for key in ('tasks', 'then', 'else', 'finally', 'errors'):
            _walk_kestra_tasks(task.get(key), visit)
        cases = task.get('cases')
        if isinstance(cases, dict):
            for case_tasks in cases.values():
                _walk_kestra_tasks(case_tasks, visit)


def validate_kestra_flow(defn: dict, *, path: str = '') -> list[str]:
    errors: list[str] = []
    prefix = f'{path}: ' if path else ''
    if not defn.get('id'):
        errors.append(f'{prefix}缺少 id')
    if not defn.get('tasks'):
        errors.append(f'{prefix}缺少 tasks')
        return errors

    from capabilities.registry import init_registry

    reg = init_registry()
    known = {t['id'] for t in reg.list_tools()}

    def check_task(task: dict) -> None:
        tid = parse_tool_id_from_uri(task.get('uri'))
        if not tid:
            return
        if tid not in known:
            step = task.get('id') or '?'
            errors.append(f'{prefix}未注册工具 {tid}（步骤 {step}）')

    _walk_kestra_tasks(defn.get('tasks'), check_task)
    return errors


def validate_pipeline_any(defn: dict, *, path: str = '') -> list[str]:
    if defn.get('tasks'):
        return validate_kestra_flow(defn, path=path)
    return validate_pipeline(defn)


def validate_pipeline_path(path: str) -> dict:
    defn = load_pipeline_yaml(path)
    errors = validate_pipeline_any(defn, path=path)
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'id': defn.get('id'),
        'engine': 'kestra' if defn.get('tasks') else 'legacy',
    }


def validate_pipeline_text(yaml_text: str, *, path: str = '<inline>') -> dict:
    try:
        import yaml
    except ImportError as exc:
        return {'valid': False, 'errors': [f'需要 PyYAML: {exc}'], 'id': None, 'engine': None}
    defn = yaml.safe_load(yaml_text)
    if not isinstance(defn, dict):
        return {'valid': False, 'errors': ['Pipeline 必须是 YAML 对象'], 'id': None, 'engine': None}
    errors = validate_pipeline_any(defn, path=path)
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'id': defn.get('id'),
        'engine': 'kestra' if defn.get('tasks') else 'legacy',
    }
