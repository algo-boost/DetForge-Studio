"""GET /api/query/task/<task_id> 恢复查询结果。"""
import json
import os

import pandas as pd

from server.core import build_query_task, load_query_task_results


def test_load_query_task_results_roundtrip(app):
    with app.app_context():
        upload = app.config['UPLOAD_FOLDER']
        df = pd.DataFrame([
            {
                'img_path': '/tmp/fake.jpg',
                'c_time': '2026-01-01 10:00:00',
                'check_status': 'OK',
                'product_no': 'SN001',
            },
        ])
        meta = {'data_source': 'detail', 'strategy_name': '测试策略'}
        data, task_id = build_query_task(df, meta)
        assert len(data) == 1

        loaded = load_query_task_results(task_id, upload)
        assert loaded is not None
        assert loaded['task_id'] == task_id
        assert loaded['count'] == 1
        assert loaded['data'][0]['product_no'] == 'SN001'
        assert '测试策略' in loaded['summary']


def test_build_query_task_does_not_copy_images(app, tmp_path):
    with app.app_context():
        upload = app.config['UPLOAD_FOLDER']
        img = tmp_path / 'line.jpg'
        img.write_bytes(b'jpg')
        df = pd.DataFrame([{'img_path': str(img), 'check_status': 'OK'}])
        data, task_id = build_query_task(df, {'data_source': 'detail'})
        task_dir = os.path.join(upload, task_id)
        assert data[0]['img_path'] == str(img)
        assert not any(
            f.lower().endswith('.jpg') for f in os.listdir(task_dir)
            if f not in ('result.csv', 'query_meta.json') and not f.endswith('.json')
        )


def test_get_query_task_api(client, app):
    with app.app_context():
        upload = app.config['UPLOAD_FOLDER']
        df = pd.DataFrame([{'img_path': '/x/a.jpg', 'check_status': 'NG'}])
        _, task_id = build_query_task(df, {'data_source': 'detail'})
        assert os.path.isfile(os.path.join(upload, task_id, 'result.csv'))

    r = client.get(f'/api/query/task/{task_id}')
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['count'] == 1

    r404 = client.get('/api/query/task/not-a-real-task')
    assert r404.status_code == 404
