"""缺陷类别加载：排除分类训练与成像标签。"""

import unittest

from studio.query.defect_categories import (
    DEFAULT_FALLBACK_CATEGORIES,
    _labels_for_defect_detection_source,
    _labels_match_defect_vocab,
    _sanitize_defect_labels,
    fetch_defect_categories,
    is_detection_deploy_model_type,
    is_detection_model_type,
)


class DefectCategoriesTests(unittest.TestCase):
    def test_deploy_model_type_strict(self):
        self.assertTrue(is_detection_deploy_model_type('DET_YOLO'))
        self.assertFalse(is_detection_deploy_model_type('BASIC_PRECISION'))
        self.assertTrue(is_detection_model_type('BASIC_PRECISION'))

    def test_sanitize_rejects_classification_labels(self):
        raw = ['正面', '反面', 'OK', 'NG']
        self.assertEqual(_sanitize_defect_labels(raw, DEFAULT_FALLBACK_CATEGORIES), [])

    def test_sanitize_keeps_known_defects(self):
        raw = ['脏污', '划伤', '未知新缺陷']
        out = _sanitize_defect_labels(raw, DEFAULT_FALLBACK_CATEGORIES)
        self.assertEqual(out, ['脏污', '划伤'])

    def test_assembly_deploy_labels_rejected(self):
        raw = ['NFC标识', '红标签', '漏焊', '防水卡子-ok']
        self.assertFalse(_labels_match_defect_vocab(raw, DEFAULT_FALLBACK_CATEGORIES))
        self.assertEqual(_labels_for_defect_detection_source(raw, DEFAULT_FALLBACK_CATEGORIES), [])

    def test_defect_deploy_labels_accepted(self):
        raw = ['脏污', '划伤', '压痕', '焊丝']
        out = _labels_for_defect_detection_source(raw, DEFAULT_FALLBACK_CATEGORIES)
        self.assertEqual(out, raw)

    def test_fetch_fallback_when_train_is_classification(self):
        class FakeClient:
            connection = object()

            def query(self, sql):
                return None

        bundle = fetch_defect_categories(FakeClient(), approach_id=18, fallback=['脏污', '划伤'])
        self.assertEqual(bundle['source'], 'fallback')
        self.assertIn('脏污', bundle['categories'])


if __name__ == '__main__':
    unittest.main()
