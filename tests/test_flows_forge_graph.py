"""组合编排 / forge workflow 流程图解析。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from studio.forge.compose_definition import build_linear_compose_definition


class ForgeWorkflowGraphTests(unittest.TestCase):
    def test_get_flow_graph_custom_template(self):
        from server.services import flows as fs

        definition = build_linear_compose_definition({
            'query': {'strategy_id': 'daily_trawl', 'time_window': {'preset': 'yesterday'}},
            'predict': {'model_id': 1, 'threshold': 0.1},
        })
        fake = {'id': 'custom_test123', 'definition': definition}

        with patch.object(fs, '_get_forge_workflow_template', return_value=fake):
            graph = fs.get_flow_graph('custom_test123')

        self.assertEqual(graph['flow_id'], 'custom_test123')
        self.assertEqual(len(graph['nodes']), 2)
        kinds = {n['id']: n.get('tool_id') or n.get('kind') for n in graph['nodes']}
        self.assertEqual(kinds['query'], 'query')
        self.assertEqual(kinds['predict'], 'predict')

    def test_workflow_run_graph_merges_step_status(self):
        from server.services.flows import _workflow_run_graph

        definition = build_linear_compose_definition({
            'query': {'strategy_id': 's1'},
            'predict': {'model_id': 2},
        })
        template = {'definition': definition}
        steps = [
            {'step_id': 'query', 'status': 'done', 'output': {'task_id': 't1', 'row_count': 5}},
            {'step_id': 'predict', 'status': 'running'},
        ]
        graph = _workflow_run_graph(template, 'custom_abc', steps)
        self.assertIsNotNone(graph)
        by_id = {n['id']: n for n in graph['nodes']}
        self.assertEqual(by_id['query']['status'], 'done')
        self.assertEqual(by_id['predict']['status'], 'running')


if __name__ == '__main__':
    unittest.main()
