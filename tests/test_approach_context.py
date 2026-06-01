import unittest

from studio.query.approach_context import resolve_local_approach_id, resolve_magic_fox_approach_id


class ApproachContextTests(unittest.TestCase):
    def test_local_from_config(self):
        self.assertEqual(resolve_local_approach_id({'defect_approach_id': 18}), 18)
        self.assertEqual(resolve_local_approach_id({'defect_approach_id': 18}, override=99), 99)

    def test_local_default(self):
        self.assertEqual(resolve_local_approach_id({}), 18)

    def test_magic_fox_from_project(self):
        self.assertEqual(resolve_magic_fox_approach_id({'approach_id': 598}), 598)
        self.assertIsNone(resolve_magic_fox_approach_id({}))
        self.assertIsNone(resolve_magic_fox_approach_id(None))

    def test_magic_fox_override(self):
        self.assertEqual(resolve_magic_fox_approach_id(None, override=598), 598)


if __name__ == '__main__':
    unittest.main()
