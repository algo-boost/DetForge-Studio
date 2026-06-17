"""部署目录与运行时路径（相对 APP_ROOT）。"""
from __future__ import annotations

from pathlib import Path

from studio.paths import APP_ROOT

DEPLOY_ROOT = Path(APP_ROOT) / 'deploy'
NATIVE_ROOT = DEPLOY_ROOT / 'native'
RUNTIME_ROOT = DEPLOY_ROOT / 'runtime'
ENV_DEFAULTS_FILE = NATIVE_ROOT / 'env.defaults'

PID_IISP = RUNTIME_ROOT / 'iisp.pid'
LOG_IISP = RUNTIME_ROOT / 'iisp.log'
