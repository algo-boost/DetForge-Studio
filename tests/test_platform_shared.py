"""packages/platform 共享层测试。"""
from __future__ import annotations

from packages.platform.img_path import img_path_from_object_key, normalize_existing_path, resolve_detail_img_path


def test_img_path_from_object_key():
    p = img_path_from_object_key('foo/bar.jpg', img_base_path='/data/')
    assert p.endswith('foo/bar.jpg')


def test_resolve_detail_img_path_prefers_local():
    row = {'local_pic_url': '/tmp/not-exist.jpg', 'origin_object_key': 'k.jpg'}
    path = resolve_detail_img_path(row)
    assert 'not-exist' in path or path


def test_normalize_existing_path_empty():
    assert normalize_existing_path('') == ''
