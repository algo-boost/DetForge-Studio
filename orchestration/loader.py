"""Pipeline YAML 加载与校验。"""
from __future__ import annotations

import os
from pathlib import Path

from orchestration.catalog_env import CATALOG_PIPELINES_DIR
from studio.paths import APP_ROOT

try:
    import yaml
except ImportError:
    yaml = None


def pipeline_search_dirs() -> list[str]:
    dirs = [
        os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'kestra'),
        os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'legacy'),
        CATALOG_PIPELINES_DIR,
        os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines'),
        os.path.join(APP_ROOT, 'workflows'),
    ]
    return [d for d in dirs if os.path.isdir(d)]


def load_pipeline_yaml(path: str) -> dict:
    if yaml is None:
        raise RuntimeError('需要 PyYAML: pip install pyyaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError('Pipeline 必须是 YAML 对象')
    return data


def validate_pipeline(defn: dict) -> list[str]:
    errors: list[str] = []
    if not defn.get('id'):
        errors.append('缺少 id')
    nodes = defn.get('nodes') or defn.get('steps') or []
    if not nodes:
        errors.append('缺少 nodes/steps')
    ids = set()
    for n in nodes:
        nid = n.get('id')
        if not nid:
            errors.append('节点缺少 id')
            continue
        if nid in ids:
            errors.append(f'重复节点 id: {nid}')
        ids.add(nid)
        tool = n.get('tool') or n.get('kind')
        if not tool:
            errors.append(f'节点 {nid} 缺少 tool/kind')
    edges = defn.get('edges') or []
    requires = [n.get('requires') or [] for n in nodes]
    if not edges and not any(requires):
        pass
    return errors


def discover_kestra_flows() -> list[dict]:
    """列出 Kestra Flow YAML（tasks 格式，不做 nodes 校验）。"""
    root = os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'kestra')
    if not os.path.isdir(root):
        return []
    found: list[dict] = []
    for path in Path(root).glob('*.yaml'):
        try:
            data = load_pipeline_yaml(str(path))
        except Exception as exc:
            found.append({
                'id': path.stem,
                '_path': str(path),
                '_valid': False,
                '_errors': [str(exc)],
            })
            continue
        if not data.get('tasks'):
            continue
        found.append({
            'id': data.get('id') or path.stem,
            'namespace': data.get('namespace') or 'iisp',
            'description': data.get('description') or '',
            'engine': 'kestra',
            '_path': str(path),
            '_valid': True,
            '_errors': [],
        })
    return sorted(found, key=lambda x: str(x.get('id') or ''))


def discover_pipelines() -> list[dict]:
    found = []
    for root in pipeline_search_dirs():
        for path in Path(root).rglob('*.yaml'):
            if path.is_file():
                try:
                    data = load_pipeline_yaml(str(path))
                    data['_path'] = str(path)
                    errs = validate_pipeline(data)
                    data['_valid'] = len(errs) == 0
                    data['_errors'] = errs
                    found.append(data)
                except Exception as e:
                    found.append({
                        'id': path.stem,
                        '_path': str(path),
                        '_valid': False,
                        '_errors': [str(e)],
                    })
        for path in Path(root).rglob('*.yml'):
            if path.is_file():
                try:
                    data = load_pipeline_yaml(str(path))
                    data['_path'] = str(path)
                    found.append(data)
                except Exception:
                    pass
    return found


def pipeline_to_workflow_definition(defn: dict) -> dict:
    """将 Catalog Pipeline YAML 转为 workflow template definition。"""
    nodes = defn.get('nodes') or []
    steps = []
    for n in nodes:
        step = {
            'id': n['id'],
            'kind': n.get('tool') or n.get('kind'),
            'params': n.get('params') or {},
        }
        if n.get('requires'):
            step['requires'] = n['requires']
        if n.get('when'):
            step['when'] = n['when']
        steps.append(step)
    return {
        'params_schema': defn.get('params_schema') or defn.get('params') or {},
        'steps': steps,
        'edges': defn.get('edges') or [],
    }
