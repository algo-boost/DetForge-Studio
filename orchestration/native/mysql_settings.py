"""从 config.json 解析 Kestra 所用 MySQL 连接（与 IISP 同实例、独立库）。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from server.core import load_config


@dataclass(frozen=True)
class KestraMysqlSettings:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def jdbc_url(self) -> str:
        return (
            f'jdbc:mysql://{self.host}:{self.port}/{self.database}'
            '?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC'
        )


def resolve_mysql_settings(database: str | None = None) -> KestraMysqlSettings:
    cfg = load_config()
    db_name = (
        database
        or cfg.get('kestra_database')
        or os.environ.get('KESTRA_MYSQL_DATABASE')
        or 'kestra'
    )
    return KestraMysqlSettings(
        host=str(cfg.get('db_host') or '127.0.0.1').strip(),
        port=int(cfg.get('db_port') or 3306),
        user=str(cfg.get('db_user') or 'root').strip(),
        password=str(cfg.get('db_password') or ''),
        database=str(db_name).strip(),
    )
