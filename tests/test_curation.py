"""筛选批次纯逻辑单测 + 可选 MySQL 集成。"""
import csv
import io
import json
import os
import tempfile
import unittest

import pandas as pd

from studio.curation import curation_service
from studio.forge import forge_db

TEST_DB = 'detforge_test'


def _db_available():
    try:
        from server.core import get_db_client
        get_db_client().fetchone('SELECT 1 AS x')
        return True
    except Exception:
        return False


class NormalizeDecisionTests(unittest.TestCase):
    def test_keep_variants(self):
        for v in ('keep', '保留', '1', 'y', 'YES'):
            self.assertEqual(curation_service.normalize_decision(v), 'keep')

    def test_reject_variants(self):
        for v in ('reject', '剔除', '0', 'n'):
            self.assertEqual(curation_service.normalize_decision(v), 'reject')

    def test_pending(self):
        self.assertEqual(curation_service.normalize_decision(''), 'pending')
        self.assertEqual(curation_service.normalize_decision(None), 'pending')


class ParseImportCsvTests(unittest.TestCase):
    def test_parse_decisions(self):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=['batch_row_id', 'img_name', 'decision', 'reject_reason'])
        writer.writeheader()
        writer.writerow({'batch_row_id': 'cb_x-r00001', 'img_name': 'a.jpg', 'decision': 'keep', 'reject_reason': ''})
        writer.writerow({'batch_row_id': 'cb_x-r00002', 'img_name': 'b.jpg', 'decision': '剔除', 'reject_reason': '模糊'})
        rows = curation_service.parse_import_csv(buf.getvalue())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['decision'], 'keep')
        self.assertEqual(rows[1]['decision'], 'reject')

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            curation_service.parse_import_csv('batch_row_id,decision\n')


class FilterCocoTests(unittest.TestCase):
    def test_filter_keep_names(self):
        coco = {
            'images': [{'id': 1, 'file_name': 'a.jpg'}, {'id': 2, 'file_name': 'b.jpg'}],
            'annotations': [{'id': 1, 'image_id': 1}, {'id': 2, 'image_id': 2}],
            'categories': [],
        }
        td = tempfile.mkdtemp()
        path = os.path.join(td, 'coco.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(coco, f)
        out = curation_service._filter_coco_keep(path, ['a.jpg'])
        self.assertEqual(len(out['images']), 1)
        self.assertEqual(out['images'][0]['file_name'], 'a.jpg')
        self.assertEqual(len(out['annotations']), 1)


class ImportCocoTests(unittest.TestCase):
    def test_coco_keep_file_names(self):
        coco = {'images': [{'file_name': 'A.JPG'}, {'file_name': 'b.png'}]}
        names = curation_service.coco_keep_file_names(coco)
        self.assertEqual(names, {'a.jpg', 'b.png'})

    def test_merge_import_coco_logic(self):
        """无 DB：只测 parse + keep names。"""
        coco = {'images': [{'file_name': 'fake1.jpg'}], 'annotations': [], 'categories': []}
        names = curation_service.coco_keep_file_names(coco)
        self.assertIn('fake1.jpg', names)


class SchemaCurationTests(unittest.TestCase):
    def test_ddl_contains_curation_tables(self):
        joined = '\n'.join(forge_db.schema_statements('detforge'))
        self.assertIn('curation_batch', joined)
        self.assertIn('curation_item', joined)


@unittest.skipUnless(_db_available(), 'MySQL 不可用')
class CurationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        for tbl in ('curation_item', 'curation_batch'):
            client.execute(f"DELETE FROM `{TEST_DB}`.`{tbl}`")
        from flask import Flask
        self.app = Flask(__name__)
        self.app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
        self.task_id = 'test-task-curation'
        self.task_dir = os.path.join(self.app.config['UPLOAD_FOLDER'], self.task_id)
        os.makedirs(self.task_dir, exist_ok=True)
        df = pd.DataFrame([
            {'img_path': '/tmp/fake1.jpg', 'product_no': 'SN1', 'product_type': 'T1', 'check_status': '1', 'ext': ''},
            {'img_path': '/tmp/fake2.jpg', 'product_no': 'SN2', 'product_type': 'T2', 'check_status': '0', 'ext': ''},
        ])
        df.to_csv(os.path.join(self.task_dir, 'result.csv'), index=False)
        with open(os.path.join(self.task_dir, 'query_meta.json'), 'w', encoding='utf-8') as f:
            json.dump({'strategy_id': 'daily_trawl', 'strategy_name': 'Daily'}, f)
        coco = {
            'info': {},
            'images': [
                {'id': 0, 'file_name': 'fake1.jpg'},
                {'id': 1, 'file_name': 'fake2.jpg'},
            ],
            'annotations': [],
            'categories': [],
        }
        with open(os.path.join(self.task_dir, '_annotations.coco.json'), 'w', encoding='utf-8') as f:
            json.dump(coco, f)

    def test_create_export_import_archive(self):
        with self.app.app_context():
            batch = curation_service.create_from_task(self.task_id, strategy_id='daily_trawl')
            self.assertTrue(batch['batch_code'].startswith('cb_'))
            bid = batch['id']

            exp = curation_service.export_batch(bid, include_images=False)
            self.assertTrue(os.path.isdir(exp['out_dir']))
            self.assertTrue(os.path.isfile(os.path.join(exp['out_dir'], '_annotations.coco.json')))

            curated = {
                'info': {},
                'images': [{
                    'id': 0,
                    'file_name': 'fake1.jpg',
                    'extra': {'disposition': 'need_label', 'need_platform_label': True},
                }],
                'annotations': [],
                'categories': [],
            }
            imp = curation_service.import_coco(bid, curated)
            self.assertEqual(imp['matched_keep'], 1)
            self.assertEqual(imp['keep'], 1)
            self.assertEqual(imp['reject'], 1)

            items = forge_db.list_curation_items(bid, decision='keep')
            self.assertEqual(items[0].get('disposition'), 'need_label')
            self.assertTrue(items[0].get('need_platform_label'))

            arch = curation_service.archive_batch(bid, copy_images=False)
            self.assertEqual(arch['keep_count'], 1)
            updated = forge_db.get_curation_batch(bid)
            self.assertEqual(updated['status'], 'archived')

    def test_delete_batch(self):
        with self.app.app_context():
            batch = curation_service.create_from_task(self.task_id, strategy_id='daily_trawl')
            bid = batch['id']
            self.assertIsNotNone(forge_db.get_curation_batch(bid))
            self.assertGreater(forge_db.count_curation_items(bid), 0)

            result = curation_service.delete_batch(bid)
            self.assertEqual(result['id'], bid)
            self.assertIsNone(forge_db.get_curation_batch(bid))
            self.assertEqual(forge_db.count_curation_items(bid), 0)

            with self.assertRaises(ValueError):
                curation_service.delete_batch(bid)


if __name__ == '__main__':
    unittest.main()
