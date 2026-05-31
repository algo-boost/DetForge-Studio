"""数据集同步模块单元测试（不依赖 Magic-Fox 网络）。"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from studio.forge import forge_paths
from studio.sync import magic_fox_bridge
from studio.sync import magic_fox_discover
from studio.sync.forge_sync import _annotation_box_count, _count_local_images


class TestMagicFoxUrlParse(unittest.TestCase):
    def test_parse_datasets_url(self):
        url = 'https://www.ai.magic-fox.com/#/datasets?approachId=598&subjectId=190'
        parsed = magic_fox_discover.parse_magic_fox_url(url)
        self.assertEqual(parsed['approach_id'], 598)
        self.assertEqual(parsed['subject_id'], 190)
        self.assertEqual(parsed['page'], 'datasets')

    def test_parse_training_url(self):
        url = 'https://www.ai.magic-fox.com/#/training?approachId=18&subjectId=3'
        parsed = magic_fox_discover.parse_magic_fox_url(url)
        self.assertEqual(parsed['approach_id'], 18)
        self.assertEqual(parsed['subject_id'], 3)
        self.assertEqual(parsed['page'], 'training')

    def test_build_page_urls(self):
        pages = magic_fox_discover.build_page_urls(598, 190)
        self.assertIn('approachId=598', pages['datasets'])
        self.assertIn('subjectId=190', pages['training'])
        self.assertIn('/#/enhance?', pages['enhance'])

    def test_build_data_view_url(self):
        url = magic_fox_discover.build_data_view_url(598, 2845, 190)
        self.assertIn('datasetId=2845', url)
        self.assertIn('subjectId=190', url)

    def test_missing_approach_raises(self):
        with self.assertRaises(ValueError):
            magic_fox_discover.parse_magic_fox_url('https://www.ai.magic-fox.com/#/datasets')


class TestMagicFoxDiscoverMock(unittest.TestCase):
    @patch('studio.sync.magic_fox_discover.fetch_all_snapshots')
    @patch('studio.sync.magic_fox_discover.fetch_all_datasets')
    def test_discover_resources(self, mock_ds, mock_sn):
        mock_ds.return_value = [{'id': 1, 'name': 'A', 'source_type': 'dataset', 'source_id': 1}]
        mock_sn.return_value = [{'enhance_id': 9, 'name': 'S', 'source_type': 'snapshot', 'source_id': 9}]
        result = magic_fox_discover.discover_resources(
            url='https://www.ai.magic-fox.com/#/datasets?approachId=598&subjectId=190',
        )
        self.assertEqual(result['approach_id'], 598)
        self.assertEqual(result['counts']['datasets'], 1)
        self.assertEqual(result['counts']['snapshots'], 1)
        self.assertIn('training', result['pages'])


class TestMagicFoxEnvFallback(unittest.TestCase):
    @patch.dict(os.environ, {'MAGIC_FOX_USERNAME': 'envuser', 'MAGIC_FOX_PASSWORD': 'envpass'}, clear=False)
    def test_resolve_uses_env_password(self):
        cfg = {'magic_fox_auth_mode': 'password', 'magic_fox_api_base': 'https://example.com/api/v1'}
        base, user, pw = magic_fox_bridge.resolve_magic_fox_credentials(cfg)
        self.assertEqual(user, 'envuser')
        self.assertEqual(pw, 'envpass')

    @patch.dict(os.environ, {'MAGIC_FOX_USERNAME': 'envuser', 'MAGIC_FOX_PASSWORD': 'envpass'}, clear=False)
    def test_auth_status_env_source(self):
        st = magic_fox_bridge.auth_status({'magic_fox_auth_mode': 'password'})
        self.assertTrue(st['magic_fox_configured'])
        self.assertEqual(st['magic_fox_credential_source'], 'env')

    def test_missing_credentials_raises(self):
        cfg = {'magic_fox_auth_mode': 'password'}
        env_keys = ('MAGIC_FOX_USERNAME', 'MAGIC_FOX_PASSWORD', 'MAGIC_FOX_TOKEN', 'MAGIC_FOX_ACCESS_TOKEN')
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        try:
            with self.assertRaises(ValueError):
                magic_fox_bridge.resolve_magic_fox_credentials(cfg)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class TestMagicFoxAuth(unittest.TestCase):
    def test_auth_status_password_mode(self):
        cfg = {
            'magic_fox_auth_mode': 'password',
            'magic_fox_api_base': 'https://example.com/api/v1',
            'magic_fox_username': 'user',
            'magic_fox_password': 'secret',
        }
        st = magic_fox_bridge.auth_status(cfg)
        self.assertTrue(st['magic_fox_configured'])
        self.assertTrue(st['magic_fox_password_set'])
        self.assertEqual(st['magic_fox_auth_mode'], 'password')

    def test_merge_keeps_saved_password(self):
        current = {'magic_fox_password': 'saved', 'magic_fox_access_token': 'tok'}
        merged = magic_fox_bridge.merge_auth_overrides(current, {'magic_fox_password': ''})
        self.assertEqual(merged['magic_fox_password'], 'saved')
        self.assertEqual(merged['magic_fox_access_token'], 'tok')

    def test_resolve_credentials_token_mode(self):
        cfg = {
            'magic_fox_auth_mode': 'token',
            'magic_fox_api_base': 'https://example.com/api/v1',
            'magic_fox_access_token': 'abc123',
        }
        base, token = magic_fox_bridge.resolve_magic_fox_credentials(cfg)
        self.assertEqual(base, 'https://example.com/api/v1')
        self.assertEqual(token, 'abc123')


class TestSyncHelpers(unittest.TestCase):
    def test_annotation_box_count(self):
        item = {'annotations': [{'shapes': [{}, {}]}, {'shapes': [{}]}]}
        self.assertEqual(_annotation_box_count(item), 3)
        self.assertEqual(_annotation_box_count({}), 0)

    def test_count_local_images_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, 'a.jpg'), 'wb').write(b'x')
            open(os.path.join(tmp, '_annotations.coco.json'), 'w').write('{}')
            self.assertEqual(_count_local_images(tmp, False), 1)

    def test_allowed_sync_roots_includes_datasets(self):
        roots = forge_paths.allowed_sync_roots()
        self.assertTrue(any('datasets' in r for r in roots))


class TestMagicFoxFetchPagination(unittest.TestCase):
    def test_fetches_with_total_limit(self):
        from studio.sync import magic_fox_fetch

        probe_resp = {
            'code': 200, 'success': True,
            'data': {'total_count': 250, 'dataset_items': [{'id': i} for i in range(100)]},
        }
        full_resp = {
            'code': 200, 'success': True,
            'data': {'total_count': 250, 'dataset_items': [{'id': i} for i in range(250)]},
        }

        class FakeResp:
            def __init__(self, data):
                self._data = data
            def raise_for_status(self):
                return None
            def json(self):
                return self._data

        class FakeSession:
            def __init__(self):
                self.calls = 0
            def get(self, *args, **kwargs):
                self.calls += 1
                limit = kwargs.get('params', {}).get('limit', 100)
                if limit <= 100:
                    return FakeResp(probe_resp)
                return FakeResp(full_resp)

        m = MagicMock()
        m._api_session.return_value = FakeSession()
        m._direct_proxies.return_value = {}

        with patch('studio.sync.magic_fox_fetch.mf.ensure_moli_module', return_value=m):
            rows = magic_fox_fetch.fetch_dataset_items_all_pages('https://example.com/api/v1', 'tok', 1)
        self.assertEqual(len(rows), 250)


if __name__ == '__main__':
    unittest.main()
