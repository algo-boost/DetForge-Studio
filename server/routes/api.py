"""REST API routes."""
from flask import Blueprint, request, jsonify, send_file, current_app
import traceback
import json
import os
import zipfile
import threading
import time
import pandas as pd
from datetime import datetime

from server.core import *
from server.core import _fetch_approaches, _resolve_query_python, _resolve_filter_rules_code
from studio.export.csv2coco import build_coco_info
from studio.export.task_images import normalize_coco_images_for_task
from studio.timezone_util import (
    format_iso_now,
    format_timestamp,
    resolve_timezone,
    stamp_compact,
    timezone_options_for_api,
)
from studio.flow.flow_compiler import (
    compile_filter_rules,
    normalize_strategy,
    resolve_strategy_python,
    extract_rules_compile_flow,
    has_inline_sampling,
    references_filter_rules,
    references_random_sample,
)
import re
from studio.flow.flow_schema import prepare_strategy, validate_flow, FLOW_IR_VERSION
from studio.flow.flow_registry import build_node_registry
from studio.query.deployed_models import fetch_deployed_models, fetch_training_models
from studio.query.pipeline_rules import fetch_pipelines, fetch_pipeline_filter_rules, fetch_pipeline_nodes
from studio.query.strategy_loader import (
    STRATEGIES_DIR,
    TEMPLATES_DIR,
    get_all_strategies as _get_all_strategies,
    get_all_templates as _get_all_templates,
)
from studio.query.strategy_executor import execute_strategy_ref
from studio.query.env_context import build_stage_context, describe_strategy_variables, find_unresolved_template_vars, format_unresolved_vars_error, substitute_template
from studio.forge import forge_paths
from studio.brand import PRODUCT_NAME, PRODUCT_TAGLINE

api_bp = Blueprint('api', __name__)

_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'docs')


@api_bp.route('/api/docs/user-guide', methods=['GET'])
def get_user_guide():
    """返回用户使用手册 Markdown（供应用内 /docs 页面渲染）。"""
    path = os.path.join(_DOCS_DIR, 'USER_GUIDE.md')
    if not os.path.isfile(path):
        return jsonify({'success': False, 'error': '文档不存在'}), 404
    with open(path, encoding='utf-8') as f:
        content = f.read()
    return jsonify({
        'success': True,
        'title': f'{PRODUCT_NAME} 用户使用手册',
        'tagline': PRODUCT_TAGLINE,
        'content': content,
        'updated_at': format_timestamp(os.path.getmtime(path)),
    })


@api_bp.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        config = load_config()
        client = get_db_client()
        bundle = get_defect_categories_bundle()
        paths = get_platform_paths_bundle()
        safe_config = config.copy()
        safe_config['defect_categories'] = bundle.get('categories', [])
        safe_config['defect_categories_source'] = bundle.get('source', '')
        safe_config['defect_categories_meta'] = bundle.get('meta', {})
        safe_config['id2name'] = bundle.get('id2name', safe_config.get('id2name', {}))
        safe_config['platform_root'] = paths.get('platform_root', '')
        safe_config['local_file_base'] = paths.get('local_file_base', '')
        safe_config['platform_root_candidates'] = paths.get('candidates', [])
        safe_config['platform_paths_source'] = paths.get('source', '')
        safe_config['approaches'] = _fetch_approaches(client)
        safe_config['db_connected'] = bool(client and client.ensure_alive())
        from server.viz_mount import is_viz_available
        safe_config['viz_available'] = is_viz_available(config)
        from server.unify_mount import is_unify_available
        safe_config['unify_available'] = is_unify_available(config)
        img_path = (safe_config.get('img_base_path') or '').strip()
        archive_path = (safe_config.get('archive_base_path') or '').strip()
        from studio.forge.predict_runtime import resolve_predict_settings, validate_predict_settings
        predict_settings, predict_checks = validate_predict_settings(config)
        safe_config['predict_runtime'] = predict_settings
        path_checks = {
            'img_base_path_exists': bool(img_path and os.path.isdir(img_path)),
            'archive_base_path_exists': bool(archive_path and os.path.isdir(archive_path)),
            **predict_checks,
        }
        sync_root = str(safe_config.get('dataset_sync_root') or 'datasets').strip()
        if sync_root and not os.path.isabs(sync_root):
            from server.core import BASE_DIR
            sync_root_abs = os.path.join(BASE_DIR, sync_root)
        else:
            sync_root_abs = sync_root
        path_checks['dataset_sync_root_exists'] = bool(sync_root_abs and os.path.isdir(sync_root_abs))

        # 敏感字段不回传明文，仅返回是否已配置
        from studio.sync import magic_fox_bridge
        mf_status = magic_fox_bridge.auth_status(config)
        safe_config.update(mf_status)
        safe_config.pop('magic_fox_password', None)
        safe_config.pop('magic_fox_access_token', None)
        from server.core import read_config_file_raw, secret_field_set_on_disk, CONFIG_FILE
        raw_cfg = read_config_file_raw()
        safe_config['api_token_set'] = bool(
            str(config.get('api_token') or '').strip() or secret_field_set_on_disk('api_token')
        )
        safe_config['api_token'] = ''
        safe_config['db_password'] = ''
        safe_config['db_password_set'] = bool(
            str(config.get('db_password') or '').strip() or secret_field_set_on_disk('db_password')
        )
        decrypt_errors = safe_config.pop('_config_decrypt_errors', None) or []
        if decrypt_errors:
            safe_config['config_decrypt_errors'] = decrypt_errors
            safe_config['config_decrypt_hint'] = (
                '部分敏感字段无法解密，请确认 .config.key 与 config.json 配对；'
                '勿在未解密时保存配置，以免覆盖口令。'
            )
        safe_config['config_file'] = CONFIG_FILE
        safe_config['config_file_exists'] = os.path.isfile(CONFIG_FILE)

        from studio.config_crypto import secrets_encryption_status
        config_secrets = secrets_encryption_status()

        return jsonify({
            'success': True,
            'config': safe_config,
            'path_checks': path_checks,
            'config_secrets': config_secrets,
            'timezone_options': timezone_options_for_api(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/config', methods=['POST'])
def save_config_api():
    """保存配置"""
    try:
        data = request.json
        incoming = data.get('config', {})
        current = load_config()
        readonly = {
            'defect_categories', 'defect_categories_source', 'defect_categories_meta',
            'platform_root', 'local_file_base', 'platform_root_candidates',
            'platform_paths_source', 'approaches', 'db_connected', 'viz_available', 'unify_available', 'predict_runtime',
            'magic_fox_configured', 'magic_fox_password_set', 'magic_fox_token_set', 'api_token_set',
        }
        from server.core import preserve_secrets_for_save
        config = {**current, **{k: v for k, v in incoming.items() if k not in readonly}}
        config = preserve_secrets_for_save(config, incoming)
        if config.get('_config_decrypt_errors') and not any(
            str(incoming.get(k) or '').strip() for k in ('db_password', 'magic_fox_password', 'magic_fox_access_token')
        ):
            return jsonify({
                'success': False,
                'error': '配置口令无法解密，请先恢复 .config.key 或在表单中重新填写密码后再保存',
                'config_decrypt_errors': config.get('_config_decrypt_errors'),
            }), 400

        mode = str(config.get('magic_fox_auth_mode') or 'password').strip().lower()
        if mode not in ('password', 'token'):
            config['magic_fox_auth_mode'] = 'password'

        # 验证必填字段
        required_fields = ['db_host', 'db_user', 'db_database']
        for field in required_fields:
            if not str(config.get(field) or '').strip():
                return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

        # 如果使用拼接模式，需要 img_base_path
        if config.get('img_path_mode', 'concat') == 'concat' and not str(config.get('img_base_path') or '').strip():
            return jsonify({'success': False, 'error': '使用拼接模式时需要提供 img_base_path'}), 400

        tz_raw = str(config.get('timezone') or '').strip()
        if tz_raw:
            config['timezone'] = str(resolve_timezone(tz_raw).key)
        else:
            config['timezone'] = 'Asia/Shanghai'

        # 更新配置并重新连接
        if update_config_and_reconnect(config):
            get_defect_categories_bundle(force_refresh=True)
            warnings = []
            for key, label in (
                ('img_base_path', '图片基础路径'),
                ('archive_base_path', '归档根目录'),
            ):
                path = str(config.get(key) or '').strip()
                if path and not os.path.isdir(path):
                    warnings.append(f'{label} 不存在: {path}')
            client = get_db_client()
            mf_probe = {}
            from studio.sync import magic_fox_bridge
            mf_status = magic_fox_bridge.auth_status(config)
            if mf_status.get('magic_fox_configured'):
                try:
                    magic_fox_bridge.test_connection(config)
                    mf_probe = {'magic_fox_reachable': True, **mf_status}
                except Exception as mf_err:  # noqa: BLE001
                    mf_probe = {
                        'magic_fox_reachable': False,
                        'magic_fox_error': str(mf_err),
                        **mf_status,
                    }
            else:
                mf_probe = mf_status
            return jsonify({
                'success': True,
                'message': '配置保存成功',
                'warnings': warnings,
                'db_connected': bool(client and client.ensure_alive()),
                'auth': mf_probe,
            })
        else:
            return jsonify({'success': False, 'error': '保存配置失败'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/config/test-connection', methods=['POST'])
def test_connection():
    """测试数据库连接；成功后将连接参数写入 config.json 并重建全局连接。"""
    try:
        from server.core import update_config_and_reconnect

        data = request.json or {}
        host = str(data.get('host', '') or '').strip()
        user = str(data.get('user', '') or '').strip()
        password = data.get('password', '')
        database = str(data.get('database', '') or '').strip()

        current = load_config()
        if not str(password).strip():
            password = current.get('db_password', '')

        if not all([host, user, database]):
            return jsonify({'success': False, 'error': '请填写主机、用户名和数据库名'}), 400

        test_client = MySQLClient(host, user, password, database)
        if not test_client.connection:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500
        test_client.close()

        from server.core import preserve_secrets_for_save
        updated = preserve_secrets_for_save(
            {**current, 'db_host': host, 'db_user': user, 'db_database': database},
            {'db_password': password},
        )
        if str(password).strip():
            updated['db_password'] = password
        if not update_config_and_reconnect(updated):
            return jsonify({'success': False, 'error': '连接成功但写入 config.json 失败'}), 500

        client = get_db_client()
        return jsonify({
            'success': True,
            'message': '数据库连接成功，凭据已写入 config.json',
            'saved': True,
            'db_connected': bool(client and client.ensure_alive()),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/config/test-magic-fox', methods=['POST'])
def test_magic_fox_connection():
    """测试 Magic-Fox 训练平台认证（可使用表单临时值，空密码/空 token 沿用已保存配置）。"""
    try:
        from studio.sync import magic_fox_bridge
        from server.core import update_config_and_reconnect
        data = request.json or {}
        cfg = magic_fox_bridge.merge_auth_overrides(load_config(), data)
        magic_fox_bridge.test_connection(cfg)
        status = magic_fox_bridge.auth_status(cfg)
        saved = False
        if status.get('magic_fox_configured'):
            to_save = magic_fox_bridge.build_config_to_persist(load_config(), data)
            if update_config_and_reconnect(to_save):
                saved = True
                status = magic_fox_bridge.auth_status(to_save)
        return jsonify({
            'success': True,
            'message': 'Magic-Fox 认证成功' + ('，凭据已写入 config.json' if saved else ''),
            'auth': status,
            'saved': saved,
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(e)}), 400


def _run_query_sync(data):
    from studio.query.query_runner import run_query_request
    return run_query_request(
        data,
        get_db_client=get_db_client,
        execute_python_filter=execute_python_filter,
        build_query_task=build_query_task,
        sample_size_from_env=sample_size_from_env,
        parse_random_seed=parse_random_seed,
        resolve_query_python=_resolve_query_python,
    )


@api_bp.route('/api/query', methods=['POST'])
def query_database():
    """执行 SQL 查询（同步，兼容旧客户端）"""
    try:
        data = request.json
        result = _run_query_sync(data)
        status = result.pop('status_code', 200 if result.get('success') else 500)
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/query/jobs', methods=['POST'])
def create_query_job():
    """提交后台查询任务（可切换页面、可并发多条）。"""
    try:
        from studio.query import query_jobs
        data = dict(request.json or {})
        label = (data.pop('label', None) or data.pop('strategy_name', None) or '').strip()
        if not str(data.get('sql', '')).strip():
            return jsonify({'success': False, 'error': 'SQL 查询语句不能为空'}), 400
        job = query_jobs.submit_query_job(data, label=label)
        return jsonify({'success': True, 'query_job_id': job['id'], 'job': job})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/query/jobs', methods=['GET'])
def list_query_jobs_route():
    try:
        from studio.query import query_jobs
        limit = min(50, int(request.args.get('limit', 30)))
        active_only = request.args.get('active_only', '').lower() in ('1', 'true', 'yes')
        jobs = query_jobs.list_query_jobs(limit=limit, active_only=active_only)
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/query/jobs/<job_id>', methods=['GET'])
def get_query_job_route(job_id):
    try:
        from studio.query import query_jobs
        job = query_jobs.get_query_job(job_id)
        if not job:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        return jsonify({'success': True, 'job': job})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/preview-filter', methods=['POST'])
def preview_filter():
    """轻量预览：SQL 行数 → 规则筛选后行数 → 采样后预估。"""
    try:
        data = request.json or {}
        sql_template = data.get('sql', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        preview_mode = data.get('preview_mode', 'rules')  # rules | full

        if not sql_template:
            return jsonify({'success': False, 'error': 'SQL 查询语句不能为空'}), 400

        strategy = _get_all_strategies().get((data.get('strategy_id') or '').strip()) if data.get('strategy_id') else None
        env_schema = data.get('env_schema')
        if strategy and not env_schema:
            from studio.query.strategy_env_schema import merge_strategy_env_schema
            env_schema = merge_strategy_env_schema(strategy, _get_all_templates())

        env_ctx = build_stage_context(
            data,
            start_time=start_time,
            end_time=end_time,
            job_id=data.get('predict_job_id') or data.get('job_id'),
            env_schema=env_schema,
        )
        sample_size = sample_size_from_env(env_ctx)
        random_seed = parse_random_seed(env_ctx.get('RANDOM_SEED'))
        sql = substitute_template(sql_template, env_ctx)
        unresolved = find_unresolved_template_vars(sql)
        if unresolved:
            return jsonify({
                'success': False,
                'error': format_unresolved_vars_error(unresolved, env_schema),
                'unresolved_vars': unresolved,
            }), 400
        client = get_db_client()
        df = client.query(sql)
        if df is None:
            detail = getattr(client, 'last_query_error', None) or ''
            msg = f'查询失败：{detail}' if detail else '查询失败'
            return jsonify({'success': False, 'error': msg}), 500

        sql_rows = len(df)
        if df.empty:
            return jsonify({
                'success': True,
                'sql_rows': 0,
                'filter_rows': 0,
                'after_sample': 0,
                'sample_size': sample_size,
                'message': 'SQL 查询结果为空',
            })

        templates = _get_all_templates()
        filter_rows = sql_rows
        execution_time = 0.0
        console_output = ''
        filter_python_ran = False

        if preview_mode != 'full':
            from studio.flow.process_pipeline import ensure_process_pipeline
            pipe = data.get('process_pipeline')
            if not pipe and strategy:
                pipe = ensure_process_pipeline(strategy, templates)
            py_snippet = (data.get('python_code') or '')
            if pipe or re.search(r'\bview\s*\(', py_snippet):
                preview_mode = 'full'
            elif references_filter_rules(py_snippet) or references_random_sample(py_snippet):
                preview_mode = 'full'

        ds = data.get('data_source') or env_ctx.get('DATA_SOURCE') or 'detail'
        sql_had_ext = 'ext' in df.columns
        if ds == 'predict_result':
            from studio.forge.predict_result_filters import hydrate_predict_result_df

            df = hydrate_predict_result_df(df)
            sql_rows = len(df)

        if preview_mode == 'full':
            try:
                merge_data = dict(data)
                if strategy:
                    if not (merge_data.get('python_code') or '').strip():
                        merge_data['python_code'] = strategy.get('python_code') or ''
                    if not merge_data.get('process_pipeline') and strategy.get('process_pipeline'):
                        merge_data['process_pipeline'] = strategy.get('process_pipeline')
                    if not merge_data.get('flow') and strategy.get('flow'):
                        merge_data['flow'] = strategy.get('flow')
                    if not merge_data.get('filter_rules_code') and strategy.get('filter_rules_code'):
                        merge_data['filter_rules_code'] = strategy.get('filter_rules_code')
                from studio.query.query_runner import _resolve_query_python_for_request

                python_code = _resolve_query_python_for_request(merge_data, templates, _resolve_query_python)
            except ValueError as e:
                return jsonify({'success': False, 'error': str(e)}), 400
            if python_code:
                try:
                    filter_python_ran = True
                    df, console_output, execution_time = execute_python_filter(
                        df,
                        python_code,
                        capture_output=True,
                        env_context=env_ctx,
                        strategy=strategy,
                    )
                    filter_rows = len(df)
                    if ds == 'predict_result':
                        from studio.forge.predict_result_filters import finalize_predict_result_df

                        df = finalize_predict_result_df(df)
                        filter_rows = len(df)
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'process_data 执行失败: {str(e)}',
                        'traceback': traceback.format_exc(),
                    }), 500
        else:
            from studio.query.query_runner import resolve_filter_rules_for_request

            merge_rules = dict(data)
            if strategy:
                if not merge_rules.get('flow') and strategy.get('flow'):
                    merge_rules['flow'] = strategy.get('flow')
            rules_code = resolve_filter_rules_for_request(merge_rules, templates, _resolve_filter_rules_code)
            if rules_code:
                try:
                    filter_python_ran = True
                    start = time.time()
                    df = execute_filter_rules_only(df, rules_code, env_context=env_ctx, strategy=strategy)
                    if ds == 'predict_result':
                        from studio.forge.predict_result_filters import finalize_predict_result_df

                        df = finalize_predict_result_df(df)
                    execution_time = time.time() - start
                    filter_rows = len(df)
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'规则筛选失败: {str(e)}',
                        'traceback': traceback.format_exc(),
                    }), 500

        flow_payload = data.get('flow') if (data.get('flow') or {}).get('nodes') else None
        from studio.flow.flow_compiler import has_inline_sampling

        if preview_mode == 'full':
            after_sample = filter_rows
        elif not has_inline_sampling('', flow_payload):
            after_sample = filter_rows
        elif sample_size is None:
            after_sample = filter_rows
        else:
            after_sample = min(sample_size, filter_rows) if filter_rows else 0
        post_sample_skipped = True
        unique_products = None
        if 'product_no' in df.columns:
            unique_products = int(df['product_no'].nunique())

        preview_resp = {
            'success': True,
            'sql_rows': sql_rows,
            'filter_rows': filter_rows,
            'after_sample': after_sample,
            'sample_size': sample_size,
            'unique_products': unique_products,
            'execution_time': round(execution_time, 3),
            'preview_mode': preview_mode,
            'post_sample_skipped': post_sample_skipped,
            'console_output': console_output or '',
        }
        if ds == 'predict_result':
            from studio.forge.predict_result_filters import predict_filter_warnings

            fw = predict_filter_warnings(
                df,
                data_source=ds,
                sql_had_ext=sql_had_ext,
                python_ran=filter_python_ran,
            )
            if fw:
                preview_resp['filter_warnings'] = fw
        return jsonify(preview_resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _make_placeholder_image(text="图片未找到", width=400, height=300):
    """生成占位图片"""
    from PIL import Image, ImageDraw, ImageFont
    import io
    img = Image.new('RGB', (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    # 边框
    draw.rectangle([0, 0, width-1, height-1], outline=(200, 200, 200), width=2)
    # 居中文字
    lines = text.split('/')
    display_text = '\n'.join(lines[-3:]) if len(lines) > 3 else text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.multiline_textbbox((0, 0), display_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(((width-tw)/2, (height-th)/2), display_text, fill=(150, 150, 150), font=font, align="center")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


@api_bp.route('/api/image/<path:filename>')
def get_image(filename):
    """获取图片（从原始路径）"""
    try:
        # 从查询参数获取完整路径
        img_path = request.args.get('path', '')
        if not img_path:
            return jsonify({'error': '图片路径不能为空'}), 400

        # 安全：仅允许读取白名单根目录内的图片（防任意文件读取）
        if not forge_paths.safe_read_path(img_path):
            return jsonify({'error': '路径不在允许范围内'}), 403

        # 检查文件是否存在
        if not os.path.exists(img_path):
            buf = _make_placeholder_image(img_path)
            return send_file(buf, mimetype='image/png')
        
        # 返回图片文件
        return send_file(img_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/export/<task_id>', methods=['GET', 'POST'])
def export_coco(task_id):
    """导出 COCO 格式文件（包含图片和JSON的ZIP包）"""
    try:
        task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
        coco_path = os.path.join(task_dir, '_annotations.coco.json')
        csv_path = os.path.join(task_dir, 'result.csv')

        if not os.path.exists(coco_path):
            return jsonify({'error': 'COCO 文件不存在'}), 404

        selected_list = None
        if request.method == 'POST':
            data = request.get_json() or {}
            raw = data.get('selected_indices')
            if raw is not None and len(raw) > 0:
                selected_list = [int(idx) for idx in raw]

        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)

        query_meta = {}
        meta_path = os.path.join(task_dir, 'query_meta.json')
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    query_meta = json.load(f)
            except Exception:
                query_meta = {}
        if query_meta.get('data_source') == 'predict_result':
            from studio.export.pred_coco_layout import ensure_predict_annotations_for_export
            from server.core import get_effective_id2name
            coco_data = ensure_predict_annotations_for_export(
                coco_data, task_dir, id2name=get_effective_id2name(),
            )

        if selected_list:
            selected_set = set(selected_list)
            filtered_images = [img for img in coco_data['images'] if img.get('id') in selected_set]
            selected_image_ids = {img['id'] for img in filtered_images}
            filtered_annotations = [
                ann for ann in coco_data['annotations']
                if ann.get('image_id') in selected_image_ids
            ]
            coco_data = {
                'info': coco_data.get('info') or build_coco_info(),
                'images': filtered_images,
                'annotations': filtered_annotations,
                'categories': coco_data.get('categories', []),
            }

        image_files = normalize_coco_images_for_task(
            task_dir, coco_data, selected_list, for_export=True,
        )

        zip_filename = f'coco_export_{task_id}.zip'
        zip_path = os.path.join(current_app.config['UPLOAD_FOLDER'], zip_filename)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr(
                    '_annotations.coco.json',
                    json.dumps(coco_data, ensure_ascii=False, indent=4),
                )
                if os.path.exists(csv_path):
                    zipf.write(csv_path, 'result.csv')
                for src, arc in image_files:
                    zipf.write(src, arc)

            response = send_file(
                zip_path,
                as_attachment=True,
                download_name=f'coco_export_{task_id}.zip',
                mimetype='application/zip',
            )

            def remove_file():
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except Exception:
                    pass

            threading.Timer(60.0, remove_file).start()
            return response
        except Exception as zip_error:
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass
            raise zip_error

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/export-csv/<task_id>')
def export_csv(task_id):
    """导出 CSV 文件"""
    try:
        task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
        csv_path = os.path.join(task_dir, 'result.csv')
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'CSV 文件不存在'}), 404
        
        return send_file(csv_path, as_attachment=True, download_name='result.csv')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/archive/jobs/<job_id>', methods=['GET'])
def get_archive_job_route(job_id):
    """轮询归档后台任务进度。"""
    try:
        from studio.export import archive_jobs
        job = archive_jobs.get_archive_job(job_id)
        if not job:
            return jsonify({'success': False, 'error': '归档任务不存在'}), 404
        return jsonify({'success': True, 'job': job})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/archive/<task_id>', methods=['POST'])
def archive_results(task_id):
    """提交 COCO 归档后台任务（立即返回 job_id，前端轮询进度）。"""
    try:
        from studio.export import archive_jobs
        data = request.get_json() or {}
        job = archive_jobs.submit_archive_job(task_id, data)
        return jsonify({
            'success': True,
            'archive_job_id': job['id'],
            'job': job,
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/query/task/<task_id>', methods=['GET'])
def get_query_task(task_id):
    """恢复已保存的查询任务结果（返回查询页 / 历史跳转用）。"""
    try:
        from server.core import load_query_task_results
        upload_folder = current_app.config['UPLOAD_FOLDER']
        loaded = load_query_task_results(task_id, upload_folder)
        if not loaded:
            return jsonify({'success': False, 'error': '任务不存在或缺少 result.csv'}), 404
        return jsonify({'success': True, **loaded})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/coco/<task_id>')
def get_coco_data(task_id):
    """获取 COCO 格式数据"""
    try:
        task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
        coco_path = os.path.join(task_dir, '_annotations.coco.json')
        
        if not os.path.exists(coco_path):
            return jsonify({'error': 'COCO 文件不存在'}), 404
        
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        
        return jsonify({'success': True, 'data': coco_data})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 策略与模板管理 ──────────────────────────────────────────────

def _load_json_dir(directory):
    """加载目录下所有 JSON 文件，返回 {id: data} 字典"""
    items = {}
    if not os.path.isdir(directory):
        return items
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'id' in data:
                            items[data['id']] = data
                except Exception as e:
                    print(f"⚠️ 加载失败: {fname}: {e}")
    return items

def _save_json(filepath, data):
    """保存 JSON 到文件，自动创建父目录"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _delete_json(directory, item_id):
    """删除对应 id 的 JSON 文件（递归搜索，UTF-8）"""
    item_id = str(item_id or '').strip()
    if not item_id or not os.path.isdir(directory):
        return False
    direct = os.path.join(directory, f'{item_id}.json')
    if os.path.isfile(direct):
        try:
            os.remove(direct)
            return True
        except OSError:
            pass
    for root, _, files in os.walk(directory):
        for fname in files:
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(root, fname)
            if fpath == direct:
                continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    if json.load(f).get('id') == item_id:
                        os.remove(fpath)
                        return True
            except Exception:
                pass
    return False

# ── 模板 API ────────────────────────────────────────────────────

@api_bp.route('/api/templates', methods=['GET'])
def list_templates():
    try:
        return jsonify({'success': True, 'data': list(_get_all_templates().values())})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/templates', methods=['POST'])
def save_template():
    try:
        data = request.json
        tpl_id = data.get('id', '').strip()
        if not tpl_id:
            return jsonify({'success': False, 'error': 'id 不能为空'}), 400
        lib_dir = os.path.join(TEMPLATES_DIR, '_library')
        filepath = os.path.join(lib_dir if data.get('_library') or data.get('_builtin') else TEMPLATES_DIR, f"{tpl_id}.json")
        _save_json(filepath, data)
        return jsonify({'success': True, 'id': tpl_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        if _delete_json(TEMPLATES_DIR, template_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '未找到模板'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── 策略 API ────────────────────────────────────────────────────

@api_bp.route('/api/python-presets', methods=['GET'])
def list_python_presets():
    try:
        from studio.query.python_preset_registry import list_preset_catalog
        return jsonify({'success': True, 'data': list_preset_catalog()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/pipeline-templates', methods=['GET'])
def list_pipeline_templates():
    """可用于 process_pipeline 的块模板目录。"""
    try:
        from studio.flow.process_pipeline import list_pipeline_templates
        return jsonify({'success': True, 'data': list_pipeline_templates(_get_all_templates())})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/strategies/compile-pipeline', methods=['POST'])
def compile_strategy_pipeline():
    """预览 process_pipeline → process_data 编译结果。"""
    try:
        from studio.flow.process_pipeline import compile_process_pipeline
        body = request.get_json(silent=True) or {}
        pipeline = body.get('process_pipeline') or []
        templates = _get_all_templates()
        result = compile_process_pipeline(pipeline, templates)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/strategies', methods=['GET'])
def list_strategies():
    try:
        templates = _get_all_templates()
        items = [normalize_strategy(s, templates) for s in _get_all_strategies().values()]
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/strategies/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    try:
        strategies = _get_all_strategies()
        if strategy_id in strategies:
            templates = _get_all_templates()
            return jsonify({
                'success': True,
                'data': normalize_strategy(strategies[strategy_id], templates),
            })
        return jsonify({'success': False, 'error': '策略不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/strategies/<strategy_id>/variables', methods=['GET'])
def get_strategy_variables(strategy_id):
    """返回策略可用环境变量（系统 + 自定义 schema / 模板推断）。"""
    try:
        strategies = _get_all_strategies()
        if strategy_id not in strategies:
            return jsonify({'success': False, 'error': '策略不存在'}), 404
        templates = _get_all_templates()
        strategy = normalize_strategy(dict(strategies[strategy_id]), templates)
        from studio.query.preset_env import apply_env_schema_defaults
        from studio.query.python_preset_registry import active_presets_for_env_schema

        vars_info = describe_strategy_variables(strategy, templates)
        schema = vars_info.get('custom_vars') or []
        vars_info['python_presets'] = active_presets_for_env_schema(strategy)
        vars_info['process_pipeline'] = strategy.get('process_pipeline') or []
        vars_info['env_defaults'] = apply_env_schema_defaults({}, schema)
        return jsonify({'success': True, 'data': vars_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── 环境变量模版 ────────────────────────────────────────────────

@api_bp.route('/api/env-profiles', methods=['GET'])
def list_env_profiles():
    try:
        from studio.query import env_profile_store
        return jsonify({'success': True, 'data': env_profile_store.list_profiles()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/env-profiles/<profile_id>', methods=['GET'])
def get_env_profile(profile_id):
    try:
        from studio.query import env_profile_store
        row = env_profile_store.get_profile(profile_id)
        if not row:
            return jsonify({'success': False, 'error': '模版不存在'}), 404
        return jsonify({'success': True, 'data': row})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/env-profiles', methods=['POST'])
def save_env_profile():
    try:
        from studio.query import env_profile_store
        data = request.json or {}
        profile = env_profile_store.save_profile(data)
        return jsonify({'success': True, 'data': profile})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/env-profiles/<profile_id>', methods=['DELETE'])
def delete_env_profile(profile_id):
    try:
        from studio.query import env_profile_store
        if env_profile_store.delete_profile(profile_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '模版不存在'}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/env-profiles/suggest', methods=['POST'])
def suggest_env_profile_vars():
    try:
        from studio.query import env_profile_store
        body = request.json or {}
        strategy_ids = body.get('strategy_ids') or []
        if body.get('strategy_id'):
            strategy_ids = list({*strategy_ids, body['strategy_id']})
        rows = env_profile_store.suggest_vars(strategy_ids)
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/strategies', methods=['POST'])
def save_strategy():
    try:
        data = request.json
        sid = data.get('id', '').strip()
        if not sid:
            return jsonify({'success': False, 'error': 'id 不能为空'}), 400
        data['updated_at'] = format_iso_now()
        if 'created_at' not in data:
            data['created_at'] = data['updated_at']
        data = prepare_strategy(data)
        templates = _get_all_templates()
        data = normalize_strategy(data, templates)
        if data.get('filter_mode') in ('flow', 'split', 'rules') and data.get('flow'):
            flow_errors = validate_flow(data['flow'])
            if flow_errors:
                return jsonify({
                    'success': False,
                    'error': '工作流校验失败: ' + '; '.join(flow_errors[:5]),
                }), 400
            rules_flow = extract_rules_compile_flow(data['flow'])
            compiled = compile_filter_rules(rules_flow, templates)
            if compiled['valid']:
                data['filter_rules_code'] = compiled['python_code']
            # python_code 保留用户手写的 process_data，不再整段覆盖
        data.pop('is_preset', None)
        data.pop('_preset', None)
        filepath = os.path.join(STRATEGIES_DIR, f'{sid}.json')
        _save_json(filepath, data)
        return jsonify({'success': True, 'id': sid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/strategies/<strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    try:
        from studio.query.strategy_loader import delete_strategy_by_id

        ok, err = delete_strategy_by_id(strategy_id)
        if ok:
            return jsonify({'success': True})
        if err == '策略不存在':
            return jsonify({'success': False, 'error': err}), 404
        return jsonify({'success': False, 'error': err or '删除失败'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── 策略执行引擎 ────────────────────────────────────────────────

@api_bp.route('/api/strategies/execute', methods=['POST'])
def execute_strategy():
    try:
        data = request.json or {}
        strategy_id = data.get('strategy_id', '')

        env_ctx = build_stage_context(
            data,
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
            sample_size=data.get('sample_size'),
            random_seed=data.get('random_seed'),
        )
        if data.get('predict_job_id') or data.get('job_id'):
            jid = data.get('predict_job_id') or data.get('job_id')
            env_ctx['JOB_ID'] = str(int(jid))
            env_ctx['PREDICT_JOB_ID'] = str(int(jid))
            env_ctx['DATA_SOURCE'] = 'predict_result'

        stage_spec = {'strategy_id': strategy_id}
        if data.get('strategy_snapshot'):
            stage_spec = {'snapshot': data['strategy_snapshot']}

        result = execute_strategy_ref(
            stage_spec,
            context=env_ctx,
            sample_size=data.get('sample_size'),
            random_seed=data.get('random_seed'),
            data_source=data.get('data_source'),
            build_task=True,
        )
        if result is None:
            return jsonify({'success': False, 'error': '策略不存在'}), 404

        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'count': result.get('count', 0),
            'task_id': result.get('task_id'),
            'sample_size': result.get('sample_size'),
            'random_seed': result.get('random_seed'),
            'rows_before_sample': result.get('rows_before_sample'),
            'post_sample_skipped': result.get('post_sample_skipped'),
            'input_rows': result.get('input_rows'),
            'input_cols': result.get('input_cols'),
            'output_rows': result.get('rows_before_sample'),
            'filter_mode': result.get('filter_mode', ''),
            'console_output': result.get('console_output'),
            'execution_time': result.get('execution_time'),
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Flow Studio API ─────────────────────────────────────────────

@api_bp.route('/api/defect-categories', methods=['GET'])
def defect_categories_api():
    try:
        force = request.args.get('refresh') == '1'
        approach_id = request.args.get('approach_id', type=int)
        bundle = get_defect_categories_bundle(force_refresh=force, approach_id_override=approach_id)
        return jsonify({'success': True, **bundle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/platform-paths', methods=['GET'])
def platform_paths_api():
    """从数据库推断 Magic-Fox 平台根目录；?drive=D 可指定盘符。"""
    try:
        config = load_config()
        if request.args.get('drive'):
            config = {**config, 'platform_root_drive': request.args.get('drive')}
        client = get_db_client()
        paths = resolve_platform_paths(client, config)
        return jsonify({'success': True, **paths})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/platform-paths/sync', methods=['POST'])
def sync_platform_paths_api():
    """将数据库推断的 local_file_base 写入 config.img_base_path。"""
    try:
        data = request.json or {}
        config = load_config()
        drive = data.get('drive') or config.get('platform_root_drive')
        if drive:
            config = {**config, 'platform_root_drive': drive}
        client = get_db_client()
        paths = resolve_platform_paths(client, config)
        updated, changed, message = sync_img_base_path(config, paths)
        if changed:
            if not update_config_and_reconnect(updated):
                return jsonify({'success': False, 'error': '保存配置失败'}), 500
        return jsonify({
            'success': True,
            'changed': changed,
            'message': message,
            'platform_root': paths.get('platform_root', ''),
            'local_file_base': paths.get('local_file_base', ''),
            'img_base_path': updated.get('img_base_path', ''),
            'candidates': paths.get('candidates', []),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/pipelines', methods=['GET'])
def pipelines_api():
    """产线 Pipeline 列表（供规则导入）。"""
    try:
        limit = request.args.get('limit', default=30, type=int)
        client = get_db_client()
        bundle = fetch_pipelines(client, limit=limit)
        return jsonify({'success': True, **bundle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/pipelines/<pipeline_id>/nodes', methods=['GET'])
def pipeline_nodes_api(pipeline_id):
    """Pipeline 下可导入规则的检测节点列表。"""
    try:
        client = get_db_client()
        nodes = fetch_pipeline_nodes(client, pipeline_id)
        return jsonify({'success': True, 'nodes': nodes, 'pipeline_id': pipeline_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/pipelines/<pipeline_id>/filter-rules', methods=['GET'])
def pipeline_filter_rules_api(pipeline_id):
    """从 pipeline 节点 param 解析筛选规则。"""
    try:
        node_id = request.args.get('node_id')
        random_drop_ratio = request.args.get('random_drop_ratio', default=0.0, type=float)
        remove_empty = request.args.get('remove_empty', default='1') != '0'
        client = get_db_client()
        bundle = get_defect_categories_bundle()
        result = fetch_pipeline_filter_rules(
            client,
            pipeline_id,
            node_id=node_id,
            random_drop_ratio=random_drop_ratio or 0.0,
            remove_empty=remove_empty,
            known_categories=bundle.get('categories') or [],
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/deployed-models', methods=['GET'])
def deployed_models_api():
    """查询部署模型及完整 .pt 路径。"""
    try:
        config = load_config()
        approach_id = request.args.get('approach_id', type=int)
        limit = request.args.get('limit', default=30, type=int)
        drive = request.args.get('drive')
        client = get_db_client()
        bundle = fetch_deployed_models(
            client, config, approach_id=approach_id, limit=limit, drive=drive,
        )
        return jsonify({'success': True, **bundle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/training-models', methods=['GET'])
def training_models_api():
    """查询训练模型：优先 detforge 平台缓存（project_id），否则 vision_backend.modeltrainconfig。"""
    try:
        config = load_config()
        approach_id = request.args.get('approach_id', type=int)
        project_id = request.args.get('project_id', type=int)
        limit = request.args.get('limit', default=100, type=int)
        force_sync = request.args.get('sync', type=int) == 1

        if project_id:
            from studio.sync import platform_models
            if force_sync:
                bundle = platform_models.sync_project_train_models(project_id, force=True)
            else:
                bundle = platform_models.list_project_train_models(project_id)
                if not bundle.get('models'):
                    bundle = platform_models.sync_project_train_models(project_id, force=True)
            models = (bundle.get('models') or [])[:limit]
            return jsonify({
                'success': True,
                'models': models,
                'meta': {
                    'approach_id': bundle.get('approach_id') or approach_id,
                    'source': 'platform_cache',
                    'project_id': project_id,
                    'count': len(models),
                    'synced_count': bundle.get('synced_count'),
                },
            })

        client = get_db_client()
        bundle = fetch_training_models(client, config, approach_id=approach_id, limit=limit)
        return jsonify({'success': True, **bundle})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/flow/nodes', methods=['GET'])
def list_flow_nodes():
    try:
        bundle = get_defect_categories_bundle()
        templates = _get_all_templates()
        nodes = build_node_registry(templates, bundle.get('categories'))
        return jsonify({
            'success': True,
            'data': nodes,
            'defect_categories': bundle.get('categories', []),
            'defect_categories_source': bundle.get('source', ''),
            'defect_categories_meta': bundle.get('meta', {}),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/flow/compile', methods=['POST'])
def compile_flow_api():
    try:
        data = request.json or {}
        flow = data.get('flow') or {}
        templates = _get_all_templates()
        target = data.get('target', 'process_data')
        if target == 'filter_rules':
            flow = extract_rules_compile_flow(flow)
            result = compile_filter_rules(flow, templates)
        elif target == 'sample_function':
            result = {
                'python_code': compile_sample_code(flow, templates),
                'valid': True,
                'errors': [],
            }
        else:
            result = compile_flow(flow, templates)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/flow/schema', methods=['GET'])
def flow_schema_api():
    return jsonify({
        'success': True,
        'flow_version': FLOW_IR_VERSION,
        'strategy_schema_version': 2,
        'containers': ['control.if', 'control.loop'],
        'branches': {'control.if': ['then', 'else'], 'control.loop': ['body']},
    })


# ── Python 代码执行 ─────────────────────────────────────────────

@api_bp.route('/api/run-python-code', methods=['POST'])
def run_python_code():
    """独立运行 Python 筛选代码（可用于测试或二次筛选）"""
    try:
        data = request.json or {}
        code = data.get('python_code', '').strip()
        task_id = data.get('task_id')

        if not code:
            return jsonify({'success': False, 'error': 'Python 代码不能为空'}), 400

        if task_id:
            csv_path = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id, 'result.csv')
            if not os.path.exists(csv_path):
                return jsonify({'success': False, 'error': '任务不存在或 CSV 未找到'}), 404
            df = pd.read_csv(csv_path, encoding='utf-8')
            is_test_data = False
        else:
            df = pd.DataFrame({
                'product_no': ['P001', 'P002', 'P003'],
                'check_status': ['1', '0', '1'],
                'c_time': ['2026-01-01', '2026-01-02', '2026-01-03'],
            })
            is_test_data = True

        input_rows, input_cols = len(df), len(df.columns)
        df, console_output, execution_time = execute_python_filter(df, code, capture_output=True)

        message = '代码执行成功'
        if is_test_data:
            message += '\n数据来源: 测试数据'
        else:
            message += '\n数据来源: 真实查询结果'

        return jsonify({
            'success': True,
            'message': message,
            'is_test_data': is_test_data,
            'input_rows': input_rows,
            'input_cols': input_cols,
            'output_rows': len(df),
            'output_cols': len(df.columns),
            'execution_time': execution_time,
            'console_output': console_output
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
