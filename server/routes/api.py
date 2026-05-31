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
from studio.flow.flow_compiler import compile_filter_rules, normalize_strategy, resolve_strategy_python, extract_rules_compile_flow, has_inline_sampling
from studio.flow.flow_schema import prepare_strategy, validate_flow, FLOW_IR_VERSION
from studio.flow.flow_registry import build_node_registry
from studio.query.deployed_models import fetch_deployed_models, fetch_training_models
from studio.query.pipeline_rules import fetch_pipelines, fetch_pipeline_filter_rules, fetch_pipeline_nodes
from studio.query.platform_paths import sync_img_base_path
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
        'updated_at': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M'),
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
        safe_config['api_token_set'] = bool(str(config.get('api_token') or '').strip())
        safe_config['api_token'] = ''
        safe_config['db_password'] = ''

        from studio.config_crypto import secrets_encryption_status
        config_secrets = secrets_encryption_status()

        return jsonify({
            'success': True,
            'config': safe_config,
            'path_checks': path_checks,
            'config_secrets': config_secrets,
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
        config = {**current, **{k: v for k, v in incoming.items() if k not in readonly}}
        if not str(incoming.get('db_password') or '').strip():
            config['db_password'] = current.get('db_password', '')
        if not str(incoming.get('magic_fox_password') or '').strip():
            config['magic_fox_password'] = current.get('magic_fox_password', '')
        if not str(incoming.get('magic_fox_access_token') or '').strip():
            config['magic_fox_access_token'] = current.get('magic_fox_access_token', '')
        if not str(incoming.get('api_token') or '').strip():
            config['api_token'] = current.get('api_token', '')

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
            return jsonify({'success': True, 'message': '配置保存成功', 'warnings': warnings})
        else:
            return jsonify({'success': False, 'error': '保存配置失败'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/api/config/test-connection', methods=['POST'])
def test_connection():
    """测试数据库连接"""
    try:
        data = request.json
        host = data.get('host', '')
        user = data.get('user', '')
        password = data.get('password', '')
        database = data.get('database', '')

        if not str(password).strip():
            password = load_config().get('db_password', '')

        if not all([host, user, database]):
            return jsonify({'success': False, 'error': '请填写主机、用户名和数据库名'}), 400
        
        # 尝试连接
        test_client = MySQLClient(host, user, password, database)
        if test_client.connection:
            test_client.close()
            return jsonify({'success': True, 'message': '数据库连接成功'})
        else:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
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


@api_bp.route('/api/query', methods=['POST'])
def query_database():
    """执行 SQL 查询"""
    try:
        data = request.json
        sql_template = data.get('sql', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        sample_size = parse_sample_size(data.get('sample_size'))
        random_seed = parse_random_seed(data.get('random_seed'))
        templates = _get_all_templates()
        flow = data.get('flow')
        filter_mode = data.get('filter_mode', '')

        try:
            python_code = _resolve_query_python(data, templates)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        
        if not sql_template:
            return jsonify({'success': False, 'error': 'SQL 查询语句不能为空'}), 400
        
        # 替换 SQL 中的时间变量
        sql = sql_template.replace('${START_TIME}', start_time).replace('${END_TIME}', end_time)
        
        # 执行查询
        client = get_db_client()
        df = client.query(sql)
        
        if df is None:
            return jsonify({'success': False, 'error': '查询失败，请检查 SQL 语句和数据库连接'}), 500
        
        if df.empty:
            return jsonify({'success': True, 'data': [], 'count': 0, 'message': '查询结果为空'})

        console_output = ''
        execution_time = 0.0
        input_rows, input_cols = len(df), len(df.columns)
        rows_before_sample = len(df)

        if python_code and python_code.strip():
            try:
                df, console_output, execution_time = execute_python_filter(
                    df, python_code, capture_output=True
                )
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Python 筛选失败: {str(e)}',
                    'traceback': traceback.format_exc(),
                    'console_output': console_output
                }), 500

            if df.empty:
                resp = {'success': True, 'data': [], 'count': 0, 'message': '筛选后结果为空'}
                if console_output:
                    resp['console_output'] = console_output
                    resp['execution_time'] = execution_time
                return jsonify(resp)

        rows_before_sample = len(df)
        flow_payload = flow if flow and flow.get('nodes') else None
        skip_post_sample = has_inline_sampling(python_code, flow_payload)
        if not skip_post_sample:
            df = apply_random_sample(df, sample_size, random_seed)

        query_meta = {
            'query_sql': sql_template,
            'query_sql_executed': sql,
            'python_code': python_code or '',
            'flow': flow_payload,
            'filter_mode': filter_mode or ('flow' if flow_payload else 'code'),
            'start_time': start_time,
            'end_time': end_time,
            'sample_size': sample_size,
            'random_seed': random_seed,
            'rows_before_sample': rows_before_sample,
            'post_sample_skipped': skip_post_sample,
            'query_mode': 'free_query',
            'data_source': data.get('data_source') or 'detail',
        }
        if query_meta['data_source'] == 'predict_result':
            if 'model_name' in df.columns and not df['model_name'].dropna().empty:
                query_meta['model_name'] = str(df['model_name'].dropna().iloc[0])
            if 'job_id' in df.columns and not df['job_id'].dropna().empty:
                try:
                    query_meta['job_id'] = int(df['job_id'].dropna().iloc[0])
                except (TypeError, ValueError):
                    pass

        result_data, task_id = build_query_task(df, query_meta)

        resp = {
            'success': True,
            'data': result_data,
            'count': len(result_data),
            'task_id': task_id,
            'post_sample_skipped': skip_post_sample,
            'sample_size': sample_size,
            'random_seed': random_seed,
            'rows_before_sample': rows_before_sample,
        }
        if python_code and python_code.strip():
            resp['console_output'] = console_output
            resp['execution_time'] = execution_time
            resp['input_rows'] = input_rows
            resp['input_cols'] = input_cols
            resp['output_rows'] = rows_before_sample
            resp['output_cols'] = len(df.columns)
        return jsonify(resp)
    
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
        sample_size = parse_sample_size(data.get('sample_size'))
        preview_mode = data.get('preview_mode', 'rules')  # rules | full

        if not sql_template:
            return jsonify({'success': False, 'error': 'SQL 查询语句不能为空'}), 400

        sql = sql_template.replace('${START_TIME}', start_time).replace('${END_TIME}', end_time)
        client = get_db_client()
        df = client.query(sql)
        if df is None:
            return jsonify({'success': False, 'error': '查询失败'}), 500

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

        if preview_mode == 'full':
            try:
                python_code = _resolve_query_python(data, templates)
            except ValueError as e:
                return jsonify({'success': False, 'error': str(e)}), 400
            if python_code:
                try:
                    df, _, execution_time = execute_python_filter(df, python_code, capture_output=True)
                    filter_rows = len(df)
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Python 筛选失败: {str(e)}',
                        'traceback': traceback.format_exc(),
                    }), 500
        else:
            rules_code = _resolve_filter_rules_code(data, templates)
            if rules_code:
                try:
                    start = time.time()
                    df = execute_filter_rules_only(df, rules_code)
                    execution_time = time.time() - start
                    filter_rows = len(df)
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'规则筛选失败: {str(e)}',
                        'traceback': traceback.format_exc(),
                    }), 500

        flow_payload = data.get('flow') if (data.get('flow') or {}).get('nodes') else None
        python_for_check = ''
        if preview_mode == 'full':
            try:
                python_for_check = _resolve_query_python(data, templates) or ''
            except ValueError:
                python_for_check = (data.get('python_code') or '').strip()
        skip_post_sample = has_inline_sampling(python_for_check, flow_payload)
        if skip_post_sample and preview_mode == 'full':
            after_sample = filter_rows
        else:
            after_sample = min(sample_size, filter_rows) if filter_rows else 0
        unique_products = None
        if 'product_no' in df.columns:
            unique_products = int(df['product_no'].nunique())

        return jsonify({
            'success': True,
            'sql_rows': sql_rows,
            'filter_rows': filter_rows,
            'after_sample': after_sample,
            'sample_size': sample_size,
            'unique_products': unique_products,
            'execution_time': round(execution_time, 3),
            'preview_mode': preview_mode,
            'post_sample_skipped': skip_post_sample,
        })
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
        
        # 获取选中的图片索引（如果提供了）
        selected_indices = None
        if request.method == 'POST':
            data = request.get_json() or {}
            selected_indices = data.get('selected_indices', None)
            if selected_indices is not None:
                selected_indices = set(int(idx) for idx in selected_indices)
        
        # 读取原始CSV数据以获取图片文件名映射
        image_filename_map = {}
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
                for idx, row in df.iterrows():
                    img_path = row.get('img_path', '')
                    if pd.notna(img_path) and img_path:
                        img_name = os.path.basename(str(img_path))
                        image_filename_map[int(idx)] = img_name
            except Exception as e:
                print(f"⚠️ 读取CSV文件警告: {e}")
        
        # 读取COCO数据
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        
        # 如果指定了选中的图片，过滤COCO数据
        if selected_indices is not None and len(selected_indices) > 0:
            # 过滤images
            filtered_images = [img for img in coco_data['images'] if img.get('id') in selected_indices]
            selected_image_ids = {img['id'] for img in filtered_images}
            
            # 过滤annotations（只保留选中图片的标注）
            filtered_annotations = [ann for ann in coco_data['annotations'] if ann.get('image_id') in selected_image_ids]
            
            # 创建新的COCO数据
            filtered_coco = {
                'info': coco_data.get('info') or build_coco_info(),
                'images': filtered_images,
                'annotations': filtered_annotations,
                'categories': coco_data.get('categories', [])
            }
            
            # 临时保存过滤后的COCO文件
            filtered_coco_path = os.path.join(task_dir, '_annotations_filtered.coco.json')
            with open(filtered_coco_path, 'w', encoding='utf-8') as f:
                json.dump(filtered_coco, f, ensure_ascii=False, indent=4)
            coco_path = filtered_coco_path
        
        # 创建临时ZIP文件
        zip_filename = f'coco_export_{task_id}.zip'
        zip_path = os.path.join(current_app.config['UPLOAD_FOLDER'], zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 添加COCO JSON文件
                zipf.write(coco_path, '_annotations.coco.json')
                if os.path.exists(csv_path):
                    zipf.write(csv_path, 'result.csv')
                
                # 添加图片文件
                image_count = 0
                if selected_indices is not None and len(selected_indices) > 0:
                    # 只添加选中的图片
                    for idx in selected_indices:
                        img_name = image_filename_map.get(idx)
                        if img_name:
                            file_path = os.path.join(task_dir, img_name)
                            if os.path.exists(file_path) and os.path.isfile(file_path):
                                zipf.write(file_path, img_name)
                                image_count += 1
                else:
                    # 添加所有图片文件
                    for filename in os.listdir(task_dir):
                        file_path = os.path.join(task_dir, filename)
                        # 只添加图片文件，跳过JSON和CSV文件
                        if os.path.isfile(file_path) and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                            zipf.write(file_path, filename)
                            image_count += 1
            
            # 清理临时过滤的COCO文件
            if selected_indices is not None and os.path.exists(filtered_coco_path):
                try:
                    os.remove(filtered_coco_path)
                except:
                    pass
            
            # 返回ZIP文件
            response = send_file(zip_path, as_attachment=True, download_name=f'coco_export_{task_id}.zip', mimetype='application/zip')
            
            # 延迟删除临时ZIP文件（在响应发送后）
            def remove_file():
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except:
                    pass
            
            # 使用Flask的after_request机制会在响应后清理，但这里我们使用线程延迟删除
            import threading
            timer = threading.Timer(60.0, remove_file)  # 60秒后删除
            timer.start()
            
            return response
        except Exception as zip_error:
            # 如果ZIP创建失败，尝试删除临时文件
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                if selected_indices is not None and os.path.exists(filtered_coco_path):
                    os.remove(filtered_coco_path)
            except:
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


def _load_task_query_meta(task_dir):
    meta_path = os.path.join(task_dir, 'query_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_coco_for_archive(task_dir, selected_indices=None):
    """加载并可选过滤 COCO 数据，返回 (coco_dict, image_names)"""
    csv_path = os.path.join(task_dir, 'result.csv')
    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if not os.path.exists(coco_path):
        return None, []

    with open(coco_path, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)

    if not selected_indices:
        image_names = []
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, encoding='utf-8')
            for idx, row in df.iterrows():
                img_path = row.get('img_path', '')
                if pd.notna(img_path) and img_path:
                    image_names.append(os.path.basename(str(img_path)))
        return coco_data, image_names

    selected_indices = set(int(i) for i in selected_indices)
    filtered_images = [img for img in coco_data.get('images', []) if img.get('id') in selected_indices]
    selected_image_ids = {img['id'] for img in filtered_images}
    filtered_annotations = [
        ann for ann in coco_data.get('annotations', [])
        if ann.get('image_id') in selected_image_ids
    ]
    filtered_coco = {
        'images': filtered_images,
        'annotations': filtered_annotations,
        'categories': coco_data.get('categories', [])
    }
    if 'info' in coco_data:
        filtered_coco['info'] = coco_data['info']

    image_names = []
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, encoding='utf-8')
        for idx in sorted(selected_indices):
            if idx < len(df):
                img_path = df.iloc[idx].get('img_path', '')
                if pd.notna(img_path) and img_path:
                    image_names.append(os.path.basename(str(img_path)))
    return filtered_coco, image_names


def _enrich_coco_archive_info(coco_data, query_meta, archived_at, include_images):
    """在 COCO info 中写入查询 SQL、Python 代码等归档元数据"""
    base = build_coco_info(query_meta)
    info = {**base, **(coco_data.get('info') or {})}
    info.update({
        'description': info.get('description') or f'{PRODUCT_NAME} archive',
        'archived_at': archived_at,
        'include_images': include_images,
    })
    coco_data['info'] = {k: v for k, v in info.items() if v is not None and v != ''}
    return coco_data


@api_bp.route('/api/archive/<task_id>', methods=['POST'])
def archive_results(task_id):
    """将 COCO 标注归档到指定目录，可选复制图片"""
    try:
        data = request.get_json() or {}
        archive_dir = (data.get('archive_dir') or '').strip()
        subfolder = (data.get('subfolder') or '').strip()
        selected_indices = data.get('selected_indices')
        include_images = bool(data.get('include_images', False))

        if not archive_dir:
            archive_dir = load_config().get('archive_base_path', '').strip()
        if not archive_dir:
            return jsonify({'success': False, 'error': '请指定归档目录或在设置中配置 archive_base_path'}), 400

        archive_dir = os.path.abspath(os.path.expanduser(archive_dir))
        if not os.path.isdir(archive_dir):
            try:
                os.makedirs(archive_dir, exist_ok=True)
            except Exception as e:
                return jsonify({'success': False, 'error': f'无法创建归档目录: {e}'}), 400

        task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
        if not os.path.isdir(task_dir):
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        if not subfolder:
            subfolder = f'archive_{task_id[:8]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

        subfolder = re.sub(r'[^\w\-\u4e00-\u9fff]+', '_', subfolder).strip('_') or f'archive_{task_id[:8]}'
        dest_dir = os.path.join(archive_dir, subfolder)
        if os.path.exists(dest_dir):
            return jsonify({'success': False, 'error': f'目标目录已存在: {dest_dir}'}), 400
        os.makedirs(dest_dir, exist_ok=True)

        indices = selected_indices if selected_indices else None
        coco_data, image_names = _load_coco_for_archive(task_dir, indices)
        if not coco_data:
            return jsonify({'success': False, 'error': 'COCO 标注文件不存在'}), 404

        query_meta = _load_task_query_meta(task_dir)
        for key in ('query_sql', 'python_code', 'start_time', 'end_time', 'strategy_id', 'strategy_name', 'sample_size'):
            if data.get(key) is not None and data.get(key) != '':
                query_meta[key] = data.get(key)
        if data.get('query_sql_executed'):
            query_meta['query_sql_executed'] = data['query_sql_executed']

        archived_at = datetime.now().isoformat()
        coco_data = _enrich_coco_archive_info(coco_data, query_meta, archived_at, include_images)

        coco_dest = os.path.join(dest_dir, '_annotations.coco.json')
        with open(coco_dest, 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, ensure_ascii=False, indent=2)
        file_count = 1
        image_count = 0

        if include_images:
            if indices:
                for img_name in image_names:
                    src = os.path.join(task_dir, img_name)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join(dest_dir, img_name))
                        image_count += 1
            else:
                for filename in os.listdir(task_dir):
                    src = os.path.join(task_dir, filename)
                    if os.path.isfile(src) and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                        shutil.copy2(src, os.path.join(dest_dir, filename))
                        image_count += 1
            file_count += image_count

        return jsonify({
            'success': True,
            'path': dest_dir,
            'file_count': file_count,
            'image_count': image_count,
            'include_images': include_images,
            'message': f'已归档 COCO 标注' + (f'及 {image_count} 张图片' if include_images else '')
        })
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

STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies')
TEMPLATES_DIR = os.path.join(STRATEGIES_DIR, 'templates')

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
    """删除对应 id 的 JSON 文件（递归搜索）"""
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith('.json'):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r') as f:
                        if json.load(f).get('id') == item_id:
                            os.remove(fpath)
                            return True
                except Exception:
                    pass
    return False

def _load_templates_raw():
    return _load_json_dir(TEMPLATES_DIR)


def _get_all_templates():
    raw = _load_templates_raw()
    bundle = get_defect_categories_bundle()
    return apply_categories_to_templates(raw, bundle.get('categories'))

def _get_all_strategies():
    items = {}
    if not os.path.isdir(STRATEGIES_DIR):
        return items
    for entry in os.listdir(STRATEGIES_DIR):
        epath = os.path.join(STRATEGIES_DIR, entry)
        if os.path.isdir(epath) and entry == 'templates':
            continue  # 跳过模板目录
        if os.path.isdir(epath):
            for root, _, files in os.walk(epath):
                for fname in files:
                    if fname.endswith('.json'):
                        try:
                            with open(os.path.join(root, fname), 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if 'id' in data:
                                    items[data['id']] = data
                        except Exception as e:
                            print(f"⚠️ 加载策略失败: {fname}: {e}")
        elif entry.endswith('.json'):
            try:
                with open(epath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'id' in data:
                        items[data['id']] = data
            except Exception as e:
                print(f"⚠️ 加载策略失败: {entry}: {e}")
    return items

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
        builtin_dir = os.path.join(TEMPLATES_DIR, '_builtin')
        filepath = os.path.join(builtin_dir if data.get('_builtin') else TEMPLATES_DIR, f"{tpl_id}.json")
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

@api_bp.route('/api/strategies', methods=['POST'])
def save_strategy():
    try:
        data = request.json
        sid = data.get('id', '').strip()
        if not sid:
            return jsonify({'success': False, 'error': 'id 不能为空'}), 400
        data['updated_at'] = datetime.now().isoformat()
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
        builtin_dir = os.path.join(STRATEGIES_DIR, '_builtin')
        filepath = os.path.join(builtin_dir if data.get('_builtin') else STRATEGIES_DIR, f"{sid}.json")
        _save_json(filepath, data)
        return jsonify({'success': True, 'id': sid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/strategies/<strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    try:
        if _delete_json(STRATEGIES_DIR, strategy_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '策略不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── 策略执行引擎 ────────────────────────────────────────────────

@api_bp.route('/api/strategies/execute', methods=['POST'])
def execute_strategy():
    try:
        data = request.json
        strategy_id = data.get('strategy_id', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')

        strategies = _get_all_strategies()
        strategy = strategies.get(strategy_id)
        if not strategy:
            return jsonify({'success': False, 'error': '策略不存在'}), 404

        all_templates = _get_all_templates()
        strategy = normalize_strategy(dict(strategy), all_templates)

        sql = strategy.get('sql_template', '')
        if not sql:
            return jsonify({'success': False, 'error': '策略无 SQL 模板'}), 400

        sql = sql.replace('${START_TIME}', start_time).replace('${END_TIME}', end_time)

        client = get_db_client()
        df = client.query(sql)
        if df is None:
            return jsonify({'success': False, 'error': '数据库查询失败'}), 500
        if df.empty:
            return jsonify({'success': True, 'data': [], 'count': 0})

        input_rows, input_cols = len(df), len(df.columns)
        python_code = ''
        console_output = ''
        execution_time = 0.0
        try:
            python_code, exec_mode = resolve_strategy_python(strategy, all_templates)
            if python_code:
                df, console_output, execution_time = execute_python_filter(
                    df, python_code, capture_output=True,
                )
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

        if df.empty:
            return jsonify({'success': True, 'data': [], 'count': 0})

        sample_size = parse_sample_size(
            data.get('sample_size', strategy.get('sample_size'))
        )
        random_seed = parse_random_seed(data.get('random_seed'))
        rows_before_sample = len(df)
        skip_post_sample = has_inline_sampling(python_code, strategy.get('flow'))
        if not skip_post_sample:
            df = apply_random_sample(df, sample_size, random_seed)

        result_data, task_id = build_query_task(df, {
            'query_sql': strategy.get('sql_template', ''),
            'query_sql_executed': sql,
            'python_code': python_code if python_code else strategy.get('python_code', ''),
            'flow': strategy.get('flow'),
            'filter_mode': strategy.get('filter_mode', ''),
            'start_time': start_time,
            'end_time': end_time,
            'strategy_id': strategy_id,
            'strategy_name': strategy.get('name', ''),
            'sample_size': sample_size,
            'random_seed': random_seed,
            'rows_before_sample': rows_before_sample,
            'query_mode': exec_mode if python_code else 'strategy',
        })

        return jsonify({
            'success': True,
            'data': result_data,
            'count': len(result_data),
            'task_id': task_id,
            'sample_size': sample_size,
            'random_seed': random_seed,
            'rows_before_sample': rows_before_sample,
            'post_sample_skipped': skip_post_sample,
            'input_rows': input_rows,
            'input_cols': input_cols,
            'output_rows': rows_before_sample,
            'filter_mode': strategy.get('filter_mode', ''),
            'console_output': console_output or None,
            'execution_time': execution_time or None,
        })
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
