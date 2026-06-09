"""平台数据库访问（委托 server.core）。"""
from __future__ import annotations


def get_platform_db():
    """返回平台 MySQL 客户端（pymysql 封装）。"""
    from server.core import get_db_client
    return get_db_client()
