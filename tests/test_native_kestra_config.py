"""orchestration.native 分层单元测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from orchestration.native.config_render import render_kestra_application
from orchestration.native.defaults import NativeDeployDefaults
from orchestration.native.mysql_settings import resolve_mysql_settings


@pytest.fixture
def deploy_root(tmp_path):
    native = tmp_path / 'native'
    native.mkdir()
    template = (
        Path(__file__).resolve().parents[1]
        / 'deploy'
        / 'native'
        / 'kestra-application.template.yml'
    ).read_text(encoding='utf-8')
    (native / 'kestra-application.template.yml').write_text(template, encoding='utf-8')
    return tmp_path


def test_resolve_mysql_settings_from_config():
    fake_cfg = {
        'db_host': '10.0.0.1',
        'db_user': 'app',
        'db_password': 'pw',
        'db_port': 3307,
        'kestra_database': 'kestra_test',
    }
    with patch('orchestration.native.mysql_settings.load_config', return_value=fake_cfg):
        s = resolve_mysql_settings()
    assert s.host == '10.0.0.1'
    assert s.port == 3307
    assert s.database == 'kestra_test'
    assert 'jdbc:mysql://10.0.0.1:3307/kestra_test' in s.jdbc_url


def test_render_kestra_application_writes_mysql_yml(deploy_root):
    fake_cfg = {
        'db_host': '127.0.0.1',
        'db_user': 'root',
        'db_password': 'secret',
        'db_port': 3306,
        'kestra_database': 'kestra',
    }
    defaults = NativeDeployDefaults(
        kestra_version='1.3.21',
        kestra_port=8080,
        iisp_port=5050,
        kestra_user='admin@kestra.io',
        kestra_password='Admin1234',
        env_iisp_base='http://127.0.0.1:5050',
        kestra_mysql_database='kestra',
        java_opts='-Xmx4096m',
    )
    with patch('orchestration.native.mysql_settings.load_config', return_value=fake_cfg):
        out = render_kestra_application(deploy_root=deploy_root, defaults=defaults)
    text = out.read_text(encoding='utf-8')
    assert 'jdbc:mysql://127.0.0.1:3306/kestra' in text
    assert 'type: mysql' in text
    assert 'admin@kestra.io' in text
