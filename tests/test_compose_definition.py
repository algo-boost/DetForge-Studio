"""组合编排 definition 与流水线单测。"""
import unittest

from studio.forge.compose_definition import build_compose_definition, build_linear_compose_definition
from studio.forge.compose_flow import (
    encode_step_id,
    normalize_flow_id,
    reindex_step_instances,
    save_compose_flow,
    get_compose_flow,
    list_compose_flows,
    upsert_compose_schedule,
    get_compose_schedule,
)
from studio.forge.workflow_graph import normalize_definition
from studio.forge.workflow_steps import resolve_templates, _build_query_context


class ComposeDefinitionTests(unittest.TestCase):
    def test_step_id_encoding(self):
        fid = normalize_flow_id('daily_fp')
        self.assertEqual(fid, 'flow_daily_fp')
        self.assertEqual(encode_step_id(fid, 1), 'flow_daily_fp.s01')
        self.assertEqual(encode_step_id(fid, 3), 'flow_daily_fp.s03')

    def test_two_step_linear_structure(self):
        d = build_linear_compose_definition({
            'query': {'strategy_id': 'daily_trawl'},
            'predict': {'model_id': 3, 'threshold': 0.1},
        }, flow_id='flow_test')
        self.assertEqual(len(d['steps']), 2)
        self.assertEqual(d['steps'][0]['id'], 'flow_test.s01')
        self.assertEqual(d['steps'][0]['params']['time_window'], '{{params.time_window}}')
        self.assertEqual(d['steps'][1]['requires'], ['flow_test.s01'])
        self.assertEqual(d['steps'][1]['params']['task_id'], '{{steps.flow_test.s01.task_id}}')

    def test_four_step_with_query_predict(self):
        d = build_compose_definition([
            {'module_id': 'query', 'params': {'strategy_id': 's1'}},
            {'module_id': 'predict', 'params': {'model_id': 1}},
            {'module_id': 'query_predict', 'params': {'strategy_id': 's2'}},
            {'module_id': 'curation_create', 'params': {}},
        ], flow_id='flow_chain')
        self.assertEqual(len(d['steps']), 4)
        self.assertEqual(d['steps'][2]['params']['predict_job_id'], '{{steps.flow_chain.s02.job_id}}')
        self.assertEqual(d['steps'][3]['params']['task_id'], '{{steps.flow_chain.s03.task_id}}')

    def test_resolve_dotted_step_id(self):
        d = build_linear_compose_definition(
            {'query': {'strategy_id': 's1'}, 'predict': {'model_id': 1}},
            flow_id='flow_x',
        )
        norm = normalize_definition(d)
        ctx = {'params': {}, 'steps': {'flow_x.s01': {'task_id': 'task-abc'}}}
        resolved = resolve_templates(norm['steps'][1]['params'], ctx)
        self.assertEqual(resolved['task_id'], 'task-abc')

    def test_resolve_time_window_object(self):
        ctx = {'params': {'time_window': {'preset': 'yesterday'}}, 'steps': {}}
        out = resolve_templates('{{params.time_window}}', ctx)
        self.assertEqual(out, {'preset': 'yesterday'})

    def test_reindex_step_instances(self):
        rows = reindex_step_instances('flow_a', [
            {'module_id': 'predict', 'params': {}},
            {'module_id': 'query', 'params': {}},
        ])
        self.assertEqual(rows[0]['uid'], 'flow_a.s01')
        self.assertEqual(rows[1]['uid'], 'flow_a.s02')

    def test_env_overrides_resolved_time_window(self):
        ctx = _build_query_context(
            {'time_window': {'preset': 'yesterday'}, 'env': {'START_TIME': '2026-06-01 00:00:00', 'END_TIME': '2026-06-01 23:59:59'}},
        )
        self.assertEqual(ctx['START_TIME'], '2026-06-01 00:00:00')
        self.assertEqual(ctx['END_TIME'], '2026-06-01 23:59:59')

    def test_global_run_env_overrides_step_env(self):
        ctx = _build_query_context(
            {
                'time_window': {'preset': 'yesterday'},
                'env': {'PRODUCT_LINE': 'step_a', 'START_TIME': '2026-01-01 00:00:00', 'END_TIME': '2026-01-01 23:59:59'},
            },
            {
                'resolved_env': {
                    'PRODUCT_LINE': 'global_b',
                    'START_TIME': '2026-06-10 08:00:00',
                    'END_TIME': '2026-06-10 18:00:00',
                },
            },
        )
        self.assertEqual(ctx['PRODUCT_LINE'], 'global_b')
        self.assertEqual(ctx['START_TIME'], '2026-06-10 08:00:00')
        self.assertEqual(ctx['END_TIME'], '2026-06-10 18:00:00')


class ComposeFlowPersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        from studio.forge import forge_db
        if not forge_db.schema_ready():
            self.skipTest('forge schema not ready')
        fid = normalize_flow_id(f'unit_test_{int(__import__("time").time())}')
        save_compose_flow(
            fid,
            name='单测流水线',
            step_instances=[
                {'module_id': 'query', 'params': {'strategy_id': 'daily_trawl'}},
                {'module_id': 'predict', 'params': {'model_id': 1}},
            ],
            run_params_defaults={'time_window': {'preset': 'last_7d'}},
        )
        loaded = get_compose_flow(fid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['flow_id'], fid)
        self.assertEqual(len(loaded['step_instances']), 2)
        self.assertEqual(loaded['step_instances'][0]['uid'], f'{fid}.s01')
        self.assertEqual(loaded['run_params_defaults']['env_spec']['template_id'], 'time_preset')
        self.assertEqual(loaded['run_params_defaults']['env_spec']['inputs']['preset'], 'last_7d')
        self.assertIn(fid, [r['flow_id'] for r in list_compose_flows()])

    def test_upsert_compose_schedule(self):
        from studio.forge import forge_db
        if not forge_db.schema_ready():
            self.skipTest('forge schema not ready')
        fid = normalize_flow_id(f'unit_sched_{int(__import__("time").time())}')
        save_compose_flow(
            fid,
            name='定时单测',
            step_instances=[
                {'module_id': 'query', 'params': {'strategy_id': 'daily_trawl'}},
            ],
            run_params_defaults={'time_window': {'preset': 'yesterday'}},
        )
        sched = upsert_compose_schedule(
            fid,
            cron_expr='0 3 * * *',
            params={
                'env_spec': {
                    'kind': 'template',
                    'template_id': 'time_preset',
                    'inputs': {'preset': 'yesterday'},
                },
            },
            enabled=1,
        )
        self.assertIsNotNone(sched)
        self.assertEqual(sched['template_id'], fid)
        self.assertEqual(sched['cron_expr'], '0 3 * * *')
        self.assertTrue(sched.get('next_run_at'))
        stored = sched.get('params') or {}
        if isinstance(stored, str):
            import json
            stored = json.loads(stored)
        self.assertEqual(stored['env_spec']['template_id'], 'time_preset')
        loaded = get_compose_schedule(fid)
        self.assertEqual(loaded['id'], sched['id'])
        sched2 = upsert_compose_schedule(fid, cron_expr='0 4 * * *', enabled=0)
        self.assertEqual(sched2['id'], sched['id'])
        self.assertEqual(sched2['cron_expr'], '0 4 * * *')
        self.assertEqual(sched2['enabled'], 0)
        stored2 = sched2.get('params') or {}
        if isinstance(stored2, str):
            import json
            stored2 = json.loads(stored2)
        self.assertEqual(stored2['env_spec']['template_id'], 'time_preset')
        flows = [r for r in list_compose_flows() if r['flow_id'] == fid]
        self.assertEqual(len(flows), 1)
        self.assertFalse(flows[0]['schedule_enabled'])

    def test_start_run_stores_resolved_env(self):
        from server.factory import create_app
        from studio.forge import forge_db
        from studio.forge.workflow_engine import start_run
        if not forge_db.schema_ready():
            self.skipTest('forge schema not ready')
        app = create_app()
        app.config['TESTING'] = True
        fid = normalize_flow_id(f'unit_run_env_{int(__import__("time").time())}')
        save_compose_flow(
            fid,
            name='运行 env 单测',
            step_instances=[
                {'module_id': 'query', 'params': {'strategy_id': 'daily_trawl'}},
            ],
            run_params_defaults={
                'env_spec': {
                    'kind': 'template',
                    'template_id': 'time_absolute',
                    'inputs': {
                        'start_time': '2026-06-01 00:00:00',
                        'end_time': '2026-06-01 23:59:59',
                    },
                },
                'env': {'TAG': 'run_test'},
            },
        )
        run_params = {
            'env_spec': {
                'kind': 'template',
                'template_id': 'time_absolute',
                'inputs': {
                    'start_time': '2026-06-01 00:00:00',
                    'end_time': '2026-06-01 23:59:59',
                },
            },
            'env': {'TAG': 'run_test'},
        }
        with app.app_context():
            run = start_run(
                fid,
                params=run_params,
                name='env 单测运行',
                created_by='unit_test',
                app=app,
            )
        ctx = (run.get('context') or {})
        if isinstance(ctx, str):
            import json
            ctx = json.loads(ctx)
        self.assertIn('resolved_env', ctx)
        self.assertEqual(ctx['resolved_env']['START_TIME'], '2026-06-01 00:00:00')
        self.assertEqual(ctx['resolved_env']['TAG'], 'run_test')


if __name__ == '__main__':
    unittest.main()
