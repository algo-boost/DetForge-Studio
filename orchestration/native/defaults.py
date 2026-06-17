"""从 deploy/native/env.defaults 与环境变量读取部署默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from orchestration.native.paths import ENV_DEFAULTS_FILE


@dataclass(frozen=True)
class NativeDeployDefaults:
    iisp_port: int
    env_iisp_base: str

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
        iisp_port=int(_get('IISP_PORT', 'IISP_PORT', '5050')),
        env_iisp_base=_get('ENV_IISP_BASE', 'ENV_IISP_BASE', 'http://127.0.0.1:5050'),
    )
