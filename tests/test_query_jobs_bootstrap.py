"""后台查询任务：启动恢复与状态合并。"""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from studio.query import query_jobs


class QueryJobsBootstrapTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._jobs_dir = os.path.join(self._tmpdir.name, 'query_jobs')
        os.makedirs(self._jobs_dir, exist_ok=True)
        self._orig_jobs = dict(query_jobs._jobs)
        self._orig_boot = query_jobs._bootstrapped
        self._orig_app = query_jobs._app
        query_jobs._jobs.clear()
        query_jobs._bootstrapped = False
        query_jobs._app = None

    def tearDown(self):
        query_jobs._jobs.clear()
        query_jobs._jobs.update(self._orig_jobs)
        query_jobs._bootstrapped = self._orig_boot
        query_jobs._app = self._orig_app
        self._tmpdir.cleanup()

    def _write_job(self, job_id, **fields):
        job = {'id': job_id, 'status': 'pending', 'created_at': time.time(), **fields}
        path = os.path.join(self._jobs_dir, f'{job_id}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(job, f)
        return job

    def test_init_marks_interrupted_only_once(self):
        job_id = 'job-running-1'
        self._write_job(job_id, status='running', started_at=time.time())
        fake_app = object()

        with patch.object(query_jobs, 'JOBS_DIR', self._jobs_dir):
            query_jobs.init_query_jobs(fake_app)
            self.assertEqual(query_jobs._jobs[job_id]['status'], 'failed')
            self.assertIn('服务已重启', query_jobs._jobs[job_id]['error'])

            query_jobs._jobs[job_id]['status'] = 'running'
            query_jobs._jobs[job_id]['error'] = ''
            query_jobs.init_query_jobs(fake_app)
            self.assertEqual(query_jobs._jobs[job_id]['status'], 'running')

    def test_merge_prefers_newer_memory_state(self):
        job_id = 'job-merge-1'
        disk = {
            'id': job_id,
            'status': 'failed',
            'error': '服务已重启，任务已中断，请重新执行查询',
            'finished_at': 100.0,
        }
        mem = {
            'id': job_id,
            'status': 'done',
            'count': 42,
            'finished_at': 200.0,
        }
        query_jobs._jobs[job_id] = dict(mem)
        with patch.object(query_jobs, '_read_job_file', return_value=disk):
            got = query_jobs.get_query_job(job_id)
        self.assertEqual(got['status'], 'done')
        self.assertEqual(got['count'], 42)


if __name__ == '__main__':
    unittest.main()
