import os
import unittest
from unittest.mock import patch

from studio.forge import predict_runtime


class PredictRuntimeTests(unittest.TestCase):
    def test_default_detunify_sibling(self):
        root = predict_runtime.default_detunify_root()
        # 在 monorepo 中通常存在 sibling DetUnify-Studio
        if os.path.isdir(os.path.join(predict_runtime.PROJECT_ROOT, '..', 'DetUnify-Studio')):
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

    @patch('studio.forge.predict_runtime.subprocess.run')
    def test_run_batch_predict_parses_stdout(self, mock_run):
        from unittest.mock import Mock
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"success": true, "results": [{"path": "/a.jpg", "ok": true, "predictions": []}]}',
            stderr='',
        )
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
