"""项目根目录与打包路径（开发目录 / PyInstaller 目录版）。"""
from __future__ import annotations

import os
import sys

_BUNDLE_TOOL_NAMES = {
    'coco': 'COCOVisualizer',
    'detunify': 'DetUnify-Studio',
}

# packages/ 下 git submodule 目录名（IISP 仓内集成）
_PACKAGE_TOOL_DIRS = {
    'coco': 'coco-visualizer',
    'detunify': 'detunify',
}


def _resolve_app_root() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_root() -> str:
    """只读打包资源根（PyInstaller _MEIPASS 或开发树根）。"""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', _resolve_app_root())
    return _resolve_app_root()


APP_ROOT = _resolve_app_root()
PROJECT_ROOT = APP_ROOT
CONFIG_FILE = os.path.join(APP_ROOT, 'config.json')


def resource_path(*parts: str) -> str:
    return os.path.join(resource_root(), *parts)


def resolve_config_path(path: str, *, must_exist: bool = False) -> str:
    """将 config 中的相对路径解析为绝对路径（相对 APP_ROOT）。"""
    p = str(path or '').strip()
    if not p:
        return ''
    out = os.path.normpath(p if os.path.isabs(p) else os.path.join(APP_ROOT, p))
    if must_exist and not (os.path.isdir(out) or os.path.isfile(out)):
        return ''
    return out


def app_temp_dir(config=None) -> str:
    """应用临时目录：优先 PC_TEMP_DIR / config.temp_dir，否则 exports/.tmp（避免系统 %TEMP% 占 C 盘）。"""
    env_dir = (os.environ.get('PC_TEMP_DIR') or '').strip()
    if env_dir:
        out = os.path.normpath(env_dir)
    else:
        if config is None:
            from server.core import load_config
            config = load_config()
        cfg_dir = resolve_config_path(str(config.get('temp_dir') or '').strip())
        out = cfg_dir if cfg_dir else os.path.join(APP_ROOT, 'exports', '.tmp')
    os.makedirs(out, exist_ok=True)
    return out


def bundled_tool_dir(name: str) -> str:
    """发行包内 tools/<name>（如 COCOVisualizer、DetUnify-Studio）。"""
    root = os.path.join(APP_ROOT, 'tools', name)
    return os.path.normpath(root) if os.path.isdir(root) else ''


def package_tool_dir(kind: str) -> str:
    """IISP 仓内 packages/<submodule>（git submodule 集成路径）。"""
    folder = _PACKAGE_TOOL_DIRS.get(kind, '')
    if not folder:
        return ''
    root = os.path.join(APP_ROOT, 'packages', folder)
    return os.path.normpath(root) if os.path.isdir(root) else ''


def _first_existing_dir(*candidates: str) -> str:
    for path in candidates:
        if path and os.path.isdir(path):
            return path
    return ''


def default_coco_visualizer_root() -> str:
    return _first_existing_dir(
        package_tool_dir('coco'),
        bundled_tool_dir(_BUNDLE_TOOL_NAMES['coco']),
        os.path.normpath(os.path.join(APP_ROOT, '..', _BUNDLE_TOOL_NAMES['coco'])),
    )


def default_detunify_studio_root() -> str:
    return _first_existing_dir(
        package_tool_dir('detunify'),
        bundled_tool_dir(_BUNDLE_TOOL_NAMES['detunify']),
        os.path.normpath(os.path.join(APP_ROOT, '..', _BUNDLE_TOOL_NAMES['detunify'])),
    )
