"""端到端 API 回归（需本地 Flask 运行在 5050，数据库可连）。"""
import json
import os
import unittest
import urllib.error
import urllib.request

BASE = os.environ.get('DETFORGE_STUDIO_URL', 'http://127.0.0.1:5050')
AB_PIPELINE = '4a19605f-518c-4ac3-8042-f202dcd9b8e3'


def _get(path):
    with urllib.request.urlopen(f'{BASE}{path}', timeout=15) as resp:
        return json.load(resp)


def _post(path, body):
    req = urllib.request.Request(
        f'{BASE}{path}',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _server_up():
    try:
        with urllib.request.urlopen(f'{BASE}/', timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@unittest.skipUnless(_server_up(), 'Flask 未运行在 5050')
class E2EApiTests(unittest.TestCase):
    def test_pipelines_list(self):
        data = _get('/api/pipelines?limit=5')
        self.assertTrue(data.get('success'))
        self.assertIsInstance(data.get('pipelines'), list)

    def test_pipeline_import_min_threshold(self):
        data = _get(f'/api/pipelines/{AB_PIPELINE}/filter-rules?random_drop_ratio=0')
        self.assertTrue(data.get('success'), data.get('error'))
        rules = data.get('rules') or []
        self.assertGreater(len(rules), 0)
        self.assertEqual(data.get('meta', {}).get('confidence_semantics'), 'min_threshold')
        for r in rules:
            self.assertEqual(r.get('confidence_mode'), 'min_threshold')
            self.assertIsNotNone(r.get('min_confidence'))
        nodes = data.get('nodes') or []
        self.assertGreater(len(nodes), 0)

    def test_compile_pipeline_rules_uses_strip_boxes(self):
        bundle = _get(f'/api/pipelines/{AB_PIPELINE}/filter-rules?random_drop_ratio=0')
        self.assertTrue(bundle.get('success'))
        comp = _post('/api/flow/compile', {
            'flow': bundle.get('flow'),
            'target': 'filter_rules',
        })
        self.assertTrue(comp.get('success'), comp.get('error'))
        code = comp.get('python_code') or ''
        self.assertIn('strip_boxes_below_confidence', code)
        self.assertIn('apply_filter_rules', code)

    def test_compile_trawl_mode_uses_filter_df(self):
        """捞图区间规则（无 min_confidence）编译后含 filter_df_by_ext 分支。"""
        bundle = _get(f'/api/pipelines/{AB_PIPELINE}/filter-rules?random_drop_ratio=1')
        rule = dict((bundle.get('rules') or [{}])[0])
        rule.pop('confidence_mode', None)
        rule.pop('min_confidence', None)
        rule['confidence_range'] = [0.5, 1.0]
        rule['random_drop_ratio'] = 1.0
        from studio.query.pipeline_rules import build_rules_flow
        flow = build_rules_flow([rule], remove_empty=True)
        comp = _post('/api/flow/compile', {'flow': flow, 'target': 'filter_rules'})
        self.assertTrue(comp.get('success'))
        code = comp.get('python_code') or ''
        self.assertIn('filter_df_by_ext', code)


@unittest.skipUnless(_server_up(), 'Flask 未运行在 5050')
class ForgeE2ETests(unittest.TestCase):
    def test_image_path_traversal_blocked(self):
        req = urllib.request.Request(f'{BASE}/api/image/x?path=%2Fetc%2Fpasswd')
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail('expected 403')
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 403)

    def test_forge_categories(self):
        data = _get('/api/forge/manual-qc/categories')
        self.assertTrue(data.get('success'))
        self.assertIn('imaging_categories', data)

    def test_forge_jobs_pagination(self):
        data = _get('/api/forge/jobs?limit=5&offset=0')
        self.assertTrue(data.get('success'))
        self.assertIn('total', data)
        self.assertIn('data', data)
        self.assertLessEqual(len(data.get('data') or []), 5)

    def test_flow_nodes_registry(self):
        data = _get('/api/flow/nodes')
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('data'))

    def test_strategies_list(self):
        data = _get('/api/strategies')
        self.assertTrue(data.get('success'))
        self.assertIsInstance(data.get('data'), list)

    def test_pipeline_nodes_api(self):
        data = _get(f'/api/pipelines/{AB_PIPELINE}/nodes')
        self.assertTrue(data.get('success'))
        self.assertGreater(len(data.get('nodes') or []), 0)

    def test_config_path_checks(self):
        data = _get('/api/config')
        self.assertTrue(data.get('success'))
        self.assertIn('path_checks', data)

    def test_predict_result_source(self):
        data = _get('/api/forge/predict-result/source')
        self.assertTrue(data.get('success'), data.get('error'))
        self.assertIn('table', data)
        sql = data.get('default_sql') or ''
        self.assertIn('predict_result', sql)
        self.assertNotIn('BETWEEN', sql.upper())


if __name__ == '__main__':
    unittest.main()
