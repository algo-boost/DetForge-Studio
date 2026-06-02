"""task 目录图片路径解析。"""
import os
import tempfile
import unittest

from studio.export.task_images import normalize_coco_images_for_task, resolve_task_image_path


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

    def test_normalize_updates_coco_file_name(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, '1_a.png')
            with open(src, 'wb') as f:
                f.write(b'x')
            coco = {
                'images': [{'id': 1, 'file_name': 'D:/remote/a.png'}],
                'annotations': [],
                'categories': [],
            }
            files = normalize_coco_images_for_task(td, coco, None)
            self.assertEqual(len(files), 1)
            self.assertEqual(coco['images'][0]['file_name'], '1_a.png')


if __name__ == '__main__':
    unittest.main()
