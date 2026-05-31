"""dataset_provenance 单元测试（不依赖真实 MySQL）。"""
import unittest
from unittest.mock import MagicMock, patch

from studio.sync import dataset_provenance as dp


class TestResolveItemProvenance(unittest.TestCase):
    def test_exact_object_key_match(self):
        key_map = {
            'foo/bar.jpg': {
                'id': 99,
                'product_no': 'SN12345678',
                'product_type': 'Model-A',
                'c_time': '2026-05-01 10:00:00',
                'position': 'front',
                'origin_object_key': 'foo/bar.jpg',
            },
        }
        prov = dp.resolve_item_provenance('foo/bar.jpg', key_map=key_map)
        self.assertEqual(prov['trace_status'], 'matched')
        self.assertEqual(prov['source_detail_id'], 99)

    def test_filename_map_match(self):
        fname_map = {
            'a.jpg': {
                'id': 7,
                'product_no': 'SN9',
                'origin_object_key': 'x/y/process/a.jpg',
                'product_type': 'T1',
                'c_time': '2026-05-02',
            },
        }
        prov = dp.resolve_item_provenance('', file_name='a.jpg', fname_map=fname_map)
        self.assertEqual(prov['trace_status'], 'filename')
        self.assertEqual(prov['product_no'], 'SN9')

    def test_sn_from_path_fallback(self):
        sn_map = {
            '98765432109876': [{
                'id': 42,
                'product_no': '98765432109876',
                'origin_object_key': 'x/98765432109876/process/a.jpg',
                'product_type': 'Type-X',
                'c_time': '2026-05-02 08:00:00',
            }],
        }
        prov = dp.resolve_item_provenance(
            'x/98765432109876/process/a.jpg',
            file_name='a.jpg',
            sn_map=sn_map,
        )
        self.assertEqual(prov['trace_status'], 'sn_only')

    def test_unmatched(self):
        prov = dp.resolve_item_provenance('random/file.jpg')
        self.assertEqual(prov['trace_status'], 'unmatched')

    def test_fuzzy_filename_match(self):
        fname_map = {
            'prefix_abc123def.jpg': {
                'id': 8,
                'product_no': 'SN8',
                'origin_object_key': 'x/y/prefix_abc123def.jpg',
                'product_type': 'T2',
                'c_time': '2026-05-02',
            },
        }
        prov = dp.resolve_item_provenance('', file_name='abc123def.jpg', fname_map=fname_map)
        self.assertEqual(prov['trace_status'], 'fuzzy')
        self.assertEqual(prov['product_no'], 'SN8')

    def test_fuzzy_score_substring(self):
        score = dp._filename_fuzzy_score('abc123def.jpg', 'longprefix_abc123def.jpg')
        self.assertGreaterEqual(score, dp.FUZZY_MIN_RATIO)


class TestBatchLookupProvenance(unittest.TestCase):
    @patch('server.core.get_db_client')
    def test_batch_lookup_fuzzy(self, mock_client_fn):
        client = MagicMock()
        mock_client_fn.return_value = client
        client.fetchall.side_effect = [
            [],  # object_key IN
            [],  # filename IN
            [],  # suffix LIKE
            [{  # fuzzy LIKE
                'id': 2,
                'product_no': 'SN2',
                'product_id': 'P2',
                'origin_object_key': 'deep/path/export_photo_v2.jpg',
                'product_type': 'M2',
                'c_time': '2026-05-01',
                'position': 'pos',
            }],
        ]
        out = dp.batch_lookup_provenance([
            {'object_key': 'local/photo_v2.jpg', 'file_name': 'photo_v2.jpg'},
        ])
        self.assertEqual(out[0]['trace_status'], 'fuzzy')
        self.assertEqual(out[0]['product_no'], 'SN2')

    @patch('server.core.get_db_client')
    def test_batch_lookup_by_filename(self, mock_client_fn):
        client = MagicMock()
        mock_client_fn.return_value = client
        client.fetchall.side_effect = [
            [],  # object_key IN
            [{  # filename IN
                'id': 1,
                'product_no': 'SN1',
                'product_id': 'P1',
                'origin_object_key': 'deep/path/photo.jpg',
                'product_type': 'M1',
                'c_time': '2026-05-01',
                'position': 'pos',
            }],
        ]
        out = dp.batch_lookup_provenance([{'object_key': 'other/key.jpg', 'file_name': 'photo.jpg'}])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['trace_status'], 'filename')
        self.assertEqual(out[0]['product_no'], 'SN1')


if __name__ == '__main__':
    unittest.main()
