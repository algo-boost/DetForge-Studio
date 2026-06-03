"""保存策略时手写 process_data 不被 process_pipeline 覆盖"""

import unittest

from studio.flow.flow_schema import prepare_strategy
from studio.flow.flow_compiler import normalize_strategy
from studio.query.strategy_loader import get_all_templates


class TestPrepareStrategyManual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = get_all_templates()

    def test_manual_code_preserved_on_save(self):
        custom = (
            "def process_data(df):\n"
            "    view(df, '我的手写标记')\n"
            "    return df\n"
        )
        strategy = {
            'id': 'test_manual_save',
            'name': 'test',
            'filter_mode': 'split',
            'python_code': custom,
            'python_code_manual': True,
            'process_pipeline': [
                {'template_id': 'preset_observe', 'params': {'stats_label': 'x', 'df_label': 'y', 'show_stats': 'yes', 'show_df': 'yes'}},
            ],
            'flow': {'version': 2, 'nodes': []},
            'env_schema': [],
        }
        prepared = prepare_strategy(strategy)
        normalized = normalize_strategy(prepared, self.templates)
        self.assertIn('我的手写标记', normalized['python_code'])
        self.assertTrue(normalized.get('python_code_manual'))

    def test_auto_detect_manual_when_code_differs(self):
        custom = "def process_data(df):\n    view(df, '唯一标记xyz')\n    return df\n"
        strategy = {
            'id': 'test_auto_manual',
            'python_code': custom,
            'process_pipeline': [
                {'template_id': 'preset_apply_filter_rules', 'params': {}},
            ],
            'flow': {'version': 2, 'nodes': []},
        }
        out = prepare_strategy(strategy)
        self.assertIn('唯一标记xyz', out['python_code'])
        self.assertTrue(out.get('python_code_manual'))

    def test_data_source_normalized_on_save(self):
        strategy = {
            'id': 'test_ds',
            'name': 't',
            'sql_template': 'SELECT * FROM detforge.predict_result WHERE job_id=1',
            'flow': {'version': 2, 'nodes': []},
        }
        out = prepare_strategy(strategy)
        self.assertEqual(out['data_source'], 'predict_result')

        strategy2 = {
            'id': 'test_ds2',
            'data_source': 'detail',
            'sql_template': 'SELECT * FROM predict_result',
            'flow': {'version': 2, 'nodes': []},
        }
        out2 = prepare_strategy(strategy2)
        self.assertEqual(out2['data_source'], 'detail')

    def test_query_compact_hide_persists_false(self):
        strategy = {
            'id': 'test_compact_hide',
            'name': 't',
            'query_ui_mode': 'compact',
            'query_compact_hide': {
                'preview_button': False,
                'data_source': True,
                'strategy_tools': True,
            },
            'flow': {'version': 2, 'nodes': []},
        }
        out = prepare_strategy(strategy)
        self.assertEqual(out['query_ui_mode'], 'compact')
        hide = out['query_compact_hide']
        self.assertFalse(hide['preview_button'])
        self.assertTrue(hide['data_source'])
        self.assertTrue(hide['strategy_tools'])


if __name__ == '__main__':
    unittest.main()
