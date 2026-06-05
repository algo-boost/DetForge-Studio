"""disposition 解析与 handoff 构建单测。"""
import json
import os
import tempfile
import unittest

from studio.curation import dispositions
from studio.curation.handoff_pack import build_coco_from_manual_qc_records, assemble_handoff_dir
from studio.curation import curation_service


class DispositionParseTests(unittest.TestCase):
    def test_coco_image_disposition(self):
        coco = {
            'images': [
                {'file_name': 'a.jpg', 'extra': {'disposition': 'need_label'}},
                {'file_name': 'b.jpg', 'attributes': {'need_platform_label': True}},
            ],
        }
        m = curation_service.coco_image_disposition_map(coco)
        self.assertEqual(m['a.jpg'][0], 'need_label')
        self.assertTrue(m['a.jpg'][1])
        self.assertEqual(m['b.jpg'][0], 'need_label')

    def test_qc_category_mapping(self):
        rec = {'qc_category': '拍不到', 'match_status': 'not_found'}
        self.assertEqual(dispositions.disposition_from_qc_record(rec), 'qc_no_shot')
        self.assertEqual(
            dispositions.disposition_from_qc_record({'qc_category': '未拍到', 'matched_detail_id': 1}),
            'qc_no_shot',
        )
        self.assertEqual(
            dispositions.disposition_from_qc_record({'qc_category': '检出', 'matched_detail_id': 1}),
            'tp_detected',
        )
        self.assertEqual(
            dispositions.disposition_from_qc_record({'qc_category': '漏检', 'matched_detail_id': 1}),
            'fn_missed',
        )

    def test_infer_intent_replay(self):
        self.assertEqual(
            curation_service.infer_intent_type('replay_eval_v2', 'detail'),
            'replay_eval',
        )


class ManualQcCocoTests(unittest.TestCase):
    def test_build_coco_from_records(self):
        rows = [{
            'id': 1,
            'product_no': 'SN1',
            'matched_img_path': '/tmp/x.jpg',
            'qc_category': '成像不清',
            'defect_info': {
                'ext': {
                    'original_predictions': [
                        {'name': '脏污', 'points': [{'x': 1, 'y': 2, 'w': 3, 'h': 4}]},
                    ],
                },
            },
        }]
        coco = build_coco_from_manual_qc_records(rows)
        self.assertEqual(len(coco['images']), 1)
        self.assertEqual(coco['images'][0]['file_name'], 'x.jpg')
        self.assertEqual(len(coco['annotations']), 1)

    def test_assemble_handoff_dir(self):
        td = tempfile.mkdtemp()
        coco = {'info': {}, 'images': [{'id': 0, 'file_name': 'x.jpg'}], 'annotations': [], 'categories': []}
        r = assemble_handoff_dir(
            td,
            intent_type='customer_qc',
            coco_data=coco,
            image_copy_fn=lambda d: 0,
            manifest_rows=[{'file_name': 'x.jpg', 'disposition': 'qc_blur', 'source': 'manual_qc'}],
        )
        self.assertTrue(os.path.isfile(os.path.join(r['out_dir'], '_annotations.coco.json')))
        self.assertTrue(os.path.isfile(os.path.join(r['out_dir'], 'HANDOFF.md')))


if __name__ == '__main__':
    unittest.main()
