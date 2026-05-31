"""config.json 敏感字段加解密（Fernet，密钥存本地 .config.key）。"""
from __future__ import annotations

import base64
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - 无 cryptography 时降级明文
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _HAS_CRYPTO = False

ENC_PREFIX = 'enc:v1:'
SENSITIVE_KEYS = (
    'db_password',
    'magic_fox_password',
    'magic_fox_access_token',
    'api_token',
)


def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def key_file_path() -> Path:
    return _base_dir() / '.config.key'


def encryption_available() -> bool:
    return _HAS_CRYPTO


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def _load_key_bytes() -> bytes | None:
    env_key = str(os.environ.get('DEFECTLOOP_CONFIG_KEY') or '').strip()
    if env_key:
        return env_key.encode('utf-8')
    path = key_file_path()
    if path.is_file():
        raw = path.read_text(encoding='utf-8').strip()
        return raw.encode('utf-8') if raw else None
    return None


def _save_key_bytes(key: bytes) -> None:
    path = key_file_path()
    path.write_text(key.decode('utf-8'), encoding='utf-8')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_or_create_key() -> bytes | None:
    if not _HAS_CRYPTO:
        return None
    existing = _load_key_bytes()
    if existing:
        return existing
    key = Fernet.generate_key()
    _save_key_bytes(key)
    return key


def _fernet() -> 'Fernet | None':
    key = _load_key_bytes() or get_or_create_key()
    if not key or not _HAS_CRYPTO:
        return None
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    if not plain or not _HAS_CRYPTO:
        return plain
    f = _fernet()
    if f is None:
        return plain
    token = f.encrypt(plain.encode('utf-8')).decode('ascii')
    return f'{ENC_PREFIX}{token}'


def decrypt_value(value: str) -> str:
    if not value or not is_encrypted(value):
        return value or ''
    if not _HAS_CRYPTO:
        raise RuntimeError('config.json 含加密字段，请安装 cryptography: pip install cryptography')
    f = _fernet()
    if f is None:
        raise RuntimeError('缺少配置加密密钥（.config.key 或 DEFECTLOOP_CONFIG_KEY）')
    token = value[len(ENC_PREFIX):].encode('ascii')
    try:
        return f.decrypt(token).decode('utf-8')
    except InvalidToken as exc:
        raise RuntimeError('config.json 解密失败，密钥可能已更换或文件损坏') from exc


def decrypt_config_secrets(config: dict) -> dict:
    out = dict(config)
    for key in SENSITIVE_KEYS:
        val = out.get(key)
        if isinstance(val, str) and is_encrypted(val):
            out[key] = decrypt_value(val)
    return out


def encrypt_config_secrets(config: dict) -> dict:
    if not _HAS_CRYPTO:
        return dict(config)
    out = dict(config)
    get_or_create_key()
    for key in SENSITIVE_KEYS:
        val = out.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        if is_encrypted(val):
            continue
        out[key] = encrypt_value(val)
    return out


def secrets_encryption_status() -> dict:
    key_path = key_file_path()
    return {
        'available': _HAS_CRYPTO,
        'key_present': bool(_load_key_bytes()),
        'key_file': str(key_path),
        'encrypted_fields': list(SENSITIVE_KEYS),
    }
