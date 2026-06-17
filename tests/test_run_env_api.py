"""运行级 env 模板 API 单测（Flask test_client）。"""
import json
import unittest


class RunEnvApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.factory import create_app
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_run_env_templates_list(self):
        r = self.client.get('/api/forge/workflows/run-env-templates?include_script=1')
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body.get('success'))
        ids = {row['id'] for row in body.get('data') or []}
        self.assertIn('time_preset', ids)
        row = next(x for x in body['data'] if x['id'] == 'time_preset')
        self.assertTrue(row.get('script'))

    def test_run_env_preview(self):
        r = self.client.post(
            '/api/forge/workflows/run-env/preview',
            data=json.dumps({
                'env_spec': {
                    'kind': 'template',
                    'template_id': 'time_absolute',
                    'inputs': {
                        'start_time': '2026-06-01 00:00:00',
                        'end_time': '2026-06-01 23:59:59',
                    },
                },
                'env': {'PRODUCT_LINE': 'hq'},
            }),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body.get('success'))
        env = body['data']['env']
        self.assertEqual(env['START_TIME'], '2026-06-01 00:00:00')
        self.assertEqual(env['PRODUCT_LINE'], 'hq')


if __name__ == '__main__':
    unittest.main()
