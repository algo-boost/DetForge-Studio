"""strategy_executor 单元测试。"""
import unittest

from studio.query.strategy_executor import ensure_predict_job_scope, substitute_sql_vars


class SubstituteSqlVarsTests(unittest.TestCase):
    def test_time_vars(self):
        sql = "WHERE c_time BETWEEN '${START_TIME}' AND '${END_TIME}'"
        out = substitute_sql_vars(sql, {'START_TIME': '2026-01-01', 'END_TIME': '2026-01-02'})
        self.assertIn('2026-01-01', out)
        self.assertNotIn('${START_TIME}', out)

    def test_job_id(self):
        sql = 'WHERE job_id = ${JOB_ID}'
        out = substitute_sql_vars(sql, {'JOB_ID': '42'})
        self.assertIn('42', out)


class EnsurePredictJobScopeTests(unittest.TestCase):
    def test_no_change_when_job_in_sql(self):
        sql = 'SELECT * FROM predict_result WHERE job_id = ${JOB_ID}'
        self.assertEqual(sql, ensure_predict_job_scope(sql, 9))

    def test_append_where(self):
        sql = 'SELECT * FROM `detforge`.`predict_result`'
        out = ensure_predict_job_scope(sql, 12)
        self.assertIn('job_id = 12', out.lower())

    def test_non_predict_table(self):
        sql = 'SELECT * FROM product_detection_detail_result'
        self.assertEqual(sql, ensure_predict_job_scope(sql, 12))


if __name__ == '__main__':
    unittest.main()
