"""strategy_env_schema：参数仅随 python_presets 勾选加载"""

import unittest

from studio.query.strategy_env_schema import (
    merge_strategy_env_schema,
    strategy_needs_sampling_env,
    sync_env_schema_with_capabilities,
)
from studio.query.python_preset_registry import inactive_preset_env_keys

USER_LOOP_FLOW = {
    'version': 2,
    'nodes': [
        {
            'id': 'nmpvv9pzv3xi8',
            'type': 'control.loop',
            'params': {'loop_mode': 'rules', 'rules': []},
            'body': [
                {
                    'id': 'nmpvv9pzvdbec',
                    'type': 'builtin.filter_df_by_ext',
                    'params': {
                        'bind_loop_rule': 'loop_rule',
                        'categories': [],
                        'confidence_range': [0, 1],
                        'random_drop_ratio': 1,
                    },
                },
            ],
        },
    ],
}


class TestStrategyEnvSchemaPresets(unittest.TestCase):
    def test_filter_only_no_sample_size(self):
        strategy = {
            'python_presets': ['observe', 'filter'],
            'env_schema': [
                {'key': 'START_TIME', 'type': 'datetime'},
                {'key': 'SAMPLE_SIZE', 'type': 'number', 'default': '300'},
                {'key': 'SAMPLE_NUMS', 'type': 'number', 'default': '300'},
            ],
            'flow': USER_LOOP_FLOW,
            'python_code': 'def process_data(df):\n    df = apply_filter_rules(df)\n    df = apply_random_sample_rows(df)\n    return df\n',
        }
        merged = merge_strategy_env_schema(strategy, templates={})
        keys = {r['key'] for r in merged}
        self.assertNotIn('SAMPLE_SIZE', keys)
        self.assertNotIn('RANDOM_SEED', keys)
        self.assertIn('SAMPLE_NUMS', keys)

    def test_sampling_preset_adds_sample_size(self):
        strategy = {
            'python_presets': ['sampling'],
            'env_schema': [{'key': 'START_TIME', 'type': 'datetime'}],
            'flow': USER_LOOP_FLOW,
        }
        merged = merge_strategy_env_schema(strategy, templates={})
        keys = {r['key'] for r in merged}
        self.assertIn('SAMPLE_SIZE', keys)
        self.assertIn('RANDOM_SEED', keys)

    def test_explicit_empty_presets_no_sampling_even_with_flow_block(self):
        strategy = {
            'python_presets': [],
            'env_schema': [],
            'flow': {
                'version': 2,
                'nodes': [
                    {'id': 's1', 'type': 'template.random_sample', 'template_id': 'random_sample'},
                ],
            },
        }
        self.assertFalse(strategy_needs_sampling_env(strategy))
        merged = merge_strategy_env_schema(strategy, templates={})
        self.assertNotIn('SAMPLE_SIZE', {r['key'] for r in merged})

    def test_legacy_infer_sampling_without_explicit_presets(self):
        strategy = {
            'env_schema': [],
            'flow': {
                'version': 2,
                'nodes': [
                    {'id': 's1', 'type': 'template.random_sample', 'template_id': 'random_sample'},
                ],
            },
            'python_code': 'def process_data(df):\n    return apply_random_sample_rows(df)\n',
        }
        self.assertTrue(strategy_needs_sampling_env(strategy))
        merged = merge_strategy_env_schema(strategy, templates={})
        self.assertIn('SAMPLE_SIZE', {r['key'] for r in merged})

    def test_sync_strips_inactive_preset_keys(self):
        strategy = {
            'python_presets': ['filter'],
            'env_schema': [{'key': 'SAMPLE_SIZE', 'type': 'number'}],
            'flow': USER_LOOP_FLOW,
        }
        synced = sync_env_schema_with_capabilities(strategy, templates={})
        blocked = inactive_preset_env_keys(['filter'])
        self.assertTrue(blocked & {'SAMPLE_SIZE', 'RANDOM_SEED'})
        self.assertNotIn('SAMPLE_SIZE', {r['key'] for r in synced})


if __name__ == '__main__':
    unittest.main()
