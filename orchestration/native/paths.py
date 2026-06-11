"""部署目录与运行时路径（相对 APP_ROOT）。"""
from __future__ import annotations

from pathlib import Path

from studio.paths import APP_ROOT

DEPLOY_ROOT = Path(APP_ROOT) / 'deploy'
NATIVE_ROOT = DEPLOY_ROOT / 'native'
RUNTIME_ROOT = DEPLOY_ROOT / 'runtime'
VENDOR_ROOT = DEPLOY_ROOT / 'vendor'
FLOWS_ROOT = Path(APP_ROOT) / 'iisp-catalog' / 'pipelines' / 'kestra'

KESTRA_BIN = VENDOR_ROOT / 'kestra'          # Linux/macOS 原生可执行（含 shell 前导的 uber-jar）
KESTRA_JAR = VENDOR_ROOT / 'kestra.jar'      # 跨平台（Windows）：java -jar 运行
PLUGINS_DIR = VENDOR_ROOT / 'plugins'
CONFIG_TEMPLATE = NATIVE_ROOT / 'kestra-application.template.yml'
ENV_DEFAULTS_FILE = NATIVE_ROOT / 'env.defaults'
RENDERED_CONFIG = RUNTIME_ROOT / 'kestra-application.yml'

PID_KESTRA = RUNTIME_ROOT / 'kestra.pid'
PID_IISP = RUNTIME_ROOT / 'iisp.pid'
LOG_KESTRA = RUNTIME_ROOT / 'kestra.log'
LOG_IISP = RUNTIME_ROOT / 'iisp.log'
