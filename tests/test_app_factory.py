"""Smoke test for Flask app factory."""
import unittest

from server.factory import create_app


class AppFactoryTests(unittest.TestCase):
    def test_create_app_registers_api_routes(self):
        app = create_app()
        rules = {r.rule for r in app.url_map.iter_rules()}
        self.assertIn('/api/config', rules)
        self.assertIn('/api/query', rules)
        self.assertIn('/api/strategies', rules)

    def test_create_app_has_spa_fallback(self):
        app = create_app()
        client = app.test_client()
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
