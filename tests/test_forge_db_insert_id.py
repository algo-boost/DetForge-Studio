"""forge_db INSERT 返回 id 单测。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class ForgeDbInsertIdTests(unittest.TestCase):
    def test_create_workflow_run_uses_execute_returning_id(self):
        from studio.forge import forge_db

        client = MagicMock()
        client.execute_returning_id.return_value = 42
        with patch.object(forge_db, '_client', return_value=client):
            run_id = forge_db.create_workflow_run({
                'template_id': 'custom_abc',
                'name': 'test',
                'params': {},
            })
        self.assertEqual(run_id, 42)
        client.execute_returning_id.assert_called_once()
        client.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
