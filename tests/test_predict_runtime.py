import os
import unittest
from unittest.mock import patch

from studio.forge import predict_runtime


class PredictRuntimeTests(unittest.TestCase):
    def test_default_detunify_sibling(self):
        from studio.paths import APP_ROOT
        root = predict_runtime.default_detunify_root()
        if os.path.isdir(os.path.join(APP_ROOT, '..', 'DetUnify-Studio')):
            self.assertTrue(root.endswith('DetUnify-Studio'))

    def test_resolve_without_script_uses_inprocess(self):
        s = predict_runtime.resolve_predict_settings({
            'detunify_studio_root': '/tmp/detunify',
            'predict_python_executable': '',
        })
        self.assertFalse(s['use_subprocess'])

    def test_resolve_auto_subprocess_when_worker_script_exists(self):
        root = predict_runtime.default_detunify_root()
        if not root:
            self.skipTest('no detunify root')
        script = os.path.join(root, 'scripts', 'predict_job_worker.py')
        if not os.path.isfile(script):
            self.skipTest('predict_job_worker missing')
        s = predict_runtime.resolve_predict_settings({
            'detunify_studio_root': root,
            'predict_python_executable': '',
        })
        self.assertTrue(s['use_subprocess'])
        self.assertTrue(s.get('predict_subprocess_auto'))

    def test_resolve_subprocess_when_configured(self):
        root = predict_runtime.default_detunify_root()
        if not root:
            self.skipTest('no detunify root')
        script = os.path.join(root, 'scripts', 'predict_job_worker.py')
        if not os.path.isfile(script):
            self.skipTest('predict_job_worker missing')
        s = predict_runtime.resolve_predict_settings({
            'detunify_studio_root': root,
            'predict_python_executable': __import__('sys').executable,
            'predict_script': script,
        })
        self.assertTrue(s['use_subprocess'])

    def test_parse_subprocess_stdout_with_leading_noise(self):
        payload = '{"success": true, "results": [{"path": "/a.jpg", "ok": true}]}'
        noisy = f'670 670\n{payload}'
        data = predict_runtime.parse_subprocess_stdout(noisy)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 1)

    def test_parse_subprocess_stdout_strict_json(self):
        data = predict_runtime.parse_subprocess_stdout('{"success": true, "results": []}')
        self.assertTrue(data['success'])

    @patch('studio.forge.predict_runtime.subprocess.Popen')
    def test_run_batch_predict_parses_stdout(self, mock_popen):
        from unittest.mock import Mock
        proc = Mock()
        proc.stdout = iter([])
        proc.stderr = iter([])
        proc.wait.return_value = 0
        mock_popen.return_value = proc
        with patch.object(predict_runtime, 'parse_subprocess_stdout') as parse:
            parse.return_value = {'success': True, 'results': [{'path': '/a.jpg', 'ok': True, 'predictions': []}]}
            cfg = {
                'detunify_studio_root': '/x',
                'predict_python_executable': '/usr/bin/python',
                'predict_script': __file__,
            }
            with patch.object(predict_runtime, 'resolve_predict_settings') as rs:
                rs.return_value = {
                    'use_subprocess': True,
                    'predict_python_executable': '/usr/bin/python',
                    'predict_script': __file__,
                    'detunify_studio_root': '/x',
                }
                out = predict_runtime.run_batch_predict({'images': []}, config=cfg)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]['ok'])
