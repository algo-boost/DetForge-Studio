"""后台查询任务 API。"""
import json


def test_create_query_job_validation(client, json_headers):
    r = client.post('/api/query/jobs', data=json.dumps({'sql': ''}), headers=json_headers)
    assert r.status_code == 400


def test_list_query_jobs(client):
    r = client.get('/api/query/jobs')
    assert r.status_code == 200
    assert r.get_json().get('success') is True
    assert 'jobs' in r.get_json()
