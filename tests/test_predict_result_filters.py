import unittest

from studio.forge.predict_result_filters import (
    ext_has_matching_prediction,
    finalize_predict_result_df,
    hydrate_predict_result_df,
    metrics_from_ext,
    normalize_ext_value,
    prepare_predict_result_df,
)
from studio.query.python_builtins import (
    filter_df_by_ext,
    remove_empty_ext_rows,
    select_df_rows_by_rules_union,
)
from studio.flow.flow_compiler import compile_filter_rules


class PredictResultFilterTests(unittest.TestCase):
    def test_normalize_ext_predictions_alias(self):
        raw = {'predictions': [{'name': '脏污', 'confidence': 0.5}]}
        norm = normalize_ext_value(raw)
        self.assertIn('original_predictions', norm)
        self.assertIn('脏污', norm)

    def test_coerce_single_quoted_ext_string(self):
        from studio.forge.predict_result_filters import _coerce_ext_object
        obj = _coerce_ext_object("{'original_predictions': [{'name': '脏污', 'confidence': 0.5}]}")
        self.assertEqual(len(obj['original_predictions']), 1)

    def test_ext_has_matching_prediction(self):
        ext = normalize_ext_value({
            'original_predictions': [
                {'name': '脏污', 'confidence': 0.4},
                {'name': '焊丝', 'confidence': 0.9},
            ],
        })
        self.assertTrue(ext_has_matching_prediction(ext, ['脏污'], min_confidence=0.35))
        self.assertFalse(ext_has_matching_prediction(ext, ['脏污'], min_confidence=0.5))
        self.assertTrue(ext_has_matching_prediction(ext, ['焊丝']))

    def test_finalize_syncs_box_count(self):
        import pandas as pd

        df = pd.DataFrame([{
            'id': 1,
            'ext': normalize_ext_value({
                'original_predictions': [
                    {'name': '脏污', 'confidence': 0.6},
                    {'name': '脏污', 'confidence': 0.2},
                ],
            }),
            'box_count': 0,
            'max_score': None,
        }])
        out = finalize_predict_result_df(df)
        self.assertEqual(int(out.loc[0, 'box_count']), 2)
        self.assertAlmostEqual(float(out.loc[0, 'max_score']), 0.6)

    def test_hydrate_adds_ext_from_id_column(self):
        import pandas as pd
        from unittest.mock import patch

        ext_json = normalize_ext_value({
            'original_predictions': [{'name': '脏污', 'confidence': 0.5}],
        })
        df = pd.DataFrame([{'id': 42, 'img_path': '/a.jpg'}])
        with patch('studio.forge.forge_db.fetch_predict_ext_by_ids', return_value={42: ext_json}):
            out = hydrate_predict_result_df(df)
        self.assertIn('ext', out.columns)
        self.assertIn('脏污', out.loc[0, 'ext'])

    def test_compile_prune_rules_strips_boxes_not_union_keep(self):
        """查询页规则默认应编译为 filter_df_by_ext（剔除框），而非捞图选行。"""
        rules = [
            {'categories': ['脏污'], 'confidence_range': [0, 1], 'random_drop_ratio': 1},
            {'categories': ['焊丝'], 'confidence_range': [0, 1], 'random_drop_ratio': 1},
        ]
        flow = {
            'version': 2,
            'nodes': [{
                'id': 'loop1', 'type': 'control.loop',
                'params': {'loop_mode': 'rules', 'rules_semantics': 'prune_boxes', 'rules': rules},
                'body': [
                    {'id': 'f1', 'type': 'builtin.filter_df_by_ext', 'params': {'bind_loop_rule': 'loop_rule'}},
                    {'id': 'r1', 'type': 'builtin.remove_empty_ext_rows', 'params': {}},
                ],
            }],
        }
        compiled = compile_filter_rules(flow, {})
        self.assertTrue(compiled['valid'])
        code = compiled['python_code']
        self.assertIn('filter_df_by_ext', code)
        self.assertNotIn('select_df_rows_by_rules_union', code)

    def test_user_rules_prune_reduces_rows(self):
        import pandas as pd

        df = prepare_predict_result_df(pd.DataFrame([{
            'ext': normalize_ext_value({'original_predictions': [
                {'name': '脏污', 'confidence': 0.5},
            ]}),
        }]))
        df = filter_df_by_ext(
            df, categories=['脏污'], confidence_range=(0, 1), random_drop_ratio=1.0,
        )
        df = remove_empty_ext_rows(df)
        self.assertEqual(len(df), 0)

    def test_flow_rules_on_predict_ext(self):
        import pandas as pd

        df = prepare_predict_result_df(pd.DataFrame([{
            'ext': normalize_ext_value({
                'original_predictions': [
                    {'name': '脏污', 'confidence': 0.5},
                ],
            }),
        }, {
            'ext': normalize_ext_value({
                'original_predictions': [
                    {'name': '焊丝', 'confidence': 0.8},
                ],
            }),
        }]))
        rules = [{'categories': ['脏污'], 'confidence_range': [0.3, 1], 'random_drop_ratio': 1.0}]
        filtered = select_df_rows_by_rules_union(df, rules)
        self.assertEqual(len(filtered), 1)
        n, mx = metrics_from_ext(filtered.loc[0, 'ext'])
        self.assertEqual(n, 1)
        self.assertAlmostEqual(mx, 0.5)


if __name__ == '__main__':
    unittest.main()
