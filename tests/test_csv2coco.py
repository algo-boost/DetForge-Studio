"""csv2coco 集成测试（无需数据库）。"""
import json
import os
import tempfile
import unittest

import pandas as pd

from studio.export.csv2coco import build_coco_info, csv2coco


class Csv2CocoTests(unittest.TestCase):
    def test_build_coco_info(self):
        info = build_coco_info({'strategy_name': '日常捞图', 'sample_size': 200})
        self.assertEqual(info['strategy_name'], '日常捞图')
        self.assertEqual(info['sample_size'], 200)
        self.assertIn('description', info)

    def test_csv2coco_ext_annotations(self):
        ext = json.dumps({
            'original_predictions': [
                {'name': '脏污', 'confidence': 0.85, 'points': [{'x': 1, 'y': 2, 'w': 10, 'h': 20}]},
                {'name': '焊丝', 'confidence': 0.5, 'points': [{'x': 30, 'y': 40, 'w': 5, 'h': 6}]},
            ],
        })
        df = pd.DataFrame([{
            'img_path': '/tmp/test_img_001.jpg',
            'ext': ext,
            'product_no': 'SN001',
            'product_type': 'M1',
            'product_id': 'P1',
            'c_time': '2026-05-01 10:00:00',
            'check_status': '1',
        }])
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, 'result.csv')
            coco_path = os.path.join(tmp, '_annotations.coco.json')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            csv2coco(csv_path, coco_path, query_meta={'strategy_name': 'test'})
            with open(coco_path, encoding='utf-8') as f:
                coco = json.load(f)
        self.assertEqual(len(coco['images']), 1)
        self.assertEqual(coco['images'][0]['product_no'], 'SN001')
        self.assertEqual(coco['images'][0]['product_type'], 'M1')
        self.assertGreaterEqual(len(coco['annotations']), 2)
        self.assertEqual(coco['info']['strategy_name'], 'test')
        cat_names = {c['name'] for c in coco['categories']}
        self.assertIn('脏污', cat_names)
        self.assertIn('焊丝', cat_names)


if __name__ == '__main__':
    unittest.main()
