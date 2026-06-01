"""replay_run_service 单元测试。"""
import unittest

from studio.curation import replay_run_service


class TimeWindowTests(unittest.TestCase):
    def test_explicit_range(self):
        start, end = replay_run_service.resolve_time_window({
            'start_time': '2026-05-01 00:00:00',
            'end_time': '2026-05-01 23:59:59',
        })
        self.assertEqual(start, '2026-05-01 00:00:00')
        self.assertEqual(end, '2026-05-01 23:59:59')

    def test_yesterday_preset(self):
        start, end = replay_run_service.resolve_time_window({'preset': 'yesterday'})
        self.assertTrue(start < end)
        self.assertIn(':', start)


if __name__ == '__main__':
    unittest.main()
