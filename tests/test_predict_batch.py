"""预测批次 SQL 与 pred COCO 布局单元测试。"""
import re
import unittest

from studio.export.pred_coco_layout import pred_coco_filename, sanitize_model_slug


def build_predict_job_sql(table, job_id):
    t = table or '`detforge`.`predict_result`'
    if job_id is not None and str(job_id).strip() != '':
        return f'SELECT * FROM {t}\nWHERE job_id = {int(job_id)}'
    return f'SELECT * FROM {t}'


class TestPredictJobSql(unittest.TestCase):
    def test_build_with_job_id_no_time_range(self):
        sql = build_predict_job_sql('`detforge`.`predict_result`', 38)
        self.assertIn('job_id = 38', sql)
        self.assertNotIn('BETWEEN', sql)
        self.assertNotIn('c_time', sql)

    def test_build_without_job_id(self):
        sql = build_predict_job_sql('`detforge`.`predict_result`', None)
        self.assertNotIn('WHERE', sql)

    def test_parse_job_id_from_sql(self):
        sql = 'SELECT * FROM predict_result WHERE job_id = 42'
        m = re.search(r'\bjob_id\s*=\s*(\d+)', sql, re.I)
        self.assertEqual(int(m.group(1)), 42)


class TestPredCocoLayout(unittest.TestCase):
    def test_sanitize_model_slug(self):
        self.assertEqual(sanitize_model_slug('V28/19+plus'), 'V28_19_plus')
        self.assertEqual(sanitize_model_slug(''), 'predict')

    def test_pred_coco_filename(self):
        name = pred_coco_filename('My Model v2')
        self.assertTrue(name.endswith('.pred.coco.json'))
        self.assertIn('_annotations.', name)


if __name__ == '__main__':
    unittest.main()
