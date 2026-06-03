"""时区工具单测。"""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from studio.timezone_util import (
    DEFAULT_TIMEZONE,
    format_datetime,
    now_local,
    resolve_timezone,
)


class TestTimezoneUtil(unittest.TestCase):
    def test_default_timezone(self):
        self.assertEqual(str(resolve_timezone(None)), DEFAULT_TIMEZONE)
        self.assertEqual(str(resolve_timezone('')), DEFAULT_TIMEZONE)

    def test_invalid_falls_back(self):
        self.assertEqual(str(resolve_timezone('Not/AZone')), DEFAULT_TIMEZONE)

    def test_now_local_has_tz(self):
        dt = now_local({'timezone': 'Asia/Shanghai'})
        self.assertIsNotNone(dt.tzinfo)

    def test_format_datetime(self):
        dt = datetime(2025, 6, 1, 12, 0, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
        s = format_datetime(dt, config={'timezone': 'Asia/Shanghai'})
        self.assertIn('2025-06-01', s)

    def test_time_range_today(self):
        from studio.query.preset_env import time_range_for_preset  # noqa: PLC0415

        start, end = time_range_for_preset('today')
        self.assertRegex(start, r'^\d{4}-\d{2}-\d{2} 00:00:00$')
        self.assertRegex(end, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')


if __name__ == '__main__':
    unittest.main()
