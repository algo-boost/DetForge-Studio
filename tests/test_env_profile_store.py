import unittest
import os
import tempfile
import shutil

from studio.query import env_profile_store


class EnvProfileStoreTest(unittest.TestCase):
    def setUp(self):
        self._orig_dir = env_profile_store.ENV_PROFILES_DIR
        self.tmp = tempfile.mkdtemp()
        env_profile_store.ENV_PROFILES_DIR = self.tmp

    def tearDown(self):
        env_profile_store.ENV_PROFILES_DIR = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_list_get_delete(self):
        saved = env_profile_store.save_profile({
            'id': 'test_profile',
            'name': '测试模版',
            'vars': [{'key': 'MIN_SCORE', 'value': '0.2', 'label': '分数'}],
            'strategy_hints': ['replay_post_ng'],
        })
        self.assertEqual(saved['id'], 'test_profile')
        self.assertEqual(saved['vars'][0]['key'], 'MIN_SCORE')

        items = env_profile_store.list_profiles()
        self.assertEqual(len(items), 1)

        row = env_profile_store.get_profile('test_profile')
        self.assertEqual(row['name'], '测试模版')

        env = env_profile_store.profile_to_env(row)
        self.assertEqual(env['MIN_SCORE'], '0.2')

        self.assertTrue(env_profile_store.delete_profile('test_profile'))
        self.assertIsNone(env_profile_store.get_profile('test_profile'))

    def test_suggest_vars_from_strategy(self):
        rows = env_profile_store.suggest_vars(['replay_post_ng'])
        keys = {r['key'] for r in rows}
        self.assertIn('MIN_SCORE', keys)


if __name__ == '__main__':
    unittest.main()
