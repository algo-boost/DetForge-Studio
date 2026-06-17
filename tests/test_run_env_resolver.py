"""运行级 env 模板推导与 legacy 迁移单测。"""
import unittest
from datetime import datetime

from studio.forge.run_env_resolver import (
    enrich_run_params_for_engine,
    eval_env_spec,
    normalize_run_params_defaults,
    preview_run_env,
    resolve_run_params_env,
)
from studio.forge.run_env_templates import list_run_env_templates


class RunEnvResolverTests(unittest.TestCase):
    def test_list_templates(self):
        rows = list_run_env_templates(include_script=True)
        ids = {r['id'] for r in rows}
        self.assertIn('time_preset', ids)
        self.assertIn('time_absolute', ids)
        self.assertTrue(all(r.get('script') for r in rows))

    def test_legacy_time_window_migrates_to_env_spec(self):
        out = normalize_run_params_defaults({'time_window': {'preset': 'last_7d'}, 'env': {'X': '1'}})
        self.assertEqual(out['env_spec']['template_id'], 'time_preset')
        self.assertEqual(out['env_spec']['inputs']['preset'], 'last_7d')
        self.assertEqual(out['env'], {'X': '1'})

    def test_legacy_absolute_time_window(self):
        out = normalize_run_params_defaults({
            'time_window': {
                'start_time': '2026-06-01 00:00:00',
                'end_time': '2026-06-01 23:59:59',
            },
        })
        self.assertEqual(out['env_spec']['template_id'], 'time_absolute')
        self.assertEqual(out['env_spec']['inputs']['start_time'], '2026-06-01 00:00:00')

    def test_time_preset_eval(self):
        fixed = datetime(2026, 6, 11, 10, 0, 0)
        env = eval_env_spec(
            {'kind': 'template', 'template_id': 'time_preset', 'inputs': {'preset': 'yesterday'}},
            now=fixed,
        )
        self.assertIn('START_TIME', env)
        self.assertIn('END_TIME', env)
        self.assertLess(env['START_TIME'], env['END_TIME'])

    def test_time_absolute_eval(self):
        env = eval_env_spec({
            'kind': 'template',
            'template_id': 'time_absolute',
            'inputs': {
                'start_time': '2026-06-01 00:00:00',
                'end_time': '2026-06-01 23:59:59',
            },
        })
        self.assertEqual(env['START_TIME'], '2026-06-01 00:00:00')
        self.assertEqual(env['END_TIME'], '2026-06-01 23:59:59')

    def test_static_env_overrides_derived(self):
        params = {
            'env_spec': {
                'kind': 'template',
                'template_id': 'time_absolute',
                'inputs': {
                    'start_time': '2026-06-01 00:00:00',
                    'end_time': '2026-06-01 23:59:59',
                },
            },
            'env': {'START_TIME': '2026-06-02 00:00:00', 'PRODUCT_LINE': 'hq'},
        }
        env = resolve_run_params_env(params)
        self.assertEqual(env['START_TIME'], '2026-06-02 00:00:00')
        self.assertEqual(env['END_TIME'], '2026-06-01 23:59:59')
        self.assertEqual(env['PRODUCT_LINE'], 'hq')

    def test_preview_run_env(self):
        result = preview_run_env({
            'env_spec': {
                'kind': 'template',
                'template_id': 'time_absolute',
                'inputs': {
                    'start_time': '2026-05-01 00:00:00',
                    'end_time': '2026-05-01 23:59:59',
                },
            },
            'env': {'TAG': 'preview'},
            'flow_id': 'flow_test',
        })
        self.assertEqual(result['env']['TAG'], 'preview')
        self.assertEqual(result['params']['env_spec']['template_id'], 'time_absolute')

    def test_enrich_run_params_for_engine_from_env_spec(self):
        enriched = enrich_run_params_for_engine({
            'env_spec': {
                'kind': 'template',
                'template_id': 'time_preset',
                'inputs': {'preset': 'last_7d'},
            },
        })
        self.assertEqual(enriched['time_window'], {'preset': 'last_7d'})
        self.assertEqual(enriched['env_spec']['template_id'], 'time_preset')

    def test_enrich_run_params_defaults_time_window(self):
        enriched = enrich_run_params_for_engine(None)
        self.assertEqual(enriched['time_window']['preset'], 'yesterday')


if __name__ == '__main__':
    unittest.main()
