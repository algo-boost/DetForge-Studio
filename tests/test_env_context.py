"""env_context 单元测试。"""
import unittest

from server.core import sample_size_from_env
from studio.query.env_context import (
    build_stage_context,
    extract_template_vars,
    find_unresolved_template_vars,
    normalize_env_dict,
    resolve_strategy_env_schema,
    substitute_template,
)


class EnvContextTests(unittest.TestCase):
    def test_substitute_template(self):
        sql = "WHERE c_time BETWEEN '${START_TIME}' AND '${END_TIME}' AND score >= ${MIN_SCORE}"
        out = substitute_template(sql, {
            'START_TIME': '2026-01-01',
            'END_TIME': '2026-01-02',
            'MIN_SCORE': '0.25',
        })
        self.assertIn('2026-01-01', out)
        self.assertIn('0.25', out)
        self.assertNotIn('${START_TIME}', out)

    def test_extract_template_vars(self):
        vars_found = extract_template_vars(
            "SELECT * FROM t WHERE job_id=${JOB_ID} AND type='${PRODUCT_TYPE}'",
            "x = get_env('MIN_SCORE')",
        )
        self.assertEqual(vars_found, ['JOB_ID', 'MIN_SCORE', 'PRODUCT_TYPE'])

    def test_normalize_env_dict(self):
        out = normalize_env_dict({'min_score': 0.1, 'PRODUCT_TYPE': ' PanelA '})
        self.assertEqual(out['MIN_SCORE'], '0.1')
        self.assertEqual(out['PRODUCT_TYPE'], 'PanelA')

    def test_sample_size_from_env_optional(self):
        self.assertIsNone(sample_size_from_env({'NUM': '10000'}))
        self.assertEqual(sample_size_from_env({'SAMPLE_SIZE': '500'}), 500)
        self.assertIsNone(sample_size_from_env({'SAMPLE_SIZE': ''}))

    def test_build_stage_context_env_sample(self):
        ctx = build_stage_context(
            {'env': {'SAMPLE_SIZE': '500', 'RANDOM_SEED': '7', 'NUM': '1000'}},
            start_time='2026-05-01 00:00:00',
            end_time='2026-05-01 23:59:59',
        )
        self.assertEqual(ctx['SAMPLE_SIZE'], '500')
        self.assertEqual(ctx['RANDOM_SEED'], '7')
        self.assertEqual(ctx['NUM'], '1000')
        self.assertEqual(ctx['START_TIME'], '2026-05-01 00:00:00')
        self.assertEqual(ctx['END_TIME'], '2026-05-01 23:59:59')

    def test_build_stage_context_legacy_sample_top_level(self):
        ctx = build_stage_context(
            {'sample_size': 150, 'random_seed': 99, 'env': {}},
            start_time='2026-05-01 00:00:00',
            end_time='2026-05-01 23:59:59',
        )
        self.assertEqual(ctx['SAMPLE_SIZE'], '150')
        self.assertEqual(ctx['RANDOM_SEED'], '99')
        ctx = build_stage_context(
            {
                'env': {'PRODUCT_LINE': 'A'},
                'stage2_env': {'MIN_SCORE': '0.3'},
                'predict': {'threshold': 0.1, 'model_id': 5},
            },
            stage='stage2',
            job_id=99,
            start_time='2026-05-01 00:00:00',
            end_time='2026-05-01 23:59:59',
        )
        self.assertEqual(ctx['JOB_ID'], '99')
        self.assertEqual(ctx['MIN_SCORE'], '0.3')
        self.assertEqual(ctx['PRODUCT_LINE'], 'A')
        self.assertEqual(ctx['THRESHOLD'], '0.1')
        self.assertEqual(ctx['STAGE'], 'stage2')

    def test_substitute_num_in_quotes(self):
        sql = "WITH consts AS (SELECT '${NUM}' AS K)"
        out = substitute_template(sql, {'NUM': '1000'})
        self.assertIn("'1000'", out)
        self.assertNotIn('${NUM}', out)

    def test_find_unresolved_after_substitute(self):
        sql = substitute_template("SELECT ${NUM} FROM t WHERE t BETWEEN '${START_TIME}' AND '${END_TIME}'", {
            'START_TIME': '2026-05-01',
            'END_TIME': '2026-05-30',
        })
        self.assertEqual(find_unresolved_template_vars(sql), ['NUM'])
        schema = resolve_strategy_env_schema({
            'id': 'demo',
            'sql_template': 'SELECT * FROM t WHERE type=${PRODUCT_TYPE}',
            'python_code': "min_score = get_env('MIN_SCORE')",
        })
        keys = {row['key'] for row in schema}
        self.assertIn('PRODUCT_TYPE', keys)
        self.assertIn('MIN_SCORE', keys)


if __name__ == '__main__':
    unittest.main()
