"""随机采样：仅 process_data + 环境变量 SAMPLE_SIZE。"""
import unittest

import pandas as pd

from server.core import execute_python_filter
from studio.flow.flow_compiler import build_random_sample_function, compile_sample_code
from studio.query.python_builtins import apply_random_sample_rows


class RandomSampleEnvTests(unittest.TestCase):
    def test_apply_random_sample_rows_skips_without_env(self):
        df = pd.DataFrame({'a': range(500)})
        out = apply_random_sample_rows(df, env={})
        self.assertEqual(len(out), 500)

    def test_apply_random_sample_rows_uses_env(self):
        df = pd.DataFrame({'a': range(500)})
        out = apply_random_sample_rows(df, env={'SAMPLE_SIZE': '100', 'RANDOM_SEED': '1'})
        self.assertEqual(len(out), 100)

    def test_sample_function_uses_get_env(self):
        code = build_random_sample_function()
        self.assertIn('get_env("SAMPLE_SIZE"', code)
        self.assertNotIn('max_rows=300', code)

    def test_process_data_only_sampling(self):
        proc = (
            'def process_data(df):\n'
            '    df = apply_random_sample_rows(df)\n'
            '    return df\n'
        )
        code = build_random_sample_function() + '\n\n' + proc
        df = pd.DataFrame({'a': range(50)})
        result, _, _ = execute_python_filter(df, code, env_context={'SAMPLE_SIZE': '10', 'RANDOM_SEED': '7'})
        self.assertEqual(len(result), 10)

    def test_compile_sample_empty_without_flow_node(self):
        flow = {'nodes': [{'type': 'builtin.view', 'params': {}}]}
        self.assertEqual(compile_sample_code(flow), '')


if __name__ == '__main__':
    unittest.main()
