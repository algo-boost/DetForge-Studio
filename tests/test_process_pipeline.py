"""process_pipeline 编译与预设步骤模板"""

import unittest

from studio.flow.process_pipeline import (
    compile_process_pipeline,
    default_pipeline_from_python_presets,
    ensure_process_pipeline,
    preset_groups_from_pipeline,
)
from studio.query.strategy_loader import get_all_templates

USER_LOOP_FLOW = {
    'version': 2,
    'nodes': [
        {
            'id': 'loop1',
            'type': 'control.loop',
            'params': {'loop_mode': 'rules', 'rules': []},
            'body': [
                {'id': 'f1', 'type': 'builtin.filter_df_by_ext', 'params': {'bind_loop_rule': 'loop_rule'}},
            ],
        },
    ],
}


class TestProcessPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = get_all_templates()

    def test_compile_process_data_indent_valid(self):
        pipeline = [
            {
                'template_id': 'preset_observe',
                'params': {
                    'stats_label': '类别统计',
                    'df_label': 'DataFrame',
                    'show_stats': 'yes',
                    'show_df': 'yes',
                },
            },
        ]
        result = compile_process_pipeline(pipeline, self.templates)
        self.assertTrue(result['valid'], result.get('errors'))
        code = result['python_code']
        compile(code, '<pipeline>', 'exec')
        self.assertIn('\n    return df\n', code)
        self.assertNotIn('\n        return df', code)

    def test_compile_observe_filter_no_sampling(self):
        pipeline = default_pipeline_from_python_presets(['observe', 'filter'])
        result = compile_process_pipeline(pipeline, self.templates)
        self.assertTrue(result['valid'], result.get('errors'))
        code = result['python_code']
        self.assertIn('apply_filter_rules', code)
        self.assertNotIn('apply_random_sample_rows', code)
        self.assertIn('view(count_category_boxes', code)

    def test_compile_full_preset_order(self):
        pipeline = default_pipeline_from_python_presets(['observe', 'filter', 'sampling'])
        result = compile_process_pipeline(pipeline, self.templates)
        self.assertTrue(result['valid'])
        code = result['python_code']
        pos_filter = code.index('apply_filter_rules')
        pos_sample = code.index('apply_random_sample_rows')
        self.assertLess(pos_filter, pos_sample)

    def test_strategy_explicit_presets_no_sampling_in_schema(self):
        from studio.query.strategy_env_schema import merge_strategy_env_schema

        strategy = {
            'python_presets': ['observe', 'filter'],
            'process_pipeline': default_pipeline_from_python_presets(['observe', 'filter']),
            'env_schema': [{'key': 'SAMPLE_SIZE', 'type': 'number'}],
            'flow': USER_LOOP_FLOW,
        }
        merged = merge_strategy_env_schema(strategy, self.templates)
        keys = {r['key'] for r in merged}
        self.assertNotIn('SAMPLE_SIZE', keys)

    def test_preset_groups_from_pipeline(self):
        pipe = default_pipeline_from_python_presets(['filter', 'sampling'])
        groups = preset_groups_from_pipeline(pipe, self.templates)
        self.assertEqual(groups, ['filter', 'sampling'])

    def test_ensure_from_python_presets(self):
        strategy = {'python_presets': ['observe', 'filter'], 'flow': USER_LOOP_FLOW}
        pipe = ensure_process_pipeline(strategy, self.templates)
        self.assertGreaterEqual(len(pipe), 2)


if __name__ == '__main__':
    unittest.main()
