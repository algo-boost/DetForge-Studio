import json
import unittest

import pandas as pd

from studio.query.pipeline_rules import (
    CONFIDENCE_MODE_MIN_THRESHOLD,
    build_rules_flow,
    dedupe_rules,
    parse_node_param,
    pipeline_threshold_to_rule,
)
from studio.query.python_builtins import strip_boxes_below_confidence
from studio.flow.flow_compiler import compile_filter_rules


AB_DEFECT_PARAM = {
    "config": {
        "basic_config": {
            "confidence": 0.2,
            "ng_tags": '["破损","划伤"]',
            "algo_config": [
                {"labels": '["凹坑","异物外漏"]', "confidence": 0.5, "position": "正面"},
                {"labels": '["划伤","压痕"]', "confidence": 0.7, "position": "正面"},
            ],
        }
    }
}


class PipelineRulesTest(unittest.TestCase):
    def test_pipeline_threshold_to_rule(self):
        rule = pipeline_threshold_to_rule(['脏污'], 0.3)
        self.assertEqual(rule['confidence_mode'], CONFIDENCE_MODE_MIN_THRESHOLD)
        self.assertAlmostEqual(rule['min_confidence'], 0.3)
        self.assertEqual(rule['confidence_range'], [0.3, 1.0])

    def test_parse_algo_config_groups(self):
        rules, warnings = parse_node_param('object_detection', json.dumps(AB_DEFECT_PARAM), 'A缺陷')
        self.assertEqual(len(rules), 3)
        self.assertEqual(rules[0]['categories'], ['凹坑', '异物外漏'])
        self.assertAlmostEqual(rules[0]['min_confidence'], 0.5)
        self.assertEqual(rules[0].get('positions'), ['正面'])
        self.assertEqual(rules[1]['categories'], ['划伤', '压痕'])
        self.assertAlmostEqual(rules[1]['min_confidence'], 0.7)
        self.assertEqual(rules[2]['categories'], ['破损'])
        self.assertAlmostEqual(rules[2]['min_confidence'], 0.2)
        for r in rules:
            self.assertEqual(r['confidence_mode'], CONFIDENCE_MODE_MIN_THRESHOLD)
        self.assertTrue(any('默认最低阈值' in w for w in warnings))

    def test_parse_ng_tags_fallback(self):
        param = {"config": {"basic_config": {"confidence": 0.4, "ng_tags": '["红标签"]', "algo_config": []}}}
        rules, _ = parse_node_param('object_detection', json.dumps(param), '错漏装')
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['categories'], ['红标签'])
        self.assertAlmostEqual(rules[0]['min_confidence'], 0.4)

    def test_build_rules_flow(self):
        rules = [{'categories': ['脏污'], 'confidence_range': [0, 1], 'random_drop_ratio': 1.0}]
        flow = build_rules_flow(rules)
        loop = flow['nodes'][0]
        self.assertEqual(loop['type'], 'control.loop')
        self.assertEqual(loop['params']['rules'], rules)

    def test_dedupe_rules(self):
        a = pipeline_threshold_to_rule(['A'], 0.5)
        merged = dedupe_rules([a, dict(a)])
        self.assertEqual(len(merged), 1)

    def test_strip_boxes_below_confidence(self):
        ext = json.dumps({
            'original_predictions': [
                {'name': '脏污', 'confidence': 0.25},
                {'name': '脏污', 'confidence': 0.35},
                {'name': '其他', 'confidence': 0.1},
            ]
        })
        df = pd.DataFrame({'ext': [ext]})
        out = strip_boxes_below_confidence(df, categories=['脏污'], min_confidence=0.3)
        preds = json.loads(out.iloc[0]['ext'])['original_predictions']
        names = [p['name'] for p in preds]
        self.assertEqual(names, ['脏污', '其他'])
        self.assertAlmostEqual(
            next(p['confidence'] for p in preds if p['name'] == '脏污'), 0.35
        )

    def test_compile_min_threshold_rule(self):
        rules = [pipeline_threshold_to_rule(['脏污'], 0.3)]
        flow = build_rules_flow(rules)
        result = compile_filter_rules(flow, {})
        self.assertTrue(result['valid'], result.get('errors'))
        self.assertIn('strip_boxes_below_confidence', result['python_code'])
        self.assertIn('0.3', result['python_code'])


if __name__ == '__main__':
    unittest.main()
