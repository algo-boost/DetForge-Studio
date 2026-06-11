"""Kestra MySQL 库引导（CREATE DATABASE IF NOT EXISTS）。"""
from __future__ import annotations

import pymysql

from orchestration.native.mysql_settings import KestraMysqlSettings, resolve_mysql_settings


def ensure_kestra_database(database: str | None = None) -> str:
    settings = resolve_mysql_settings(database)
    conn = pymysql.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        charset='utf8mb4',
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.database}` "
                'DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
            )
    finally:
        conn.close()
    return settings.database
