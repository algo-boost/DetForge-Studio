"""row_fields 单元测试。"""
import unittest

import pandas as pd

from studio.query.row_fields import enrich_df_product_fields, normalize_result_row_fields, sn_from_path


class RowFieldsTests(unittest.TestCase):
    def test_normalize_product_fields(self):
        row = pd.Series({
            'product_no': 'SN12345678',
            'product_id': 'PID-001',
            'product_type': 'Model-A',
            'position': '门板',
        })
        norm = normalize_result_row_fields(row)
        self.assertEqual(norm['product_no'], 'SN12345678')
        self.assertEqual(norm['product_id'], 'PID-001')
        self.assertEqual(norm['product_type'], 'Model-A')

    def test_product_type_fallback_result_product_type(self):
        row = pd.Series({
            'product_no': 'SN999',
            'result_product_type': 'Model-B',
        })
        norm = normalize_result_row_fields(row)
        self.assertEqual(norm['product_type'], 'Model-B')

    def test_sn_not_filled_from_product_id(self):
        row = pd.Series({'product_id': '12345678901'})
        norm = normalize_result_row_fields(row)
        self.assertEqual(norm['product_no'], '')
        self.assertEqual(norm['product_id'], '12345678901')

    def test_sn_from_path(self):
        path = '/data/20260501/12345678901234/process/img.jpg'
        self.assertEqual(sn_from_path(path), '12345678901234')

    def test_sn_alias_columns(self):
        row = pd.Series({'code': 'CODE-SN-1', 'product_id': 'X1'})
        norm = normalize_result_row_fields(row)
        self.assertEqual(norm['product_no'], 'CODE-SN-1')

    def test_enrich_df_fills_missing(self):
        df = pd.DataFrame([{
            'product_id': 'P1',
            'result_product_type': 'Type-X',
            'origin_object_key': '/x/98765432109876/process/a.jpg',
        }])
        out = enrich_df_product_fields(df)
        self.assertEqual(str(out.at[0, 'product_no']), '98765432109876')
        self.assertEqual(str(out.at[0, 'product_type']), 'Type-X')


if __name__ == '__main__':
    unittest.main()
