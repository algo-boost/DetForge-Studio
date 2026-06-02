"""filter / 捞图行级筛选语义。"""
import json
import unittest

import pandas as pd

from studio.query.python_builtins import (
    filter_df_by_ext,
    remove_empty_ext_rows,
    select_df_rows_by_rules_union,
)


def _ext(*names):
    preds = [
        {'name': n, 'confidence': 0.5, 'type': 'det', 'points': [{'x': 1, 'y': 1, 'w': 2, 'h': 2}]}
        for n in names
    ]
    return json.dumps({'original_predictions': preds}, ensure_ascii=False)


class PythonBuiltinsFilterTests(unittest.TestCase):
    def test_select_rows_keeps_all_boxes_on_match(self):
        df = pd.DataFrame({
            'ext': [_ext('脏污', '划伤'), _ext('焊丝')],
        })
        rules = [{
            'categories': ['脏污'],
            'confidence_range': [0, 1],
            'random_drop_ratio': 1.0,
        }]
        out = select_df_rows_by_rules_union(df, rules)
        self.assertEqual(len(out), 1)
        preds = json.loads(out.iloc[0]['ext'])['original_predictions']
        names = {p['name'] for p in preds}
        self.assertEqual(names, {'脏污', '划伤'})

    def test_select_rows_union_second_rule(self):
        df = pd.DataFrame({
            'ext': [_ext('脏污'), _ext('焊丝')],
        })
        rules = [
            {'categories': ['脏污'], 'confidence_range': [0, 1], 'random_drop_ratio': 1.0},
            {'categories': ['焊丝'], 'confidence_range': [0, 1], 'random_drop_ratio': 1.0},
        ]
        out = select_df_rows_by_rules_union(df, rules)
        self.assertEqual(len(out), 2)

    def test_filter_df_by_ext_still_strips_boxes(self):
        df = pd.DataFrame({'ext': [_ext('脏污', '划伤')]})
        out = filter_df_by_ext(
            df, categories=['脏污'], confidence_range=(0, 1), random_drop_ratio=1.0,
        )
        names = {p['name'] for p in json.loads(out.iloc[0]['ext'])['original_predictions']}
        self.assertEqual(names, {'划伤'})

    def test_remove_empty_after_select(self):
        df = pd.DataFrame({'ext': [_ext('脏污'), _ext('其他')]})
        rules = [{'categories': ['脏污'], 'confidence_range': [0, 1], 'random_drop_ratio': 1.0}]
        out = remove_empty_ext_rows(select_df_rows_by_rules_union(df, rules))
        self.assertEqual(len(out), 1)


if __name__ == '__main__':
    unittest.main()
