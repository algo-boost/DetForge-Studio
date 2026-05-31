"""config.json 敏感字段加密测试。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import config_crypto as cc


class TestConfigCrypto(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.key_path = self.base / '.config.key'

    def tearDown(self):
        self._tmpdir.cleanup()

    @unittest.skipUnless(cc.encryption_available(), 'cryptography not installed')
    def test_roundtrip_encrypt_decrypt(self):
        with patch.object(cc, 'key_file_path', return_value=self.key_path):
            plain = {'db_password': 'secret123', 'magic_fox_access_token': 'tok-abc'}
            enc = cc.encrypt_config_secrets(plain)
            self.assertTrue(cc.is_encrypted(enc['db_password']))
            self.assertTrue(cc.is_encrypted(enc['magic_fox_access_token']))
            dec = cc.decrypt_config_secrets(enc)
            self.assertEqual(dec['db_password'], 'secret123')
            self.assertEqual(dec['magic_fox_access_token'], 'tok-abc')

    @unittest.skipUnless(cc.encryption_available(), 'cryptography not installed')
    def test_load_save_integration(self):
        cfg_file = self.base / 'config.json'
        with patch.object(cc, 'key_file_path', return_value=self.key_path):
            from server.core import save_config, load_config, CONFIG_FILE
            with patch('server.core.CONFIG_FILE', str(cfg_file)):
                ok = save_config({'db_password': 'pw1', 'db_host': 'localhost'})
                self.assertTrue(ok)
                raw = json.loads(cfg_file.read_text(encoding='utf-8'))
                self.assertTrue(cc.is_encrypted(raw['db_password']))
                loaded = load_config()
                self.assertEqual(loaded['db_password'], 'pw1')

    def test_plaintext_backward_compatible(self):
        cfg = {'db_password': 'legacy-plain'}
        dec = cc.decrypt_config_secrets(cfg)
        self.assertEqual(dec['db_password'], 'legacy-plain')


if __name__ == '__main__':
    unittest.main()
