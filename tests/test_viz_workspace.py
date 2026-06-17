"""样本图库 .viz 沙箱单测。"""
import json
import os
import tempfile
import unittest

from studio.export.viz_workspace import (
    COCO_SUBDIR,
    build_viz_workspace,
    clean_stale_coco_artifacts,
    prepare_export_dir_for_viz,
    should_use_viz_workspace,
)


class TestVizWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.export_dir = self.tmp.name
        self.img_path = os.path.join(self.export_dir, 'photo.jpg')
        with open(self.img_path, 'wb') as f:
            f.write(b'\xff\xd8\xff\xd9')

    def tearDown(self):
        self.tmp.cleanup()

    def _write_main_coco(self, *, with_source=True):
        img = {
            'id': 0,
            'file_name': 'photo.jpg',
            'width': 10,
            'height': 10,
        }
        if with_source:
            img['source_path'] = '/prod/line'
        coco = {
            'images': [img],
            'categories': [{'id': 1, 'name': '脏污'}],
            'annotations': [{
                'id': 1,
                'image_id': 0,
                'category_id': 1,
                'bbox': [0, 0, 5, 5],
            }],
            'source_dirs': {'/prod': '/prod'},
            'source_coco_paths': {'/prod': '/prod/_annotations.coco.json'},
        }
        with open(os.path.join(self.export_dir, '_annotations.coco.json'), 'w', encoding='utf-8') as f:
            json.dump(coco, f)
        with open(os.path.join(self.export_dir, 'result.csv'), 'w', encoding='utf-8') as f:
            f.write('img_path\n' + self.img_path + '\n')

    def test_should_use_for_query_task(self):
        self._write_main_coco()
        self.assertTrue(should_use_viz_workspace(self.export_dir))

    def test_clean_removes_pred_sidecar(self):
        self._write_main_coco()
        sidecar = os.path.join(self.export_dir, '_annotations.m.pred.coco.json')
        with open(sidecar, 'w', encoding='utf-8') as f:
            json.dump({'images': []}, f)
        n = clean_stale_coco_artifacts(self.export_dir)
        self.assertGreaterEqual(n, 1)
        self.assertFalse(os.path.isfile(sidecar))
        self.assertTrue(os.path.isfile(os.path.join(self.export_dir, '_annotations.coco.json')))

    def test_prepare_export_dir_for_viz(self):
        self._write_main_coco()
        coco_path, image_dir = build_viz_workspace(self.export_dir)
        norm = coco_path.replace('\\', '/')
        self.assertTrue(norm.endswith(f'{COCO_SUBDIR}/_annotations.coco.json'))
        self.assertEqual(os.path.abspath(image_dir), os.path.abspath(self.export_dir))
        with open(coco_path, encoding='utf-8') as f:
            viz = json.load(f)
        self.assertNotIn('source_dirs', viz)
        self.assertNotIn('source_coco_paths', viz)
        self.assertNotIn('source_path', viz['images'][0])
        fn = viz['images'][0]['file_name'].replace('\\', '/')
        self.assertTrue(os.path.isabs(fn) or os.path.isfile(fn))
        self.assertEqual(os.path.normpath(fn), os.path.normpath(self.img_path))
        self.assertTrue(os.path.isfile(os.path.join(self.export_dir, '_annotations.coco.json')))

    def test_viz_maps_predict_id_and_row_index(self):
        """预测结果 CSV 含 id 列时，COCO image.id 仍可为 0..n-1。"""
        coco = {
            'images': [{'id': 0, 'file_name': 'x.jpg', 'width': 1, 'height': 1}],
            'categories': [],
            'annotations': [],
        }
        with open(os.path.join(self.export_dir, '_annotations.coco.json'), 'w', encoding='utf-8') as f:
            json.dump(coco, f)
        with open(os.path.join(self.export_dir, 'result.csv'), 'w', encoding='utf-8') as f:
            f.write('id,img_path,_viz_id\n99999,' + self.img_path + ',0\n')
        coco_path, _ = build_viz_workspace(self.export_dir)
        with open(coco_path, encoding='utf-8') as f:
            viz = json.load(f)
        self.assertEqual(
            os.path.normpath(viz['images'][0]['file_name']),
            os.path.normpath(self.img_path),
        )

    def test_prepare_skips_rebuild_when_viz_coco_fresh(self):
        self._write_main_coco()
        path1, _ = prepare_export_dir_for_viz(self.export_dir)
        mtime1 = os.path.getmtime(path1)
        path2, _ = prepare_export_dir_for_viz(self.export_dir)
        self.assertEqual(path1, path2)
        self.assertEqual(os.path.getmtime(path2), mtime1)


if __name__ == '__main__':
    unittest.main()
