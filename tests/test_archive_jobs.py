"""归档后台任务。"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from studio.export import archive_jobs


class ArchiveJobsTests(unittest.TestCase):
    def test_calc_progress_images_phase(self):
        self.assertEqual(
            archive_jobs._calc_progress('images', 50, 100, include_images=True),
            57,
        )
        self.assertEqual(
            archive_jobs._calc_progress('done', 0, 0, include_images=False),
            100,
        )

    def test_validate_submit_rejects_missing_task(self):
        app = MagicMock()
        app.config = {'UPLOAD_FOLDER': tempfile.mkdtemp()}
        archive_jobs._app = app
        with self.assertRaises(ValueError) as ctx:
            archive_jobs._validate_submit(
                'no-such-task',
                {'archive_dir': app.config['UPLOAD_FOLDER'], 'subfolder': 'x'},
                app.config['UPLOAD_FOLDER'],
            )
        self.assertIn('任务不存在', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
