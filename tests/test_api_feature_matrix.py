"""全功能 API 特性矩阵（Flask test_client，不依赖 5050 live server）。"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock

import pandas as pd
import pytest

# ── 路由注册：确保主要蓝图均已挂载 ─────────────────────────────────────

EXPECTED_ROUTES = {
    '/api/config',
    '/api/docs/user-guide',
    '/api/query',
    '/api/preview-filter',
    '/api/image/<path:filename>',
    '/api/export/<task_id>',
    '/api/export-csv/<task_id>',
    '/api/archive/<task_id>',
    '/api/coco/<task_id>',
    '/api/templates',
    '/api/strategies',
    '/api/strategies/execute',
    '/api/env-profiles',
    '/api/env-profiles/suggest',
    '/api/defect-categories',
    '/api/platform-paths',
    '/api/platform-paths/sync',
    '/api/pipelines',
    '/api/deployed-models',
    '/api/training-models',
    '/api/flow/nodes',
    '/api/flow/compile',
    '/api/flow/schema',
    '/api/run-python-code',
    '/api/forge/schema/status',
    '/api/forge/schema/init',
    '/api/forge/models',
    '/api/forge/jobs',
    '/api/forge/jobs/predict',
    '/api/forge/jobs/predict/batch',
    '/api/forge/predict-result/source',
    '/api/forge/manual-qc',
    '/api/forge/manual-qc/categories',
    '/api/forge/manual-qc/lookup',
    '/api/forge/sync/projects',
    '/api/forge/sync/datasets',
    '/api/forge/sync/train-models',
    '/api/viz/status',
    '/api/viz/open',
    '/api/unify/status',
}


def test_all_expected_routes_registered(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    missing = EXPECTED_ROUTES - rules
    assert not missing, f'缺少路由: {sorted(missing)}'


# ── SPA 前端路由（History API fallback）──────────────────────────────────

FRONTEND_SPA_PATHS = [
    '/',
    '/config',
    '/history',
    '/models',
    '/jobs',
    '/training',
    '/manual-qc',
    '/viewer',
    '/online-predict',
]


@pytest.mark.parametrize('path', FRONTEND_SPA_PATHS)
def test_spa_fallback_returns_html(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data.lower()


@pytest.mark.parametrize('path', ['/admin', '/sync', '/docs', '/compare'])
def test_spa_legacy_paths_serve_spa(client, path):
    """旧路径由 React Router 客户端重定向；服务端仍返回 SPA shell。"""
    resp = client.get(path)
    assert resp.status_code == 200
    assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data.lower()


# ── 配置与文档 ───────────────────────────────────────────────────────────

class TestConfigAndDocs:
    def test_get_config_success_shape(self, client):
        resp = client.get('/api/config')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'config' in body
        assert 'path_checks' in body
        cfg = body['config']
        assert 'db_password' not in cfg or cfg.get('db_password') == ''
        assert cfg.get('api_token') == ''

    def test_user_guide_markdown(self, client):
        resp = client.get('/api/docs/user-guide')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        assert 'content' in body
        assert len(body['content']) > 100

    def test_post_config_missing_required_fields(self, client, json_headers):
        resp = client.post(
            '/api/config',
            data=json.dumps({'config': {'db_host': '', 'db_user': '', 'db_database': ''}}),
            headers=json_headers,
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_test_connection_without_body(self, client, json_headers):
        resp = client.post('/api/config/test-connection', headers=json_headers)
        assert resp.status_code in (400, 500)
        body = resp.get_json()
        assert body.get('success') is False or 'error' in body


# ── 数据查询 ─────────────────────────────────────────────────────────────

class TestQueryApi:
    def test_query_empty_sql_returns_400(self, client, json_headers):
        resp = client.post('/api/query', data=json.dumps({'sql': ''}), headers=json_headers)
        assert resp.status_code == 400
        assert '不能为空' in resp.get_json().get('error', '')

    def test_query_with_mock_db_empty_result(self, client, json_headers, monkeypatch):
        class MockClient:
            def query(self, sql):
                return pd.DataFrame([])

            def ensure_alive(self):
                return True

        monkeypatch.setattr('server.routes.api.get_db_client', lambda: MockClient())
        resp = client.post(
            '/api/query',
            data=json.dumps({'sql': 'SELECT 1', 'start_time': '', 'end_time': ''}),
            headers=json_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['count'] == 0

    def test_query_with_mock_db_and_python_filter(self, client, json_headers, monkeypatch):
        class MockClient:
            def query(self, sql):
                return pd.DataFrame([{'check_status': '1', 'score': 0.9}])

            def ensure_alive(self):
                return True

        monkeypatch.setattr('server.routes.api.get_db_client', lambda: MockClient())
        resp = client.post(
            '/api/query',
            data=json.dumps({
                'sql': 'SELECT 1',
                'python_code': 'def process_data(df):\n    return df',
            }),
            headers=json_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()['count'] >= 1

    def test_preview_filter_requires_data(self, client, json_headers):
        resp = client.post('/api/preview-filter', data=json.dumps({}), headers=json_headers)
        assert resp.status_code in (400, 500)
        body = resp.get_json()
        assert body.get('success') is False or 'error' in body


# ── 策略 / 模板 / Flow ───────────────────────────────────────────────────

class TestStrategiesAndFlow:
    def test_list_strategies(self, client):
        resp = client.get('/api/strategies')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert isinstance(body.get('data') or body.get('strategies'), list)

    def test_list_templates(self, client):
        resp = client.get('/api/templates')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_flow_schema(self, client):
        resp = client.get('/api/flow/schema')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body.get('flow_version')

    def test_flow_nodes(self, client):
        resp = client.get('/api/flow/nodes')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert isinstance(body.get('data') or body.get('nodes'), list)

    def test_flow_compile_empty_flow(self, client, json_headers):
        resp = client.post(
            '/api/flow/compile',
            data=json.dumps({'flow': {'nodes': [], 'edges': []}}),
            headers=json_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'python_code' in body

    def test_flow_compile_sample_function(self, client, json_headers):
        resp = client.post(
            '/api/flow/compile',
            data=json.dumps({
                'target': 'sample_function',
                'flow': {'nodes': [{'type': 'template.random_sample', 'params': {'max_rows': 50, 'random_seed': 7}}], 'edges': []},
            }),
            headers=json_headers,
        )
        assert resp.status_code == 200
        assert 'apply_random_sample' in resp.get_json().get('python_code', '')

    def test_delete_nonexistent_strategy(self, client):
        resp = client.delete('/api/strategies/__nonexistent_test_id__')
        assert resp.status_code in (404, 500)
        body = resp.get_json()
        assert body.get('success') is False or 'error' in body


# ── 平台路径 / 流水线 / 模型列表 ─────────────────────────────────────────

class TestPlatformMeta:
    def test_defect_categories(self, client):
        resp = client.get('/api/defect-categories')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True

    def test_platform_paths(self, client):
        resp = client.get('/api/platform-paths')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_pipelines_list(self, client):
        resp = client.get('/api/pipelines')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True

    def test_deployed_models(self, client):
        resp = client.get('/api/deployed-models')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_training_models(self, client):
        resp = client.get('/api/training-models')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ── 图片访问安全 ─────────────────────────────────────────────────────────

class TestImageSecurity:
    def test_image_missing_path_param(self, client):
        resp = client.get('/api/image/test.jpg')
        assert resp.status_code == 400

    def test_image_forbidden_path(self, client):
        resp = client.get('/api/image/x.jpg?path=/etc/passwd')
        assert resp.status_code == 403

    def test_image_nonexistent_allowed_root_returns_placeholder(self, client, monkeypatch):
        monkeypatch.setattr(
            'studio.forge.forge_paths.safe_read_path',
            lambda p: True,
        )
        resp = client.get('/api/image/missing.png?path=/tmp/detforge_test_missing.png')
        assert resp.status_code == 200
        assert resp.mimetype == 'image/png'


# ── 导出 / 归档（无 task 时应 404）──────────────────────────────────────

class TestExportArchive:
    def test_export_coco_missing_task(self, client):
        resp = client.get('/api/export/__missing_task__')
        assert resp.status_code == 404

    def test_export_csv_missing_task(self, client):
        resp = client.get('/api/export-csv/__missing_task__')
        assert resp.status_code == 404

    def test_coco_json_missing_task(self, client):
        resp = client.get('/api/coco/__missing_task__')
        assert resp.status_code == 404

    def test_archive_missing_task(self, client, json_headers):
        resp = client.post(
            '/api/archive/__missing_task__',
            data=json.dumps({'entries': []}),
            headers=json_headers,
        )
        assert resp.status_code in (404, 400, 500)


# ── Python 独立执行 ──────────────────────────────────────────────────────

class TestRunPythonCode:
    def test_empty_code_rejected(self, client, json_headers):
        resp = client.post('/api/run-python-code', data=json.dumps({}), headers=json_headers)
        assert resp.status_code in (400, 500)

    def test_simple_filter_on_mock_task(self, client, json_headers, monkeypatch, app):
        task_id = 'test_run_py_task'
        task_dir = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
        os.makedirs(task_dir, exist_ok=True)
        csv_path = os.path.join(task_dir, 'result.csv')
        pd.DataFrame([{'check_status': '1'}, {'check_status': '0'}]).to_csv(csv_path, index=False)
        try:
            resp = client.post(
                '/api/run-python-code',
                data=json.dumps({
                    'task_id': task_id,
                    'python_code': 'def process_data(df):\n    return df.head(1)',
                }),
                headers=json_headers,
            )
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['success'] is True
            assert body.get('output_rows') == 1
        finally:
            import shutil
            shutil.rmtree(task_dir, ignore_errors=True)


# ── Forge：预测 / 模型 / 作业 ────────────────────────────────────────────

class TestForgePredict:
    def test_predict_result_source(self, client):
        resp = client.get('/api/forge/predict-result/source')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'predict_result' in body.get('table', '')
        assert 'default_sql' in body

    def test_schema_status_returns_json(self, client):
        resp = client.get('/api/forge/schema/status')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'success' in body

    def test_list_models_returns_json(self, client):
        resp = client.get('/api/forge/models')
        body = resp.get_json()
        assert isinstance(body, dict)
        assert 'success' in body

    def test_list_jobs_returns_json(self, client):
        resp = client.get('/api/forge/jobs')
        body = resp.get_json()
        assert isinstance(body, dict)
        assert 'success' in body

    def test_predict_job_missing_body(self, client, json_headers):
        resp = client.post('/api/forge/jobs/predict', data=json.dumps({}), headers=json_headers)
        assert resp.status_code in (400, 500)
        assert resp.get_json().get('success') is False

    def test_predict_batch_missing_body(self, client, json_headers):
        resp = client.post('/api/forge/jobs/predict/batch', data=json.dumps({}), headers=json_headers)
        assert resp.status_code in (400, 500)

    def test_job_detail_nonexistent(self, client):
        resp = client.get('/api/forge/jobs/999999999')
        assert resp.status_code in (404, 500)
        assert resp.get_json().get('success') is False

    def test_exports_download_missing_path(self, client):
        resp = client.get('/api/forge/exports/download')
        assert resp.status_code in (400, 404, 500)


# ── Forge：人工质检 ──────────────────────────────────────────────────────

class TestForgeManualQc:
    def test_categories_get(self, client):
        resp = client.get('/api/forge/manual-qc/categories')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True

    def test_lookup_empty_sn(self, client):
        resp = client.get('/api/forge/manual-qc/lookup?sn=')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body.get('count') == 0

    def test_list_records(self, client):
        resp = client.get('/api/forge/manual-qc')
        body = resp.get_json()
        assert isinstance(body, dict)
        assert 'success' in body

    def test_export_empty_range_returns_json(self, client, json_headers):
        resp = client.post(
            '/api/forge/manual-qc/export',
            data=json.dumps({'start': '2099-01-01', 'end': '2099-01-02'}),
            headers=json_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True


# ── Forge：训练平台同步 ──────────────────────────────────────────────────

class TestForgeSync:
    def test_list_projects(self, client):
        resp = client.get('/api/forge/sync/projects')
        body = resp.get_json()
        assert isinstance(body, dict)
        assert 'success' in body

    def test_list_datasets(self, client):
        resp = client.get('/api/forge/sync/datasets')
        body = resp.get_json()
        assert isinstance(body, dict)

    def test_list_train_models(self, client):
        resp = client.get('/api/forge/sync/train-models')
        body = resp.get_json()
        assert isinstance(body, dict)

    def test_discover_without_auth(self, client, json_headers):
        resp = client.post('/api/forge/sync/discover', data=json.dumps({}), headers=json_headers)
        assert resp.status_code in (400, 500)


# ── Viz / Unify 桥接 ─────────────────────────────────────────────────────

class TestVizUnifyBridge:
    def test_viz_status(self, client):
        resp = client.get('/api/viz/status')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'available' in body
        assert 'mount_prefix' in body

    def test_viz_open_missing_task(self, client, json_headers):
        resp = client.post(
            '/api/viz/open',
            data=json.dumps({'source': 'query_task'}),
            headers=json_headers,
        )
        assert resp.status_code in (400, 500)

    def test_viz_session_nonexistent(self, client):
        resp = client.get('/api/viz/session/__nonexistent__')
        assert resp.status_code in (404, 500)

    def test_unify_status(self, client):
        resp = client.get('/api/unify/status')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body.get('viewer_path') == '/online-predict'


# ── 可选 API Token 鉴权 ──────────────────────────────────────────────────

class TestEnvProfiles:
    def test_list_env_profiles(self, client):
        resp = client.get('/api/env-profiles')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        assert isinstance(body.get('data'), list)

    def test_save_get_delete_env_profile(self, client, json_headers):
        payload = {
            'id': 'pytest_env_profile',
            'name': 'pytest',
            'vars': [{'key': 'NUM', 'value': '42', 'label': '数量'}],
            'strategy_hints': ['daily_trawl'],
        }
        save = client.post('/api/env-profiles', data=json.dumps(payload), headers=json_headers)
        assert save.status_code == 200
        assert save.get_json()['data']['id'] == 'pytest_env_profile'

        get_one = client.get('/api/env-profiles/pytest_env_profile')
        assert get_one.status_code == 200
        assert get_one.get_json()['data']['vars'][0]['value'] == '42'

        delete = client.delete('/api/env-profiles/pytest_env_profile')
        assert delete.status_code == 200

    def test_suggest_env_profile_vars(self, client, json_headers):
        resp = client.post(
            '/api/env-profiles/suggest',
            data=json.dumps({'strategy_id': 'replay_post_ng'}),
            headers=json_headers,
        )
        assert resp.status_code == 200
        keys = {row['key'] for row in resp.get_json().get('data', [])}
        assert 'MIN_SCORE' in keys


class TestOptionalApiToken:
    def test_unauthorized_when_token_configured(self, client, monkeypatch):
        monkeypatch.setattr(
            'server.core.load_config',
            lambda: {'api_token': 'secret-test-token'},
        )
        resp = client.get('/api/config')
        assert resp.status_code == 401
        assert '未授权' in resp.get_json().get('error', '')

    def test_authorized_with_header(self, client, monkeypatch):
        monkeypatch.setattr(
            'server.core.load_config',
            lambda: {'api_token': 'secret-test-token'},
        )
        resp = client.get('/api/config', headers={'X-API-Token': 'secret-test-token'})
        assert resp.status_code == 200

    def test_spa_not_blocked_by_token(self, client, monkeypatch):
        monkeypatch.setattr(
            'server.core.load_config',
            lambda: {'api_token': 'secret-test-token'},
        )
        resp = client.get('/')
        assert resp.status_code == 200
