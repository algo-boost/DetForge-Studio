"""工具集成配置 — embedded / remote / standalone（Query、viz、unify 等共用）。"""
from __future__ import annotations

import os
from typing import Any

VALID_MODES = frozenset({'embedded', 'remote', 'standalone'})

# tool_id → 默认挂载与 config 键
TOOL_SPECS: dict[str, dict[str, Any]] = {
    'query': {
        'config_key': 'query_tool',
        'mount_prefix': '/tools/query',
        'standalone_port_env': 'QUERY_TOOL_PORT',
        'standalone_port_default': 6021,
        'hash_routing': True,
    },
    'viz': {
        'config_key': 'viz_tool',
        'mount_prefix': '/viz',
        'standalone_port_env': 'VIZ_TOOL_PORT',
        'standalone_port_default': 6010,
        'hash_routing': False,
    },
    'coco-visualizer': {
        'config_key': 'viz_tool',
        'mount_prefix': '/viz',
        'standalone_port_env': 'VIZ_TOOL_PORT',
        'standalone_port_default': 6010,
        'hash_routing': False,
    },
    'unify': {
        'config_key': 'unify_tool',
        'mount_prefix': '/unify',
        'standalone_port_env': 'UNIFY_TOOL_PORT',
        'standalone_port_default': 6022,
        'hash_routing': False,
    },
}


def tool_spec(tool_id: str) -> dict[str, Any]:
    tid = str(tool_id or '').strip().lower()
    if tid not in TOOL_SPECS:
        key = tid.replace('-', '_')
        return {
            'config_key': f'{key}_tool',
            'mount_prefix': f'/tools/{tid}',
            'standalone_port_env': f'{key.upper()}_TOOL_PORT',
            'standalone_port_default': 6020,
            'hash_routing': True,
        }
    return TOOL_SPECS[tid]


def config_key_for_tool(tool_id: str) -> str:
    return str(tool_spec(tool_id).get('config_key') or f'{tool_id}_tool')


def get_tool_config(tool_id: str, config=None) -> dict:
    if config is None:
        from server.core import load_config
        config = load_config()
    key = config_key_for_tool(tool_id)
    raw = config.get(key)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def get_integration_mode(tool_id: str, config=None) -> str:
    mode = str(get_tool_config(tool_id, config).get('integration') or 'embedded').strip().lower()
    return mode if mode in VALID_MODES else 'embedded'


def get_remote_url(tool_id: str, config=None) -> str:
    return str(get_tool_config(tool_id, config).get('remote_url') or '').strip().rstrip('/')


def get_standalone_url(tool_id: str, config=None) -> str:
    cfg = get_tool_config(tool_id, config)
    explicit = str(cfg.get('standalone_url') or '').strip().rstrip('/')
    if explicit:
        return explicit
    spec = tool_spec(tool_id)
    port = int(os.environ.get(spec['standalone_port_env'], spec['standalone_port_default']))
    return f'http://127.0.0.1:{port}'


def build_integration_payload(
    tool_id: str,
    *,
    config=None,
    extra: dict | None = None,
) -> dict:
    """Shell / ToolHost 统一 status 形状。"""
    spec = tool_spec(tool_id)
    integration = get_integration_mode(tool_id, config)
    remote_url = get_remote_url(tool_id, config)
    standalone_url = get_standalone_url(tool_id, config)
    payload = {
        'success': True,
        'tool_id': tool_id,
        'integration': integration,
        'remote_url': remote_url or None,
        'standalone_url': standalone_url or None,
        'mount_prefix': spec.get('mount_prefix'),
        'hash_routing': bool(spec.get('hash_routing')),
    }
    if extra:
        payload.update(extra)
    return payload


def query_integration_extra() -> dict:
    from server.query_mount import (
        is_query_tool_ui_available,
        is_query_tool_ui_mounted,
    )
    from tools.query.ui_server import is_query_tool_ui_built, resolve_query_tool_ui_root

    return {
        'mount_available': is_query_tool_ui_available(),
        'built': is_query_tool_ui_built(),
        'mount_ready': is_query_tool_ui_mounted(),
        'available': is_query_tool_ui_available(),
        'mounted': is_query_tool_ui_mounted(),
        'ui_root': resolve_query_tool_ui_root() or None,
        'invoke': '/v1/tools/query/invoke',
    }


def viz_integration_extra() -> dict:
    from server.viz_mount import is_viz_available, is_viz_mounted

    return {
        'available': is_viz_available(),
        'mounted': is_viz_mounted(),
        'mount_ready': is_viz_mounted(),
    }


def unify_integration_extra() -> dict:
    from server.unify_mount import is_unify_available, is_unify_mounted

    return {
        'available': is_unify_available(),
        'mounted': is_unify_mounted(),
        'mount_ready': is_unify_mounted(),
        'viewer_path': '/online-predict',
    }


_INTEGRATION_EXTRA = {
    'query': query_integration_extra,
    'viz': viz_integration_extra,
    'coco-visualizer': viz_integration_extra,
    'unify': unify_integration_extra,
}


def integration_extra_for(tool_id: str) -> dict:
    fn = _INTEGRATION_EXTRA.get(str(tool_id or '').strip().lower())
    return fn() if fn else {}
