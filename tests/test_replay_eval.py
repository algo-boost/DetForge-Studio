"""历史回跑向导单测。"""
import unittest

from studio.curation import replay_eval_service


class ReplayFilterTests(unittest.TestCase):
    def test_ng_only_default(self):
        f, mode = replay_eval_service.parse_replay_filters({})
        self.assertEqual(mode, 'ng_only')
        self.assertTrue(f.get('only_with_boxes'))

    def test_clean_only(self):
        f, mode = replay_eval_service.parse_replay_filters({'filter_mode': 'clean_only'})
        self.assertEqual(mode, 'clean_only')
        self.assertTrue(f.get('zero_boxes_only'))

    def test_min_score(self):
        f, _ = replay_eval_service.parse_replay_filters({'filter_mode': 'all', 'min_max_score': 0.5})
        self.assertEqual(f.get('min_max_score'), 0.5)
        self.assertNotIn('only_with_boxes', f)


class RowsToDataframeTests(unittest.TestCase):
    def test_check_status_from_boxes(self):
        import pandas as pd
        df = replay_eval_service._rows_to_dataframe([
            {'img_path': '/a.jpg', 'box_count': 2, 'ext': {'x': 1}},
            {'img_path': '/b.jpg', 'box_count': 0, 'ext': None},
        ])
        self.assertEqual(list(df['check_status']), ['1', '0'])


if __name__ == '__main__':
    unittest.main()
