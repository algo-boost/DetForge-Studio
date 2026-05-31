"""看图桥接单测。"""
import os
import unittest

from server.viz_mount import resolve_coco_visualizer_root, is_viz_available
from studio import viz_bridge


class VizBridgeTests(unittest.TestCase):
    def test_coco_root_sibling(self):
        root = resolve_coco_visualizer_root()
        if os.path.isdir(os.path.join(os.path.dirname(__file__), '..', '..', 'COCOVisualizer')):
            self.assertTrue(root.endswith('COCOVisualizer'))

    def test_session_roundtrip(self):
        payload = {'dataset_id': 'dataset_test', 'dataset_name': 't', 'categories': ['a']}
        meta = viz_bridge._store_session(payload, source='test')
        rec = viz_bridge.get_session(meta['session_id'])
        self.assertIsNotNone(rec)
        self.assertEqual(rec['dataset_id'], 'dataset_test')

    @unittest.skipUnless(is_viz_available(), 'COCOVisualizer 不可用')
    def test_open_from_task_missing(self):
        with self.assertRaises(FileNotFoundError):
            viz_bridge.open_from_task('nonexistent_task_id_xyz')
