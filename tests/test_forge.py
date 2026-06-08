"""DetForge 模型预测升级单测。

纯逻辑测试始终运行；依赖 MySQL 的作业/续跑/归档测试在无法连库时自动跳过，
并使用独立写库名 detforge_test，避免污染真实数据。
"""
import os
import sys
import unittest
from unittest.mock import patch

import shutil
import tempfile

import pandas as pd

from studio.forge import forge_db
from studio.forge import forge_service
from studio.forge import forge_predict
from studio.forge import forge_manual_qc
from studio.forge import forge_paths
from studio.query import python_builtins as pb

TEST_DB = 'detforge_test'


# ── 纯逻辑 ─────────────────────────────────────────────────────────

class StratifiedSampleTests(unittest.TestCase):
    def test_per_type_cap(self):
        df = pd.DataFrame({'product_type': ['A', 'A', 'A', 'B', 'B', 'C'], 'x': range(6)})
        out = pb.stratified_sample_by_type(df, n=2, type_col='product_type', seed=1)
        self.assertEqual(len(out), 5)  # A:2 B:2 C:1
        self.assertEqual(out.groupby('product_type').size()['A'], 2)

    def test_missing_type_col_falls_back(self):
        df = pd.DataFrame({'x': range(10)})
        out = pb.stratified_sample_by_type(df, n=3, type_col='product_type', seed=1)
        self.assertEqual(len(out), 3)

    def test_seed_reproducible(self):
        df = pd.DataFrame({'product_type': ['A'] * 10, 'x': range(10)})
        a = pb.stratified_sample_by_type(df, n=4, seed=7)
        b = pb.stratified_sample_by_type(df, n=4, seed=7)
        self.assertEqual(list(a['x']), list(b['x']))

    def test_registered_in_namespace(self):
        self.assertIn('stratified_sample_by_type', pb.build_python_namespace())


class SchemaTests(unittest.TestCase):
    def test_statements_cover_five_tables(self):
        stmts = forge_db.schema_statements('detforge')
        joined = '\n'.join(stmts)
        for tbl in ('model_registry', 'job', 'job_item', 'predict_result', 'manual_qc'):
            self.assertIn(f'`detforge`.`{tbl}`', joined)
        self.assertTrue(stmts[0].startswith('CREATE DATABASE'))

    def test_qualified_name(self):
        self.assertEqual(forge_db._t('job', {'forge_database': 'foo'}), '`foo`.`job`')

    def test_json_roundtrip(self):
        self.assertEqual(forge_db._json_load(forge_db._json_dump({'a': 1})), {'a': 1})
        self.assertIsNone(forge_db._json_dump(None))

    def test_manual_qc_ddl_has_new_columns(self):
        joined = '\n'.join(forge_db.schema_statements('detforge'))
        self.assertIn('defect_type', joined)
        self.assertIn('qc_category', joined)

    def test_extra_columns_migration_defined(self):
        cols = {(t, c) for t, c, _ in forge_db._EXTRA_COLUMNS}
        self.assertIn(('manual_qc', 'qc_category'), cols)
        self.assertIn(('manual_qc', 'workflow_status'), cols)
        self.assertIn(('job_item', 'next_retry_at'), cols)


# ── 路径安全 ───────────────────────────────────────────────────────

class PathSafetyTests(unittest.TestCase):
    def test_within_root(self):
        root = tempfile.mkdtemp()
        try:
            self.assertTrue(forge_paths.is_within(os.path.join(root, 'a/b.png'), [root]))
            self.assertFalse(forge_paths.is_within('/etc/passwd', [root]))
            self.assertFalse(forge_paths.is_within(os.path.join(root, '../evil.png'), [root]))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_empty_path_rejected(self):
        self.assertFalse(forge_paths.is_within('', ['/tmp']))


# ── 人工质检（DB-free，monkeypatch）────────────────────────────────

class ManualQcLogicTests(unittest.TestCase):
    def setUp(self):
        self._orig = {
            'dup': forge_db.find_manual_qc_duplicate,
            'ins': forge_db.insert_manual_qc,
            'cats': forge_manual_qc.get_categories,
        }
        self.inserted = {}
        forge_db.find_manual_qc_duplicate = lambda *a, **k: None
        forge_db.insert_manual_qc = lambda row: (self.inserted.update(row) or 123)

    def tearDown(self):
        forge_db.find_manual_qc_duplicate = self._orig['dup']
        forge_db.insert_manual_qc = self._orig['ins']
        forge_manual_qc.get_categories = self._orig['cats']

    def test_no_match_archive(self):
        res = forge_manual_qc.archive_one('SN1', no_match=True, qc_category='拍不到', defect_type='划伤')
        self.assertEqual(res['match_status'], 'not_found')
        self.assertRegex(res.get('batch_id') or '', r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(res['qc_category'], '拍不到')
        self.assertEqual(self.inserted['defect_type'], '划伤')
        self.assertIsNone(self.inserted['matched_detail_id'])

    def test_dedup_blocks_without_force(self):
        forge_db.find_manual_qc_duplicate = lambda *a, **k: {'id': 7, 'qc_category': '拍不到'}
        with self.assertRaises(ValueError):
            forge_manual_qc.archive_one('SN1', customer_img_path='/x.png', no_match=True, qc_category='拍不到')

    def test_dedup_allows_with_force(self):
        forge_db.find_manual_qc_duplicate = lambda *a, **k: {'id': 7}
        res = forge_manual_qc.archive_one('SN1', customer_img_path='/x.png', no_match=True, qc_category='拍不到', force=True)
        self.assertEqual(res['duplicate_of'], 7)

    def test_strict_defect_type(self):
        forge_manual_qc.get_categories = lambda: {
            'defect_strict': True, 'defect_types': ['划伤'], 'imaging_categories': [],
        }
        with self.assertRaises(ValueError):
            forge_manual_qc.archive_one('SN1', no_match=True, qc_category='拍不到', defect_type='未知')


class ManualQcWorkflowTests(unittest.TestCase):
    def setUp(self):
        self._orig = {
            'dup': forge_db.find_manual_qc_duplicate,
            'ins': forge_db.insert_manual_qc,
            'upd': forge_db.update_manual_qc,
            'get': forge_db.get_manual_qc,
            'cats': forge_manual_qc.get_categories,
            'fetch': forge_manual_qc._fetch_detail_record,
        }
        self.store = {}

        def _insert(row):
            rid = len(self.store) + 1
            rec = dict(row)
            rec['id'] = rid
            self.store[rid] = rec
            return rid

        def _get(qc_id):
            return dict(self.store.get(int(qc_id)) or {})

        def _update(qc_id, fields):
            rec = self.store.get(int(qc_id))
            if not rec:
                return 0
            rec.update(fields)
            return 1

        forge_db.find_manual_qc_duplicate = lambda *a, **k: None
        forge_db.insert_manual_qc = _insert
        forge_db.get_manual_qc = _get
        forge_db.update_manual_qc = _update
        forge_manual_qc._fetch_detail_record = lambda did: {
            'id': did, 'img_path': '/p.jpg', 'origin_object_key': 'k', 'ext': {}, 'product_type': 'T',
        }

    def tearDown(self):
        forge_db.find_manual_qc_duplicate = self._orig['dup']
        forge_db.insert_manual_qc = self._orig['ins']
        forge_db.update_manual_qc = self._orig['upd']
        forge_db.get_manual_qc = self._orig['get']
        forge_manual_qc._fetch_detail_record = self._orig['fetch']
        forge_manual_qc.get_categories = self._orig['cats']

    def test_intake_and_confirm(self):
        res = forge_manual_qc.intake_one('SN1', customer_img_path='/c.jpg')
        self.assertEqual(res['workflow_status'], 'intake')
        qid = res['id']
        forge_manual_qc.save_review(
            qid, matched_detail_id=99, qc_category='成像清晰', defect_type='脏污',
        )
        self.assertEqual(self.store[qid]['workflow_status'], 'confirmed')
        out = forge_manual_qc.confirm_one(qid)
        self.assertEqual(out['workflow_status'], 'archived')
        self.assertIsNotNone(self.store[qid].get('archived_at'))


class ManualQcReviseTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.history = []
        self._orig = {
            'get': forge_db.get_manual_qc,
            'upd': forge_db.update_manual_qc,
            'ins_hist': forge_db.insert_manual_qc_history,
            'list_hist': forge_db.list_manual_qc_history,
            'cats': forge_manual_qc.get_categories,
            'fetch': forge_manual_qc._fetch_detail_record,
            'archive': forge_manual_qc.get_archive_settings,
            'sync': forge_manual_qc.sync_record_to_archive_root,
        }
        self.store[1] = {
            'id': 1,
            'workflow_status': 'archived',
            'product_no': 'SN1',
            'qc_category': '检出',
            'defect_type': '划伤',
            'note': 'old',
            'matched_detail_id': 10,
            'matched_img_path': '/p.jpg',
            'match_status': 'matched',
            'disposition': 'fp',
            'product_type': 'T',
        }

        def _get(qc_id):
            rec = self.store.get(int(qc_id))
            return dict(rec) if rec else None

        def _update(qc_id, fields):
            rec = self.store.get(int(qc_id))
            if not rec:
                return 0
            rec.update(fields)
            return 1

        def _insert_hist(qc_id, **kw):
            hid = len(self.history) + 1
            row = {'id': hid, 'qc_id': int(qc_id), **kw}
            self.history.append(row)
            return hid

        def _list_hist(qc_id, limit=100):
            return [dict(h) for h in self.history if h['qc_id'] == int(qc_id)][:limit]

        forge_db.get_manual_qc = _get
        forge_db.update_manual_qc = _update
        forge_db.insert_manual_qc_history = _insert_hist
        forge_db.list_manual_qc_history = _list_hist
        forge_manual_qc.get_categories = lambda: {'defect_strict': False, 'defect_types': []}
        forge_manual_qc._fetch_detail_record = lambda did: {
            'id': did, 'img_path': f'/p{did}.jpg', 'origin_object_key': 'k', 'ext': {}, 'product_type': 'T',
        }
        forge_manual_qc.get_archive_settings = lambda: {}
        forge_manual_qc.sync_record_to_archive_root = lambda **k: None

    def tearDown(self):
        forge_db.get_manual_qc = self._orig['get']
        forge_db.update_manual_qc = self._orig['upd']
        forge_db.insert_manual_qc_history = self._orig['ins_hist']
        forge_db.list_manual_qc_history = self._orig['list_hist']
        forge_manual_qc.get_categories = self._orig['cats']
        forge_manual_qc._fetch_detail_record = self._orig['fetch']
        forge_manual_qc.get_archive_settings = self._orig['archive']
        forge_manual_qc.sync_record_to_archive_root = self._orig['sync']

    def test_revise_writes_history(self):
        out = forge_manual_qc.update_archived_record(
            1, qc_category='漏检', defect_type='脏污', note='new note',
        )
        self.assertEqual(out['record']['qc_category'], '漏检')
        self.assertEqual(out['record']['defect_type'], '脏污')
        self.assertEqual(len(self.history), 1)
        self.assertIn('qc_category', self.history[0]['changed_fields'])
        rows = forge_manual_qc.list_record_history(1)
        self.assertEqual(len(rows), 1)

    def test_revise_rejects_non_archived(self):
        self.store[2] = {'id': 2, 'workflow_status': 'confirmed', 'qc_category': '检出',
                         'matched_detail_id': 1}
        with self.assertRaises(ValueError):
            forge_manual_qc.update_archived_record(2, qc_category='漏检')

    def test_revise_no_change_skips_history(self):
        out = forge_manual_qc.update_archived_record(1, qc_category='检出', defect_type='划伤', note='old')
        self.assertEqual(len(self.history), 0)
        self.assertIsNone(out['history_id'])


class ManualQcExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp_src = tempfile.mkdtemp()
        # 一张真实存在的客户图
        self.cust = os.path.join(self.tmp_src, 'cust.png')
        with open(self.cust, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
        self.out_dir = os.path.join(forge_manual_qc.BASE_DIR, 'exports', 'test_export_tmp')
        self._orig_list = forge_db.list_manual_qc
        forge_db.list_manual_qc = lambda **k: [{
            'id': 1, 'product_no': 'SN9', 'qc_category': '拍不到', 'defect_type': '划伤',
            'product_type': 'T', 'match_status': 'not_found', 'archived_at': '2026-01-01 00:00:00',
            'note': '', 'customer_img_path': self.cust, 'matched_img_path': None,
        }]

    def tearDown(self):
        forge_db.list_manual_qc = self._orig_list
        shutil.rmtree(self.tmp_src, ignore_errors=True)
        shutil.rmtree(self.out_dir, ignore_errors=True)

    def test_export_copies_and_manifest(self):
        res = forge_manual_qc.export_records(out_dir=self.out_dir, include='customer')
        self.assertEqual(res['copied'], 1)
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, '2026', '01', '01', '拍不到', 'SN9', '1__customer.png')))
        self.assertTrue(os.path.exists(res['manifest']))
        self.assertEqual(res.get('coco_count', 0), 0)

    def test_export_writes_coco_for_platform(self):
        plat = os.path.join(self.tmp_src, 'plat.png')
        shutil.copy(self.cust, plat)
        forge_db.list_manual_qc = lambda **k: [{
            'id': 2, 'product_no': 'SN9', 'qc_category': '检出', 'defect_type': '杂质',
            'product_type': 'T', 'match_status': 'matched', 'archived_at': '2026-01-01 00:00:00',
            'note': '', 'customer_img_path': self.cust, 'matched_img_path': plat,
            'defect_info': {'ext': {'original_predictions': [{
                'name': '杂质', 'points': [{'x': 1, 'y': 2, 'w': 10, 'h': 20}],
                'confidence': 0.9,
            }]}},
        }]
        res = forge_manual_qc.export_records(out_dir=self.out_dir, include='both')
        self.assertGreaterEqual(res['copied'], 1)
        self.assertGreaterEqual(res.get('coco_count', 0), 1)
        sn_coco = os.path.join(self.out_dir, '2026', '01', '01', '检出', 'SN9', '_annotations.coco.json')
        self.assertTrue(os.path.exists(sn_coco))
        self.assertFalse(os.path.exists(os.path.join(self.out_dir, '_annotations.coco.json')))
        self.assertFalse(os.path.exists(os.path.join(self.out_dir, '2026', '01', '01', '检出', '_annotations.coco.json')))

    def test_export_rejects_outside_dir(self):
        with self.assertRaises(ValueError):
            forge_manual_qc.export_records(out_dir='/tmp/not_allowed_export', include='customer')


class CleanupUploadsTests(unittest.TestCase):
    def setUp(self):
        self.upload_root = os.path.join(forge_manual_qc.BASE_DIR, 'uploads', 'manual_qc', 'test_cleanup')
        os.makedirs(self.upload_root, exist_ok=True)
        self.keep = os.path.join(self.upload_root, 'keep.png')
        self.orphan = os.path.join(self.upload_root, 'orphan.png')
        for p in (self.keep, self.orphan):
            with open(p, 'wb') as f:
                f.write(b'x')
        self._orig = forge_db.referenced_customer_imgs
        forge_db.referenced_customer_imgs = lambda: {self.keep}

    def tearDown(self):
        forge_db.referenced_customer_imgs = self._orig
        shutil.rmtree(self.upload_root, ignore_errors=True)

    def test_dry_run_lists_orphans(self):
        res = forge_manual_qc.cleanup_orphan_uploads(dry_run=True, root=self.upload_root)
        self.assertIn(os.path.abspath(self.orphan), res['orphans'])
        self.assertTrue(os.path.exists(self.orphan))  # dry run 不删

    def test_delete_orphans(self):
        res = forge_manual_qc.cleanup_orphan_uploads(dry_run=False, root=self.upload_root)
        self.assertGreaterEqual(res['deleted'], 1)
        self.assertFalse(os.path.exists(self.orphan))
        self.assertTrue(os.path.exists(self.keep))


class FrameworkInferTests(unittest.TestCase):
    def test_dino_and_hq(self):
        self.assertEqual(forge_service.infer_framework('dino'), ('dino', None))
        self.assertEqual(forge_service.infer_framework('rtdetr'), ('hq_det', 'rtdetr'))
        self.assertEqual(forge_service.infer_framework('unknown'), ('', None))
        self.assertEqual(forge_service.infer_framework('DET0307'), ('', None))
        self.assertEqual(forge_service.infer_framework('DETRTDETR'), ('hq_det', 'rtdetr'))

    @patch('studio.forge.forge_service.os.path.isfile', return_value=True)
    @patch('studio.forge.predict_runtime.detect_model_framework', return_value=('hq_det', 'dino2'))
    @patch('studio.forge.forge_db.upsert_model', return_value=99)
    def test_import_model_detects_from_checkpoint(self, mock_upsert, mock_detect, _mock_isfile):
        mid = forge_service.import_model({
            'name': 'V28',
            'checkpoint_path': __import__('os').path.join(__import__('tempfile').gettempdir(), 'fake.pt'),
            'model_type': 'DET0307',
            'source': 'modeldeploy',
        })
        self.assertEqual(mid, 99)
        payload = mock_upsert.call_args[0][0]
        self.assertEqual(payload['framework'], 'hq_det')
        self.assertEqual(payload['sub_type'], 'dino2')
        mock_detect.assert_called_once()

    @patch('studio.sync.forge_sync.resolve_dataset_output_dir')
    @patch('studio.forge.forge_db.get_sync_project')
    @patch('studio.forge.forge_db.get_sync_dataset')
    def test_build_predict_items_sync_dataset(self, mock_get_ds, mock_get_proj, mock_resolve):
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            img = os.path.join(tmp, 'a.jpg')
            open(img, 'wb').close()
            mock_get_ds.return_value = {'project_id': 1, 'name': 't-ds'}
            mock_get_proj.return_value = {'id': 1, 'approach_id': 598}
            mock_resolve.return_value = tmp
            items, meta = forge_service.build_predict_items({
                'type': 'sync_dataset',
                'sync_dataset_id': 9,
            })
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0].endswith('a.jpg'))
            self.assertIn(items[0], meta)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    @patch('studio.forge.forge_service.import_model')
    @patch('studio.forge.forge_service.os.path.isfile', return_value=True)
    @patch('studio.query.deployed_models.fetch_training_models')
    def test_import_train_model(self, mock_fetch, mock_isfile, mock_import):
        mock_fetch.return_value = {
            'models': [{
                'id': 7,
                'model_name': 'train-v1',
                'model_type': 'rtdetr',
                'full_path': 'D:/ckpt/best.pt',
                'path_resolvable': True,
                'labels': ['a'],
            }],
        }
        mock_import.return_value = 42
        mid = forge_service.import_train_model(7, 598)
        self.assertEqual(mid, 42)
        mock_import.assert_called_once()
        payload = mock_import.call_args[0][0]
        self.assertEqual(payload['source'], 'modeltrainconfig')
        self.assertEqual(payload['source_ref'], '7')


class PlatformPredictTests(unittest.TestCase):
    def test_annotations_to_predictions(self):
        from studio.forge import forge_platform_predict as fp
        pa = {
            'predictions': [
                {
                    'name': '划伤',
                    'confidence': 0.9,
                    'type': 'rect',
                    'points': [{'x': 1, 'y': 2, 'w': 3, 'h': 4}],
                },
                {
                    'name': '脏污',
                    'confidence': 0.05,
                    'type': 'rect',
                    'points': [{'x': 0, 'y': 0, 'w': 1, 'h': 1}],
                },
            ],
        }
        out = fp.annotations_to_predictions(pa, threshold=0.1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['name'], '划伤')

    def test_platform_model_id_negative(self):
        from studio.forge import forge_platform_predict as fp
        self.assertEqual(fp._platform_model_id(5182), -5182)

    def test_resolve_platform_predict_settings(self):
        from studio.forge import forge_platform_predict as fp
        s = fp.resolve_platform_predict_settings({
            'platform_predict_batch_size': 99,
            'platform_upload_chunk': 0,
            'platform_upload_write_timeout': 5000,
        })
        self.assertEqual(s['platform_predict_batch_size'], 50)
        self.assertEqual(s['platform_upload_chunk'], 1)
        self.assertEqual(s['platform_upload_write_timeout'], 5000)

    def test_parse_training_csv_fields(self):
        from studio.sync import platform_models as pm
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write('train_id,创建时间,模型版本,模型类型,训练时长,创建人,训练进度,数据集快照,备注\n')
            f.write('6115,2026-05-29,V28_19plus,高精度检测,10分钟,admin,,snap,\n')
        rows = pm._parse_csv(path)
        os.unlink(path)
        self.assertEqual(rows[0]['train_id'], 6115)
        self.assertEqual(rows[0]['model_name'], 'V28_19plus')

    @patch('studio.forge.forge_service.enqueue_platform_predict_job')
    @patch('studio.forge.forge_service.import_deploy_model')
    @patch('studio.forge.forge_service.build_predict_items')
    @patch('studio.forge.forge_db.get_sync_project')
    @patch('studio.forge.forge_db.get_sync_dataset')
    def test_batch_train_uses_platform_api(
        self, mock_get_ds, mock_get_proj, mock_build, mock_import_deploy, mock_platform,
    ):
        mock_get_ds.return_value = {'project_id': 1, 'name': 'ds1'}
        mock_get_proj.return_value = {'id': 1, 'approach_id': 598}
        mock_build.return_value = (['/tmp/a.jpg'], {'/tmp/a.jpg': {}})
        mock_platform.return_value = {'job_id': 99, 'total': 1, 'train_id': 7}
        with patch('studio.forge.forge_service._resolve_train_model_name', return_value='V17_test'):
            result = forge_service.enqueue_predict_jobs_batch(
                train_model_ids=[7],
                sync_dataset_id=1,
            )
        self.assertEqual(result['model_count'], 1)
        self.assertEqual(result['jobs'][0]['predict_mode'], 'platform_validation')
        mock_platform.assert_called_once()
        mock_import_deploy.assert_not_called()

    @patch('studio.forge.forge_service.enqueue_predict_job')
    @patch('studio.forge.forge_service.import_deploy_model')
    @patch('studio.forge.forge_service.build_predict_items')
    @patch('studio.forge.forge_db.get_sync_project')
    @patch('studio.forge.forge_db.get_sync_dataset')
    @patch('server.core.load_config')
    def test_batch_deploy_uses_local_approach_not_project(
        self, mock_load_cfg, mock_get_ds, mock_get_proj, mock_build, mock_import_deploy, mock_enqueue,
    ):
        mock_load_cfg.return_value = {'defect_approach_id': 18}
        mock_get_ds.return_value = {'project_id': 1, 'name': 'ds1'}
        mock_get_proj.return_value = {'id': 1, 'approach_id': 598}
        mock_build.return_value = (['/tmp/a.jpg'], {'/tmp/a.jpg': {}})
        mock_import_deploy.return_value = 42
        mock_enqueue.return_value = {'job_id': 1, 'total': 1}
        with patch('studio.forge.forge_db.get_model', return_value={'name': 'm1'}):
            forge_service.enqueue_predict_jobs_batch(
                deploy_model_ids=[7],
                sync_dataset_id=1,
            )
        mock_import_deploy.assert_called_once()
        self.assertEqual(mock_import_deploy.call_args[0][1], 18)


class ModelApiShapeTests(unittest.TestCase):
    def test_make_pred_ext_shape(self):
        sys.path.insert(0, forge_predict.DETUNIFY_PREDICT_DIR)
        import model_api
        pred = model_api.LoadedModel._make_pred('划伤', 0.873123, 10, 20, 30, 40)
        self.assertEqual(pred['name'], '划伤')
        self.assertEqual(pred['type'], 'rect')
        self.assertEqual(pred['points'][0], {'x': 10.0, 'y': 20.0, 'w': 30.0, 'h': 40.0})
        self.assertAlmostEqual(pred['confidence'], 0.873123, places=5)

    def test_build_ext_wrapper(self):
        ext = forge_predict._build_ext([{'name': 'x', 'confidence': 0.5}])
        self.assertIn('original_predictions', ext)
        self.assertEqual(len(ext['original_predictions']), 1)


# ── DB 相关（需 MySQL）────────────────────────────────────────────

def _db_available():
    try:
        from server.core import get_db_client
        client = get_db_client()
        return bool(client and client.ensure_alive())
    except Exception:
        return False


class _FakeLoadedModel:
    """假模型：每张图返回 1 个固定框，避免 torch / 真实权重。"""
    def __init__(self, boxes=1):
        self.boxes = boxes
        self.released = False

    def predict_one(self, img_path, threshold=None):
        preds = [{
            'name': '划伤', 'confidence': 0.9, 'type': 'rect',
            'points': [{'x': 1, 'y': 1, 'w': 10, 'h': 10}],
        } for _ in range(self.boxes)]
        return {'width': 100, 'height': 100, 'predictions': preds}

    def release(self):
        self.released = True


@unittest.skipUnless(_db_available(), 'MySQL 不可用')
class ForgeDbIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 用独立测试库，避免污染真实 detforge
        cls._orig_name = forge_db.forge_db_name
        forge_db.forge_db_name = lambda config=None: TEST_DB
        forge_db.ensure_schema()

    @classmethod
    def tearDownClass(cls):
        try:
            from server.core import get_db_client
            get_db_client().execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
        finally:
            forge_db.forge_db_name = cls._orig_name

    def setUp(self):
        from server.core import get_db_client
        client = get_db_client()
        for tbl in ('predict_result', 'job_item', 'job', 'model_registry', 'manual_qc'):
            client.execute(f"DELETE FROM `{TEST_DB}`.`{tbl}`")

    def _make_model(self):
        return forge_db.upsert_model({
            'name': 'unit-model', 'framework': 'hq_det', 'sub_type': 'rtdetr',
            'checkpoint_path': '/tmp/unit-model.pth', 'default_params': {'threshold': 0.5},
        })

    def test_model_upsert_idempotent(self):
        mid1 = self._make_model()
        mid2 = self._make_model()
        self.assertEqual(mid1, mid2)
        self.assertEqual(len(forge_db.list_models()), 1)

    def test_predict_job_writes_results(self):
        mid = self._make_model()
        items = ['/imgs/a.jpg', '/imgs/b.jpg', '/imgs/c.jpg']
        meta = {p: {'product_no': f'SN{i}', 'product_type': 'T1'} for i, p in enumerate(items)}
        job_id = forge_db.create_job('predict', 'unit', {'model_id': mid, 'items_meta': meta}, items=items)
        job = forge_db.get_job(job_id)
        self.assertEqual(job['total'], 3)

        forge_predict.run_predict_job(job, model_loader=lambda: _FakeLoadedModel(boxes=2))
        progress = forge_db.recompute_job_progress(job_id)
        self.assertEqual(progress['done'], 3)
        self.assertEqual(progress['remaining'], 0)

        rows = forge_db._client().fetchall(
            f"SELECT * FROM `{TEST_DB}`.`predict_result` WHERE job_id=%s", (job_id,))
        self.assertEqual(len(rows), 3)
        self.assertEqual(int(rows[0]['box_count']), 2)
        self.assertIn('original_predictions', forge_db._json_load(rows[0]['ext']))

    def test_resume_skips_done_items(self):
        mid = self._make_model()
        items = ['/imgs/a.jpg', '/imgs/b.jpg']
        job_id = forge_db.create_job('predict', 'resume', {'model_id': mid, 'items_meta': {}}, items=items)
        job = forge_db.get_job(job_id)
        forge_predict.run_predict_job(job, model_loader=lambda: _FakeLoadedModel())
        # 再次跑：无 pending，应不再新增结果
        before = forge_db._client().fetchone(
            f"SELECT COUNT(*) AS c FROM `{TEST_DB}`.`predict_result` WHERE job_id=%s", (job_id,))['c']
        forge_predict.run_predict_job(job, model_loader=lambda: _FakeLoadedModel())
        after = forge_db._client().fetchone(
            f"SELECT COUNT(*) AS c FROM `{TEST_DB}`.`predict_result` WHERE job_id=%s", (job_id,))['c']
        self.assertEqual(before, after)

    def test_job_control_transitions(self):
        mid = self._make_model()
        job_id = forge_db.create_job('predict', 'ctrl', {'model_id': mid}, items=['/x.jpg'])
        self.assertEqual(forge_db.job_control(job_id, 'pause'), 'paused')
        self.assertEqual(forge_db.job_control(job_id, 'resume'), 'pending')
        self.assertEqual(forge_db.job_control(job_id, 'cancel'), 'canceled')

    def test_interrupted_jobs_flow(self):
        mid = self._make_model()
        job_id = forge_db.create_job('predict', 'interrupt', {'model_id': mid}, items=['/a.jpg', '/b.jpg'])
        forge_db.update_job(job_id, status='running')
        n = forge_db.pause_active_jobs_for_service_stop(reason='test')
        self.assertGreaterEqual(n, 1)
        jobs = forge_db.list_interrupted_jobs()
        self.assertTrue(any(j['id'] == job_id for j in jobs))
        forge_db.resolve_interrupted_jobs('resume', job_ids=[job_id])
        job = forge_db.get_job(job_id)
        self.assertEqual(job['status'], 'pending')
        self.assertIsNone((job.get('params') or {}).get('interrupted_at'))

    def test_claim_next_job(self):
        mid = self._make_model()
        job_id = forge_db.create_job('predict', 'claim', {'model_id': mid}, items=['/x.jpg'])
        claimed = forge_db.claim_next_job('w1', ['predict'])
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed['id'], job_id)
        self.assertEqual(claimed['status'], 'running')
        self.assertIsNone(forge_db.claim_next_job('w1', ['predict']))  # 已无 pending


class WorkerLaneTests(unittest.TestCase):
    def test_default_lanes_split_predict_and_sync(self):
        import worker
        saved = {
            k: os.environ.get(k)
            for k in ('PC_WORKER_CONCURRENCY', 'PC_WORKER_PREDICT_SLOTS', 'PC_WORKER_SYNC_SLOTS')
        }
        try:
            for k in saved:
                os.environ.pop(k, None)
            lanes = worker.resolve_worker_lanes()
            names = [lane['name'] for lane in lanes]
            self.assertIn('predict', names)
            self.assertIn('sync', names)
            self.assertGreaterEqual(worker.WorkerManager().concurrency, 2)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class WorkflowGraphTests(unittest.TestCase):
    def test_linear_to_graph(self):
        from studio.forge.workflow_graph import linear_steps_to_graph, topological_steps
        steps = [
            {'id': 'a', 'kind': 'query', 'params': {}},
            {'id': 'b', 'kind': 'predict', 'params': {}, 'requires': ['a']},
        ]
        g = linear_steps_to_graph(steps)
        self.assertEqual(len(g['nodes']), 2)
        self.assertEqual(len(g['edges']), 1)
        order = [s['id'] for s in topological_steps(g['nodes'], g['edges'])]
        self.assertEqual(order, ['a', 'b'])

    def test_branch_edge_eval(self):
        from studio.forge.workflow_graph import eval_edge_when
        self.assertTrue(eval_edge_when('empty', 'skipped', {'reason': 'empty_result'}))
        self.assertTrue(eval_edge_when('not_empty', 'done', {'row_count': 5}))
        self.assertTrue(eval_edge_when('empty', 'done', {'row_count': 0}))
        self.assertFalse(eval_edge_when('not_empty', 'skipped', {'reason': 'empty_result'}))

    def test_normalize_v2_graph(self):
        from studio.forge.workflow_graph import normalize_definition
        d = normalize_definition({
            'version': 2,
            'graph': {
                'nodes': [
                    {'id': 'q', 'kind': 'query'},
                    {'id': 'n', 'kind': 'notify'},
                ],
                'edges': [
                    {'from': 'q', 'to': 'n', 'when': 'empty'},
                ],
            },
        })
        self.assertEqual(len(d['steps']), 2)
        self.assertIn('graph', d)


class WorkflowTests(unittest.TestCase):
    def test_builtin_templates_defined(self):
        from studio.forge.workflow_templates import BUILTIN_TEMPLATES
        ids = {t['id'] for t in BUILTIN_TEMPLATES}
        self.assertIn('daily_ng_curation', ids)
        self.assertIn('weekly_predict_eval', ids)

    def test_resolve_templates(self):
        from studio.forge.workflow_steps import resolve_templates
        ctx = {
            'params': {'strategy_id': 'daily_trawl', 'model_id': 3},
            'steps': {'query': {'task_id': 'abc-123', 'row_count': 10}},
        }
        out = resolve_templates({
            'task_id': '{{steps.query.task_id}}',
            'strategy_id': '{{params.strategy_id}}',
        }, ctx)
        self.assertEqual(out['task_id'], 'abc-123')
        self.assertEqual(out['strategy_id'], 'daily_trawl')

    def test_cron_next_run(self):
        from studio.forge.workflow_scheduler import compute_next_run
        nra = compute_next_run('0 2 * * *')
        self.assertRegex(nra, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
        self.assertTrue(nra.endswith(':00:00') and ' 02:00:00' in nra)

    def test_schema_includes_workflow_tables(self):
        joined = '\n'.join(forge_db.schema_statements('detforge'))
        for tbl in ('workflow_template', 'workflow_schedule', 'workflow_run', 'workflow_step_run'):
            self.assertIn(f'`detforge`.`{tbl}`', joined)

    def test_empty_query_marks_skipped(self):
        from studio.forge.workflow_steps import run_query_step
        with patch('studio.forge.workflow_steps.execute_strategy_ref') as mock_exec:
            mock_exec.return_value = {'count': 0, 'task_id': None}
            out = run_query_step({'strategy_id': 'daily_trawl'}, {'run_id': 1})
        self.assertTrue(out.get('skipped'))
        self.assertEqual(out.get('reason'), 'empty_result')


class JobLogTests(unittest.TestCase):
    def test_append_throttled(self):
        from studio.forge import job_log
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            orig = job_log.LOG_DIR
            job_log.LOG_DIR = tmp
            try:
                job_log._throttle_state.clear()
                job_log.append_throttled(999, 'a', min_interval=60)
                self.assertIsNone(job_log.append_throttled(999, 'b', min_interval=60))
                job_log.append_throttled(999, 'c', min_interval=0)
                lines = job_log.read_tail(999)
                self.assertEqual(len(lines), 2)
            finally:
                job_log.LOG_DIR = orig


if __name__ == '__main__':
    unittest.main()
