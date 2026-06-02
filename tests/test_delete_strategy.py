"""删除策略"""

import json
import os
import tempfile
import unittest
from unittest import mock

from studio.query import strategy_loader as sl


class TestDeleteStrategy(unittest.TestCase):
    def test_delete_user_strategy_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            sid = 'saved_test_delete'
            fpath = os.path.join(tmp, f'{sid}.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump({
                    'id': sid,
                    'name': '测试策略中文',
                    'category': '我的查询',
                    'sql_template': 'SELECT 1',
                }, f, ensure_ascii=False)

            fake = {
                sid: {'id': sid, 'name': '测试', 'category': '我的查询'},
            }
            with mock.patch.object(sl, 'STRATEGIES_DIR', tmp), \
                 mock.patch.object(sl, 'get_all_strategies', return_value=fake):
                ok, err = sl.delete_strategy_by_id(sid)
            self.assertTrue(ok, err)
            self.assertFalse(os.path.isfile(fpath))

    def test_delete_recommended_strategy_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sid = 'ok_history_predict'
            fpath = os.path.join(tmp, f'{sid}.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump({'id': sid, 'name': '历史OK', 'category': '推荐', 'sql_template': 'SELECT 1'}, f)
            fake = {sid: {'id': sid, 'name': '历史OK', 'category': '推荐'}}
            with mock.patch.object(sl, 'STRATEGIES_DIR', tmp), \
                 mock.patch.object(sl, 'get_all_strategies', return_value=fake):
                ok, err = sl.delete_strategy_by_id(sid)
            self.assertTrue(ok, err)

    def test_delete_legacy_builtin_alias_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin_dir = os.path.join(tmp, '_builtin')
            os.makedirs(builtin_dir)
            fpath = os.path.join(builtin_dir, 'replay_post_ng.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump({
                    'id': 'replay_post_ng',
                    'name': '回跑后筛 FP',
                    'category': '内置',
                    'sql_template': 'SELECT 1',
                }, f, ensure_ascii=False)
            fake = {
                'ok_predict_filter': {
                    'id': 'ok_predict_filter',
                    'name': '回跑后筛 FP',
                    'category': '内置',
                },
            }
            with mock.patch.object(sl, 'STRATEGIES_DIR', tmp), \
                 mock.patch.object(sl, 'LEGACY_BUILTIN_DIR', builtin_dir), \
                 mock.patch.object(sl, 'get_all_strategies', return_value=fake):
                ok, err = sl.delete_strategy_by_id('ok_predict_filter')
            self.assertTrue(ok, err)
            self.assertFalse(os.path.isfile(fpath))


if __name__ == '__main__':
    unittest.main()
