"""从 deploy/native/env.defaults 与环境变量读取部署默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from orchestration.native.paths import ENV_DEFAULTS_FILE


@dataclass(frozen=True)
class NativeDeployDefaults:
    kestra_version: str
    kestra_port: int
    iisp_port: int
    kestra_user: str
    kestra_password: str
    env_iisp_base: str
    kestra_mysql_database: str
    java_opts: str

    @property
    def kestra_url(self) -> str:
        return f'http://127.0.0.1:{self.kestra_port}'

    @property
    def iisp_url(self) -> str:
        return f'http://127.0.0.1:{self.iisp_port}'


def _parse_defaults_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_DEFAULTS_FILE.is_file():
        return out
    for line in ENV_DEFAULTS_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        out[key.strip()] = val.strip()
    return out


def load_defaults() -> NativeDeployDefaults:
    file_vals = _parse_defaults_file()

    def _get(key: str, env_key: str, fallback: str) -> str:
        return os.environ.get(env_key) or file_vals.get(key) or fallback

    return NativeDeployDefaults(
        kestra_version=_get('KESTRA_VERSION', 'KESTRA_VERSION', '1.3.21'),
        kestra_port=int(_get('KESTRA_PORT', 'KESTRA_PORT', '8080')),
        iisp_port=int(_get('IISP_PORT', 'IISP_PORT', '5050')),
        kestra_user=_get('KESTRA_USER', 'KESTRA_USER', 'admin@kestra.io'),
        kestra_password=_get('KESTRA_PASSWORD', 'KESTRA_PASSWORD', 'Admin1234'),
        env_iisp_base=_get('ENV_IISP_BASE', 'ENV_IISP_BASE', 'http://127.0.0.1:5050'),
        kestra_mysql_database=_get('KESTRA_MYSQL_DATABASE', 'KESTRA_MYSQL_DATABASE', 'kestra'),
        java_opts=_get('JAVA_OPTS', 'JAVA_OPTS', '-Xms512m -Xmx4096m -XX:MaxRAMPercentage=75.0'),
    )
