"""env_field_types 单元测试。"""
import unittest

from studio.query.env_field_types import (
    normalize_env_field_row,
    normalize_field_type,
    normalize_options,
)


class EnvFieldTypesTests(unittest.TestCase):
    def test_normalize_field_type_aliases(self):
        self.assertEqual(normalize_field_type('multi_select'), 'multiselect')
        self.assertEqual(normalize_field_type('datetime'), 'datetime')

    def test_normalize_options(self):
        opts = normalize_options([{'value': 'a', 'label': '甲'}, 'b'])
        self.assertEqual(opts[0]['value'], 'a')
        self.assertEqual(opts[1]['label'], 'b')

    def test_normalize_row_multiselect(self):
        row = normalize_env_field_row({
            'key': 'tags',
            'type': 'multiselect',
            'options': [{'value': 'x', 'label': 'X'}],
        })
        self.assertEqual(row['type'], 'multiselect')
        self.assertEqual(len(row['options']), 1)


if __name__ == '__main__':
    unittest.main()
