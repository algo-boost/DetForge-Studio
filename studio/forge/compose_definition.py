"""组合编排 definition 构建（与 frontend composeModules 对齐）。"""
from __future__ import annotations

from studio.forge.compose_flow import (
    COMPOSE_MODULES,
    DEFAULT_MODULE_IDS,
    build_compose_definition,
    build_linear_compose_definition,
    default_step_instances,
    encode_step_id,
    is_compose_flow_id,
    normalize_flow_id,
    reindex_step_instances,
)

DEFAULT_COMPOSE_PIPELINE = [
    {'uid': 'flow_draft.s01', 'module_id': 'query'},
    {'uid': 'flow_draft.s02', 'module_id': 'predict'},
]

__all__ = [
    'COMPOSE_MODULES',
    'DEFAULT_COMPOSE_PIPELINE',
    'DEFAULT_MODULE_IDS',
    'build_compose_definition',
    'build_linear_compose_definition',
    'default_step_instances',
    'encode_step_id',
    'is_compose_flow_id',
    'normalize_flow_id',
    'reindex_step_instances',
]
