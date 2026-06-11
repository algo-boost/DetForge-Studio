"""渲染 Kestra application.yml（模板 + MySQL 设置 + 部署默认值）。"""
from __future__ import annotations

from pathlib import Path

from orchestration.native.defaults import NativeDeployDefaults, load_defaults
from orchestration.native.mysql_settings import resolve_mysql_settings
from orchestration.native.paths import (
    CONFIG_TEMPLATE,
    DEPLOY_ROOT,
    FLOWS_ROOT,
    RENDERED_CONFIG,
    RUNTIME_ROOT,
)


def escape_yaml(value: str) -> str:
    if value == '':
        return '""'
    if any(c in value for c in ':{}[]&*#?|-<>=!%@\\"\''):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def render_kestra_application(
    *,
    deploy_root: Path | None = None,
    defaults: NativeDeployDefaults | None = None,
    kestra_database: str | None = None,
) -> Path:
    """写入 deploy/runtime/kestra-application.yml，返回路径。"""
    root = deploy_root or DEPLOY_ROOT
    opts = defaults or load_defaults()
    mysql = resolve_mysql_settings(kestra_database)

    runtime = root / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / 'storage').mkdir(parents=True, exist_ok=True)
    (runtime / 'tmp').mkdir(parents=True, exist_ok=True)

    template_path = root / 'native' / 'kestra-application.template.yml'
    if not template_path.is_file():
        template_path = CONFIG_TEMPLATE
    out_path = runtime / 'kestra-application.yml'
    template = template_path.read_text(encoding='utf-8')

    replacements = {
        '{{JDBC_URL}}': mysql.jdbc_url,
        '{{DB_USER}}': escape_yaml(mysql.user),
        '{{DB_PASSWORD}}': escape_yaml(mysql.password),
        '{{KESTRA_PORT}}': str(opts.kestra_port),
        '{{KESTRA_USER}}': escape_yaml(opts.kestra_user),
        '{{KESTRA_PASSWORD}}': escape_yaml(opts.kestra_password),
        '{{STORAGE_PATH}}': str((runtime / 'storage').resolve()),
        '{{TMP_PATH}}': str((runtime / 'tmp').resolve()),
        '{{FLOWS_PATH}}': str(FLOWS_ROOT.resolve()),
    }
    content = template
    for key, val in replacements.items():
        content = content.replace(key, val)
    out_path.write_text(content, encoding='utf-8')
    return out_path


def rendered_config_path() -> Path:
    return RENDERED_CONFIG
