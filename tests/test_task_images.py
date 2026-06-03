"""task 目录图片路径解析。"""
import os
import tempfile
import unittest

from studio.export.task_images import (
    _load_csv_paths_by_image_id,
    normalize_coco_images_for_task,
    resolve_task_image_path,
)


class TaskImagesTests(unittest.TestCase):
    def test_resolve_prefixed_copy_name(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, '0_photo.jpg')
            with open(src, 'wb') as f:
                f.write(b'x')
            path, arc = resolve_task_image_path(
                td, 0, coco_file_name='photo.jpg', csv_img_path='D:/data/photo.jpg',
            )
            self.assertEqual(path, src)
            self.assertEqual(arc, '0_photo.jpg')

    def test_normalize_export_uses_basename_from_csv(self):
        with tempfile.TemporaryDirectory() as td:
            remote = os.path.join(td, 'remote', 'a.png')
            os.makedirs(os.path.dirname(remote), exist_ok=True)
            with open(remote, 'wb') as f:
                f.write(b'x')
            with open(os.path.join(td, 'result.csv'), 'w', encoding='utf-8') as f:
                f.write('img_path\n' + remote.replace('\\', '/') + '\n')
            coco = {
                'images': [{'id': 0, 'file_name': 'a.png'}],
                'annotations': [],
                'categories': [],
            }
            files = normalize_coco_images_for_task(td, coco, None, for_export=True)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0][0], os.path.abspath(remote))
            self.assertEqual(coco['images'][0]['file_name'], 'a.png')

    def test_normalize_legacy_prefixed_copy(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, '1_a.png')
            with open(src, 'wb') as f:
                f.write(b'x')
            coco = {
                'images': [{'id': 1, 'file_name': 'a.png'}],
                'annotations': [],
                'categories': [],
            }
            files = normalize_coco_images_for_task(td, coco, None, for_export=True)
            self.assertEqual(len(files), 1)
            self.assertEqual(coco['images'][0]['file_name'], '1_a.png')


    def test_csv_maps_row_index_and_predict_id(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'result.csv'), 'w', encoding='utf-8') as f:
                f.write('id,img_path,_viz_id\n42,C:/data/a.jpg,0\n')
            m = _load_csv_paths_by_image_id(td)
            self.assertEqual(m[0], 'C:/data/a.jpg')
            self.assertEqual(m[42], 'C:/data/a.jpg')


if __name__ == '__main__':
    unittest.main()
