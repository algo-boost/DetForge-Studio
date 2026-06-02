"""Magic-Fox API 桥接：认证仅来自 config.json 或环境变量，脚本使用内置 vendor 目录。"""
import os
import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent / 'vendor'


def _vendor_script(name: str) -> Path:
    path = _VENDOR_DIR / name
    if not path.is_file():
        raise ImportError(f'内置 Magic-Fox 脚本缺失: {path}')
    return path


def _ensure_vendor_on_path():
    p = str(_VENDOR_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def ensure_coco_export():
    _ensure_vendor_on_path()
    from coco_export import convert_to_coco, fetch_labels_map, generate_stats  # noqa: WPS433
    return convert_to_coco, fetch_labels_map, generate_stats


def ensure_moli_module():
    _ensure_vendor_on_path()
    import moli_dataset_export as m  # noqa: WPS433
    return m


def ensure_flat_download_module():
    _ensure_vendor_on_path()
    from download_generate_snapshot_flat import (  # noqa: WPS433
        assign_dedup_name,
        dataset_page_rows_to_detail_items,
        download_batches,
        fetch_dataset_items_all_pages,
        fetch_dataset_meta,
        fetch_generate_detail,
        hydrate_items_for_coco,
        split_type_to_subdir,
        strip_export_filename,
    )
    return {
        'assign_dedup_name': assign_dedup_name,
        'dataset_page_rows_to_detail_items': dataset_page_rows_to_detail_items,
        'download_batches': download_batches,
        'fetch_dataset_items_all_pages': fetch_dataset_items_all_pages,
        'fetch_dataset_meta': fetch_dataset_meta,
        'fetch_generate_detail': fetch_generate_detail,
        'hydrate_items_for_coco': hydrate_items_for_coco,
        'split_type_to_subdir': split_type_to_subdir,
        'strip_export_filename': strip_export_filename,
    }


def vendor_fetch_training_models_script() -> Path:
    return _vendor_script('fetch_training_models.py')


def _cfg(config=None):
    from server.core import load_config
    return config or load_config()


def _base_url(cfg):
    return str(cfg.get('magic_fox_api_base') or 'https://www.ai.magic-fox.com/api/v1').strip()


def normalize_access_token(token):
    return str(token or '').replace('\n', '').replace('\r', '').replace(' ', '').strip()


def _env_token():
    return normalize_access_token(
        os.environ.get('MAGIC_FOX_TOKEN')
        or os.environ.get('MAGIC_FOX_ACCESS_TOKEN')
        or ''
    )


def _env_password_creds():
    user = str(os.environ.get('MAGIC_FOX_USERNAME') or '').strip()
    pw = str(os.environ.get('MAGIC_FOX_PASSWORD') or '').strip()
    if user and pw:
        return user, pw
    return None


def _disk_secret_set(key):
    try:
        from server.core import secret_field_set_on_disk
        return secret_field_set_on_disk(key)
    except Exception:
        return False


def _credential_source(cfg):
    """返回 (configured: bool, source: str|None)。source 仅 config | env。"""
    mode = str(cfg.get('magic_fox_auth_mode') or 'password').strip().lower()
    if mode not in ('password', 'token'):
        mode = 'password'
    has_user = bool(str(cfg.get('magic_fox_username') or '').strip())
    has_pw = bool(str(cfg.get('magic_fox_password') or '').strip()) or _disk_secret_set('magic_fox_password')
    has_token = bool(str(cfg.get('magic_fox_access_token') or '').strip()) or _disk_secret_set('magic_fox_access_token')

    if mode == 'token':
        if has_token:
            return True, 'config'
        if _env_token():
            return True, 'env'
        return False, None

    if has_user and has_pw:
        return True, 'config'
    if _env_password_creds():
        return True, 'env'
    return False, None


def auth_status(config=None):
    """返回认证配置状态（不含密钥明文），供设置页展示。"""
    cfg = _cfg(config)
    mode = str(cfg.get('magic_fox_auth_mode') or 'password').strip().lower()
    if mode not in ('password', 'token'):
        mode = 'password'
    has_user = bool(str(cfg.get('magic_fox_username') or '').strip())
    has_pw = bool(str(cfg.get('magic_fox_password') or '').strip()) or _disk_secret_set('magic_fox_password')
    has_token = bool(str(cfg.get('magic_fox_access_token') or '').strip()) or _disk_secret_set('magic_fox_access_token')
    configured, source = _credential_source(cfg)
    username = str(cfg.get('magic_fox_username') or '').strip()
    if not username and source == 'env':
        creds = _env_password_creds()
        if creds:
            username = creds[0]
    return {
        'magic_fox_auth_mode': mode,
        'magic_fox_api_base': _base_url(cfg),
        'magic_fox_username': username,
        'magic_fox_password_set': has_pw or (source == 'env' and mode == 'password'),
        'magic_fox_token_set': has_token or (source == 'env' and mode == 'token'),
        'magic_fox_configured': configured,
        'magic_fox_credential_source': source,
    }


def merge_auth_overrides(cfg, overrides=None):
    """用请求体中的临时字段覆盖 cfg（空密码/空 token 表示沿用 cfg / 磁盘密文）。"""
    from server.core import preserve_secrets_for_save
    base = _cfg() if cfg is None else dict(cfg)
    ov = dict(overrides or {})

    if ov.get('magic_fox_api_base') is not None:
        base['magic_fox_api_base'] = ov.get('magic_fox_api_base')
    if ov.get('magic_fox_auth_mode') is not None:
        base['magic_fox_auth_mode'] = ov.get('magic_fox_auth_mode')
    if ov.get('magic_fox_username') is not None:
        base['magic_fox_username'] = ov.get('magic_fox_username')

    pw = str(ov.get('magic_fox_password') or '').strip()
    if pw:
        base['magic_fox_password'] = pw

    tok = normalize_access_token(ov.get('magic_fox_access_token'))
    if tok:
        base['magic_fox_access_token'] = tok

    return preserve_secrets_for_save(base, ov)


def build_config_to_persist(current_cfg, overrides=None):
    """测试认证成功后，将 Magic-Fox 字段合并进可持久化配置。"""
    merged = merge_auth_overrides(current_cfg, overrides)
    ov = dict(overrides or {})
    for key in (
        'magic_fox_api_base', 'magic_fox_auth_mode', 'magic_fox_username', 'dataset_sync_root',
    ):
        if ov.get(key) is not None:
            merged[key] = ov[key]
    return merged


def resolve_magic_fox_credentials(config=None):
    """返回 (base_url, token) 或 (base_url, username, password)。"""
    cfg = _cfg(config)
    base_url = _base_url(cfg)
    mode = str(cfg.get('magic_fox_auth_mode') or 'password').strip().lower()

    if mode == 'token':
        from studio.config_crypto import is_encrypted, resolve_secret_value
        raw_tok = cfg.get('magic_fox_access_token')
        token = normalize_access_token(
            resolve_secret_value(raw_tok) if isinstance(raw_tok, str) and is_encrypted(raw_tok) else raw_tok
        ) or _env_token()
        if not token:
            try:
                from server.core import read_config_file_raw
                disk = read_config_file_raw().get('magic_fox_access_token')
                if isinstance(disk, str) and is_encrypted(disk):
                    token = normalize_access_token(resolve_secret_value(disk))
            except Exception:
                pass
        if token:
            return base_url, token
        raise ValueError(
            '未配置 Magic-Fox Access Token。'
            '请在「设置 → Magic-Fox 训练平台」填写并点「保存配置」，'
            '或设置环境变量 MAGIC_FOX_TOKEN / MAGIC_FOX_ACCESS_TOKEN。'
        )

    from studio.config_crypto import is_encrypted, resolve_secret_value
    user = str(cfg.get('magic_fox_username') or '').strip()
    raw_pw = cfg.get('magic_fox_password')
    pw = resolve_secret_value(raw_pw) if isinstance(raw_pw, str) and is_encrypted(raw_pw) else str(raw_pw or '').strip()
    if not pw:
        disk = None
        try:
            from server.core import read_config_file_raw
            disk = read_config_file_raw().get('magic_fox_password')
        except Exception:
            disk = None
        if isinstance(disk, str) and disk.strip():
            pw = resolve_secret_value(disk) if is_encrypted(disk) else disk.strip()
    if user and pw:
        return base_url, user, pw
    env_creds = _env_password_creds()
    if env_creds:
        return base_url, env_creds[0], env_creds[1]
    raise ValueError(
        '未配置 Magic-Fox 账号密码。'
        '请在「设置 → Magic-Fox 训练平台」填写并点「保存配置」，'
        '或设置环境变量 MAGIC_FOX_USERNAME / MAGIC_FOX_PASSWORD。'
    )


def get_api_token(config=None):
    creds = resolve_magic_fox_credentials(config)
    if len(creds) == 2:
        return creds[0], creds[1]
    base, user, pw = creds
    m = ensure_moli_module()
    token = m.login_and_get_token(base, user, pw)
    if not token:
        raise RuntimeError('Magic-Fox 登录失败，请检查设置页中的账号与密码')
    return base, token


def test_connection(config=None):
    base, token = get_api_token(config)
    m = ensure_moli_module()
    s = m._api_session()
    r = s.get(
        f"{base.rstrip('/')}/labels/",
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
        params={'approach_id': 0},
        proxies=m._direct_proxies(),
        timeout=15,
    )
    if r.status_code in (200, 400, 404):
        return True
    raise RuntimeError(f'Magic-Fox API 响应异常: HTTP {r.status_code}')
