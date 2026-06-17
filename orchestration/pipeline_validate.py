"""Pipeline 统一校验（CLI + MCP）。"""
from __future__ import annotations

from orchestration.loader import load_pipeline_yaml, validate_pipeline


def validate_pipeline_any(defn: dict, *, path: str = '') -> list[str]:
    prefix = f'{path}: ' if path else ''
    if defn.get('tasks'):
        return [f'{prefix}不再支持 Kestra tasks 格式，请使用 legacy nodes/steps 或组合编排']
    return validate_pipeline(defn)


def validate_pipeline_path(path: str) -> dict:
    defn = load_pipeline_yaml(path)
    errors = validate_pipeline_any(defn, path=path)
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'id': defn.get('id'),
        'engine': 'legacy',
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
        'engine': 'legacy',
    }
