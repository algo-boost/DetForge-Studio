"""flow_compiler 单元测试（无需数据库）。"""
import json
import os
import unittest

from studio.flow.flow_compiler import (
    FILTER_RULES_FUNC,
    PROCESS_FUNC,
    combine_python_code,
    compile_filter_rules,
    compile_process_data,
    extract_rules_compile_flow,
    has_inline_sampling,
    has_filter_rules_definition,
    references_filter_rules,
    normalize_strategy,
    resolve_strategy_python,
)


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_TRAWL = os.path.join(HERE, 'strategies', '_builtin', 'daily_trawl.json')
TEMPLATES_DIR = os.path.join(HERE, 'strategies', 'templates', '_builtin')


def _load_templates():
    templates = {}
    if not os.path.isdir(TEMPLATES_DIR):
        return templates
    for fname in os.listdir(TEMPLATES_DIR):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(TEMPLATES_DIR, fname), encoding='utf-8') as f:
            data = json.load(f)
            if data.get('id'):
                templates[data['id']] = data
    return templates


class FlowCompilerTests(unittest.TestCase):
    def test_combine_python_code(self):
        rules = f'def {FILTER_RULES_FUNC}(df):\n    return df\n'
        proc = f'def {PROCESS_FUNC}(df):\n    return df\n'
        merged = combine_python_code(rules, proc)
        self.assertIn(FILTER_RULES_FUNC, merged)
        self.assertIn(PROCESS_FUNC, merged)

    def test_compile_filter_rules_from_daily_trawl(self):
        with open(DAILY_TRAWL, encoding='utf-8') as f:
            strategy = json.load(f)
        flow = extract_rules_compile_flow(strategy['flow'])
        result = compile_filter_rules(flow, {})
        self.assertTrue(result['valid'], result.get('errors'))
        self.assertIn(f'def {FILTER_RULES_FUNC}', result['python_code'])
        self.assertIn('脏污', result['python_code'])
        compile(result['python_code'], '<rules>', 'exec')

    def test_compile_filter_rules_if_else_indent(self):
        """规则循环内 if/else 须正确缩进，避免 exec SyntaxError。"""
        flow = {
            'version': 2,
            'nodes': [{
                'id': 'loop1', 'type': 'control.loop',
                'params': {
                    'loop_mode': 'rules',
                    'rules': [{'categories': ['脏污'], 'confidence_range': [0, 1], 'random_drop_ratio': 1.0}],
                },
                'body': [
                    {'id': 'f1', 'type': 'builtin.filter_df_by_ext', 'params': {'bind_loop_rule': 'loop_rule'}},
                ],
            }],
        }
        result = compile_filter_rules(flow, {})
        self.assertTrue(result['valid'], result.get('errors'))
        compile(result['python_code'], '<rules>', 'exec')
        self.assertIn('else:', result['python_code'])
        self.assertIn('    else:', result['python_code'])

    def test_compile_process_data_delegates_rules(self):
        templates = _load_templates()
        with open(DAILY_TRAWL, encoding='utf-8') as f:
            strategy = json.load(f)
        result = compile_process_data(strategy['flow'], templates)
        self.assertTrue(result['valid'], result.get('errors'))
        code = result['python_code']
        self.assertIn(f'df = {FILTER_RULES_FUNC}(df)', code)
        self.assertNotIn('for _loop_rule in _rules', code)
        self.assertIn('apply_random_sample_rows', code)
        self.assertIn('apply_random_sample_rows(df)', code)
        self.assertNotIn('_tpl_random_sample', code)
        self.assertNotIn('max_rows=300', code)
        self.assertNotIn('if len(df) >', code)

    def test_normalize_strategy_splits_legacy(self):
        templates = _load_templates()
        with open(DAILY_TRAWL, encoding='utf-8') as f:
            base = json.load(f)
        legacy = dict(base)
        legacy['python_code'] = 'def process_data(df):\n    for _loop_rule in _rules:\n        pass\n    return df\n'
        legacy.pop('filter_rules_code', None)
        normalized = normalize_strategy(legacy, templates)
        self.assertIn('filter_rules_code', normalized)
        self.assertIn(f'def {FILTER_RULES_FUNC}', normalized['filter_rules_code'])
        self.assertIn(f'def {PROCESS_FUNC}', normalized['python_code'])
        self.assertNotIn('for _loop_rule in _rules', normalized['python_code'])
        self.assertEqual(normalized.get('filter_mode'), 'split')

    def test_normalize_template_flow_to_code(self):
        templates = _load_templates()
        with open(os.path.join(HERE, 'strategies', '_builtin', 'high_conf_defects.json'), encoding='utf-8') as f:
            strategy = json.load(f)
        normalized = normalize_strategy(strategy, templates)
        self.assertEqual(normalized.get('filter_mode'), 'code')
        self.assertIn(f'def {PROCESS_FUNC}', normalized.get('python_code', ''))
        self.assertIn('apply_random_sample_rows(df)', normalized.get('python_code', ''))
        self.assertNotIn('_tpl_random_sample', normalized.get('python_code', ''))
        self.assertIn('def apply_random_sample_rows', normalized.get('sample_code', ''))
        self.assertNotIn('filter_rules_code', normalized)

    def test_has_inline_sampling_daily_trawl(self):
        with open(DAILY_TRAWL, encoding='utf-8') as f:
            strategy = json.load(f)
        templates = _load_templates()
        code, _ = resolve_strategy_python(strategy, templates)
        from studio.flow.flow_compiler import has_inline_sampling
        self.assertTrue(has_inline_sampling(code, strategy.get('flow')))

    def test_has_inline_sampling_plain_rules(self):
        rules = f'def {FILTER_RULES_FUNC}(df):\n    return df\n'
        proc = f'def {PROCESS_FUNC}(df):\n    return df\n'
        code = combine_python_code(rules, proc)
        self.assertFalse(has_inline_sampling(code))

    def test_references_filter_rules_without_def(self):
        proc = f'def {PROCESS_FUNC}(df):\n    return {FILTER_RULES_FUNC}(df)\n'
        self.assertTrue(references_filter_rules(proc))
        self.assertFalse(has_filter_rules_definition(proc))

    def test_combine_when_process_calls_rules(self):
        rules = f'def {FILTER_RULES_FUNC}(df):\n    return df.head(1)\n'
        proc = f'def {PROCESS_FUNC}(df):\n    return {FILTER_RULES_FUNC}(df)\n'
        merged = combine_python_code(rules, proc)
        self.assertIn(f'def {FILTER_RULES_FUNC}', merged)
        self.assertIn(f'def {PROCESS_FUNC}', merged)

if __name__ == '__main__':
    unittest.main()
