"""路径解析（开发 / PyInstaller 发行包）。"""
import os
import sys
import unittest

from studio import paths


class TestPaths(unittest.TestCase):
    def test_app_root_is_directory(self):
        self.assertTrue(os.path.isdir(paths.APP_ROOT))

    def test_resource_path_strategies(self):
        p = paths.resource_path('strategies')
        self.assertTrue(os.path.isdir(p) or os.path.isfile(p))

    def test_resolve_config_path_relative(self):
        rel = paths.resolve_config_path('exports')
        self.assertTrue(os.path.isabs(rel))
        self.assertTrue(rel.endswith('exports'))

    def test_bundled_tool_dir_optional(self):
        # 开发树通常无 tools/，不应抛错
        p = paths.bundled_tool_dir('COCOVisualizer')
        self.assertTrue(p == '' or os.path.isdir(p))


if __name__ == '__main__':
    unittest.main()
