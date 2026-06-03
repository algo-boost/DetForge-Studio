"""pred/GT 分层 COCO 导出集成测试。"""
import json
import os
import tempfile
import unittest

from studio.export.pred_coco_layout import (
    build_predict_view_coco,
    ensure_predict_annotations_for_export,
    find_nearby_gt_coco,
    load_pred_annotations_by_image_id,
    remove_pred_sidecars,
    merge_gt_categories,
    merge_pred_sidecars_into_coco,
    pred_coco_filename,
    align_pred_sidecars_to_gt_images,
    list_pred_sidecar_paths,
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
            'ext': {'original_predictions': [{'name': '脏污', 'confidence': 0.9, 'bbox': [1, 2, 3, 4]}]},
        }]
        gt_path, pred_path, count, sources = build_predict_view_coco(
            rows,
            export_dir=self.export_dir,
            model_name='TestModel',
            image_id_key='id',
        )
        self.assertEqual(count, 1)
        self.assertTrue(os.path.isfile(gt_path))
        self.assertIsNone(pred_path)
        with open(gt_path, encoding='utf-8') as f:
            gt = json.load(f)
        self.assertEqual(len(gt['images']), 1)
        self.assertGreater(len(gt.get('annotations') or []), 0)
        fn = gt['images'][0]['file_name']
        self.assertEqual(fn, '1_sample.jpg')
        self.assertFalse(os.path.isabs(fn))

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

    def test_merge_pred_sidecars_into_main_coco_for_export(self):
        rows = [{
            'id': 1,
            'img_path': self.img_path,
            'ext': {'original_predictions': [
                {'name': '脏污', 'confidence': 0.9, 'points': [{'x': 1, 'y': 2, 'w': 10, 'h': 8}]},
            ]},
        }]
        gt_path, pred_path, count, _ = build_predict_view_coco(
            rows, export_dir=self.export_dir, model_name='TestModel', image_id_key='id',
        )
        self.assertIsNone(pred_path)
        with open(gt_path, encoding='utf-8') as f:
            gt = json.load(f)
        self.assertGreater(len(gt.get('annotations') or []), 0)
        with open(gt_path, encoding='utf-8') as f:
            gt = json.load(f)
        self.assertGreater(len(gt.get('annotations') or []), 0)
        merged = merge_pred_sidecars_into_coco(gt, self.export_dir)
        self.assertGreaterEqual(len(merged.get('annotations') or []), len(gt.get('annotations') or []))
        self.assertEqual(merged['annotations'][0]['image_id'], 1)
        cat_names = {c['name'] for c in merged.get('categories') or []}
        self.assertNotIn('窗户按钮', cat_names)

    def test_load_annotations_from_main_coco(self):
        rows = [{
            'id': 0,
            'img_path': self.img_path,
            'ext': {'original_predictions': [
                {'name': '脏污', 'confidence': 0.8, 'bbox': [0, 0, 5, 5]},
            ]},
        }]
        build_predict_view_coco(rows, export_dir=self.export_dir, model_name='M', image_id_key='id')
        by_img = load_pred_annotations_by_image_id(self.export_dir)
        self.assertIn(0, by_img)
        self.assertEqual(len(by_img[0]), 1)

    def test_ensure_predict_from_csv_when_no_sidecar(self):
        import pandas as pd
        csv_path = os.path.join(self.export_dir, 'result.csv')
        ext = json.dumps({'original_predictions': [
            {'name': '焊丝', 'confidence': 0.8, 'bbox': [0, 0, 5, 5]},
        ]}, ensure_ascii=False)
        pd.DataFrame([{
            'img_path': self.img_path,
            'ext': ext,
        }]).to_csv(csv_path, index=False)
        coco = {'images': [{'id': 0, 'file_name': 'sample.jpg'}], 'categories': [], 'annotations': []}
        out = ensure_predict_annotations_for_export(coco, self.export_dir)
        self.assertGreater(len(out.get('annotations') or []), 0)

    def test_align_pred_sidecar_file_name_to_gt(self):
        rows = [{
            'id': 1,
            'img_path': self.img_path,
            'ext': {'original_predictions': [
                {'name': '脏污', 'confidence': 0.9, 'bbox': [1, 2, 3, 4]},
            ]},
        }]
        build_predict_view_coco(
            rows, export_dir=self.export_dir, model_name='M', image_id_key='id',
            emit_pred_sidecar=True,
        )
        sidecar = list_pred_sidecar_paths(self.export_dir)[0]
        with open(sidecar, encoding='utf-8') as f:
            pred = json.load(f)
        pred['images'][0]['file_name'] = 'sample.jpg'
        with open(sidecar, 'w', encoding='utf-8') as f:
            json.dump(pred, f)
        self.assertTrue(align_pred_sidecars_to_gt_images(self.export_dir))
        with open(sidecar, encoding='utf-8') as f:
            pred = json.load(f)
        self.assertEqual(pred['images'][0]['file_name'], '1_sample.jpg')

    def test_sanitize_model_slug_edge_cases(self):
        self.assertEqual(sanitize_model_slug(None), 'predict')
        self.assertEqual(sanitize_model_slug('  '), 'predict')
        self.assertTrue(len(sanitize_model_slug('x' * 100)) <= 64)


if __name__ == '__main__':
    unittest.main()
