"""pred/GT 分层 COCO 导出集成测试。"""
import json
import os
import tempfile
import unittest

from studio.export.pred_coco_layout import (
    build_predict_view_coco,
    find_nearby_gt_coco,
    load_pred_annotations_by_image_id,
    merge_gt_categories,
    pred_coco_filename,
    sanitize_model_slug,
    write_pred_sidecar,
)


class TestPredCocoExportIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.export_dir = self.tmp.name
        self.img_path = os.path.join(self.export_dir, 'sample.jpg')
        with open(self.img_path, 'wb') as f:
            f.write(b'\xff\xd8\xff\xd9')

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_predict_view_coco_minimal(self):
        rows = [{
            'id': 1,
            'img_path': self.img_path,
            'img_width': 100,
            'img_height': 80,
            'product_no': 'SN001',
            'ext': {'original_predictions': [{'name': 'scratch', 'score': 0.9, 'bbox': [1, 2, 3, 4]}]},
        }]
        gt_path, pred_path, count, sources = build_predict_view_coco(
            rows,
            export_dir=self.export_dir,
            model_name='TestModel',
        )
        self.assertEqual(count, 1)
        self.assertTrue(os.path.isfile(gt_path))
        self.assertTrue(os.path.isfile(pred_path))
        self.assertTrue(pred_path.endswith(pred_coco_filename('TestModel')))
        with open(gt_path, encoding='utf-8') as f:
            gt = json.load(f)
        self.assertEqual(len(gt['images']), 1)
        self.assertTrue(gt['images'][0]['file_name'].endswith('sample.jpg'))

    def test_write_pred_sidecar_and_load(self):
        images = [{'id': 1, 'file_name': 'a.jpg'}]
        categories = [{'id': 1, 'name': 'scratch'}]
        annotations = [{'id': 1, 'image_id': 1, 'category_id': 1, 'bbox': [0, 0, 1, 1]}]
        path = write_pred_sidecar(self.export_dir, 'm1', images, categories, annotations)
        self.assertTrue(os.path.isfile(path))
        by_img = load_pred_annotations_by_image_id(self.export_dir)
        self.assertIn(1, by_img)
        self.assertEqual(len(by_img[1]), 1)

    def test_find_nearby_gt_coco_none_when_missing(self):
        gt, path = find_nearby_gt_coco(self.img_path)
        self.assertIsNone(gt)
        self.assertIsNone(path)

    def test_merge_gt_categories_dedupes_by_name(self):
        target = [{'id': 1, 'name': 'a'}]
        merge_gt_categories(target, [{'id': 99, 'name': 'a'}, {'id': 2, 'name': 'b'}])
        names = {c['name'] for c in target}
        self.assertIn('a', names)
        self.assertIn('b', names)

    def test_sanitize_model_slug_edge_cases(self):
        self.assertEqual(sanitize_model_slug(None), 'predict')
        self.assertEqual(sanitize_model_slug('  '), 'predict')
        self.assertTrue(len(sanitize_model_slug('x' * 100)) <= 64)


if __name__ == '__main__':
    unittest.main()
