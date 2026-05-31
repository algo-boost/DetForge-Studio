"""annotation_parser 单元测试。"""
import json
import unittest

import pandas as pd

from studio.export.annotation_parser import (
    bbox_from_prediction,
    build_name2id_maps,
    parse_row_predictions,
    predictions_to_coco_annotations,
    resolve_category_id,
)


class AnnotationParserTests(unittest.TestCase):
    def test_bbox_from_points(self):
        pred = {'name': '脏污', 'confidence': 0.9, 'points': [{'x': 10, 'y': 20, 'w': 30, 'h': 40}]}
        self.assertEqual(bbox_from_prediction(pred), [10.0, 20.0, 30.0, 40.0])

    def test_bbox_from_bbox_field(self):
        pred = {'name': '划伤', 'bbox': [1, 2, 3, 4]}
        self.assertEqual(bbox_from_prediction(pred), [1.0, 2.0, 3.0, 4.0])

    def test_parse_ext_only(self):
        ext = json.dumps({
            'original_predictions': [
                {'name': '脏污', 'confidence': 0.8, 'points': [{'x': 0, 'y': 0, 'w': 10, 'h': 10}]},
            ],
        })
        row = pd.Series({'ext': ext})
        preds = parse_row_predictions(row)
        self.assertEqual(len(preds), 1)
        self.assertEqual(preds[0]['name'], '脏污')
        self.assertEqual(preds[0]['source'], 'ext')

    def test_parse_infer_raw_only(self):
        infer = json.dumps({
            'predictions': [
                {'name': '线头', 'confidence': 0.5, 'points': [{'x': 5, 'y': 5, 'w': 8, 'h': 8}]},
            ],
        })
        row = pd.Series({'infer_raw_result': infer})
        preds = parse_row_predictions(row)
        self.assertEqual(len(preds), 1)
        self.assertEqual(preds[0]['source'], 'infer_raw_result')

    def test_dedup_ext_and_infer(self):
        ext = json.dumps({
            'original_predictions': [
                {'name': '脏污', 'confidence': 0.8, 'points': [{'x': 1, 'y': 2, 'w': 3, 'h': 4}]},
            ],
        })
        infer = json.dumps({
            'predictions': [
                {'name': '脏污', 'confidence': 0.7, 'points': [{'x': 1, 'y': 2, 'w': 3, 'h': 4}]},
                {'name': '其他', 'confidence': 0.6, 'points': [{'x': 10, 'y': 10, 'w': 5, 'h': 5}]},
            ],
        })
        row = pd.Series({'ext': ext, 'infer_raw_result': infer})
        preds = parse_row_predictions(row)
        self.assertEqual(len(preds), 2)
        names = {p['name'] for p in preds}
        self.assertEqual(names, {'脏污', '其他'})

    def test_unknown_category_registered(self):
        id2name = {0: '其他', 14: '脏污'}
        _, name2id = build_name2id_maps(id2name)
        categories = [{'id': 0, 'name': '其他'}, {'id': 14, 'name': '脏污'}]
        cat_id = resolve_category_id('焊丝', name2id, id2name, categories)
        self.assertEqual(cat_id, 15)
        self.assertIn({'id': 15, 'name': '焊丝'}, categories)

    def test_predictions_to_coco_annotations(self):
        id2name = {14: '脏污'}
        _, name2id = build_name2id_maps(id2name)
        categories = [{'id': 14, 'name': '脏污'}]
        preds = [{'name': '脏污', 'confidence': 0.9, 'bbox': [0, 0, 10, 10], 'source': 'ext'}]
        anns = predictions_to_coco_annotations(0, preds, name2id, id2name, categories)
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0]['category_id'], 14)
        self.assertEqual(anns[0]['area'], 100)


if __name__ == '__main__':
    unittest.main()
