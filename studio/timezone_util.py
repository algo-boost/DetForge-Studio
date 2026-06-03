"""应用时区：默认北京时间，可在 config.json 的 timezone 字段配置。"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

DEFAULT_TIMEZONE = 'Asia/Shanghai'

# (IANA id, 中文说明) — 设置页下拉
TIMEZONE_CHOICES: list[tuple[str, str]] = [
    ('Asia/Shanghai', '北京时间 (UTC+8)'),
    ('Asia/Hong_Kong', '香港时间'),
    ('Asia/Taipei', '台北时间'),
    ('Asia/Tokyo', '东京时间'),
    ('UTC', 'UTC'),
    ('America/New_York', '美东时间'),
    ('America/Los_Angeles', '美西时间'),
    ('Europe/London', '伦敦时间'),
]


def timezone_options_for_api() -> list[dict[str, str]]:
    return [{'id': tid, 'label': label} for tid, label in TIMEZONE_CHOICES]


def resolve_timezone(name: str | None = None) -> ZoneInfo:
    tid = (name or '').strip() or DEFAULT_TIMEZONE
    if tid in available_timezones():
        return ZoneInfo(tid)
    for fallback in (DEFAULT_TIMEZONE, 'UTC'):
        if fallback in available_timezones():
            return ZoneInfo(fallback)
    return ZoneInfo('UTC')


def get_config_timezone(config: dict | None = None) -> ZoneInfo:
    if config is None:
        from server.core import load_config
        config = load_config()
    return resolve_timezone((config or {}).get('timezone'))


def now_local(config: dict | None = None) -> datetime:
    """当前时刻（配置时区）。"""
    return datetime.now(get_config_timezone(config))


def format_datetime(
    dt: datetime | None,
    fmt: str = '%Y-%m-%d %H:%M:%S',
    *,
    config: dict | None = None,
) -> str:
    if dt is None:
        return ''
    tz = get_config_timezone(config)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime(fmt)


def format_now(fmt: str = '%Y-%m-%d %H:%M:%S', *, config: dict | None = None) -> str:
    return format_datetime(now_local(config), fmt, config=config)


def format_timestamp(
    ts: float,
    fmt: str = '%Y-%m-%d %H:%M',
    *,
    config: dict | None = None,
) -> str:
    tz = get_config_timezone(config)
    return datetime.fromtimestamp(ts, tz=tz).strftime(fmt)


def format_iso_now(*, config: dict | None = None) -> str:
    return now_local(config).isoformat(timespec='seconds')


def stamp_compact(*, config: dict | None = None) -> str:
    """目录名用：YYYYMMDD_HHMMSS"""
    return format_now('%Y%m%d_%H%M%S', config=config)


def stamp_day(*, config: dict | None = None) -> str:
    return format_now('%Y%m%d', config=config)
