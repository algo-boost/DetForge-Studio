"""python_preset_registry 单元测试。"""
import unittest

from studio.query.python_preset_registry import (
    infer_preset_groups_from_code,
    resolve_python_presets,
    build_execution_namespace,
)
from studio.query.preset_env import fill_time_env_defaults, time_range_for_preset


class PythonPresetRegistryTests(unittest.TestCase):
    def test_infer_observe_from_view(self):
        code = "def process_data(df):\n    view(df, 'x')\n    return df\n"
        groups = infer_preset_groups_from_code(code)
        self.assertIn('observe', groups)

    def test_resolve_explicit_presets(self):
        strategy = {
            'python_presets': ['filter', 'sampling'],
            'python_code': 'def process_data(df):\n    return df\n',
        }
        self.assertEqual(resolve_python_presets(strategy), ['filter', 'sampling'])

    def test_build_namespace_has_get_env(self):
        ns = build_execution_namespace(
            {'SAMPLE_SIZE': '10'},
            python_presets=['sampling'],
            code='def process_data(df):\n    return apply_random_sample_rows(df)\n',
        )
        self.assertIn('get_env', ns)
        self.assertIn('apply_random_sample_rows', ns)
        self.assertNotIn('view', ns)

    def test_fill_time_env_defaults(self):
        start, end = time_range_for_preset('today')
        out = fill_time_env_defaults({}, schema=[{'key': 'START_TIME'}, {'key': 'END_TIME'}])
        self.assertTrue(out['START_TIME'])
        self.assertTrue(out['END_TIME'])


if __name__ == '__main__':
    unittest.main()
