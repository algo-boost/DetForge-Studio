"""DetForge 模型预测 / 作业 / 人工质检 路由（写库 detforge）。"""
import os
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file

from studio.forge import forge_db
from studio.forge import forge_service
from studio.forge import forge_manual_qc
from studio.forge import forge_predict
from studio.forge import forge_paths

forge_bp = Blueprint('forge', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANUAL_QC_UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads', 'manual_qc')
_ALLOWED_IMG_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif'}
_MAX_UPLOAD_FILES = 500  # 单次上传张数上限


def _err(e, code=500):
    return jsonify({'success': False, 'error': str(e)}), code


# ── Schema ─────────────────────────────────────────────────────────

@forge_bp.route('/api/forge/schema/status', methods=['GET'])
def schema_status():
    try:
        return jsonify({
            'success': True,
            'database': forge_db.forge_db_name(),
            'ready': forge_db.schema_ready(),
        })
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/schema/init', methods=['POST'])
def schema_init():
    try:
        count = forge_db.ensure_schema()
        return jsonify({'success': True, 'database': forge_db.forge_db_name(), 'statements': count})
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ── 模型注册 ───────────────────────────────────────────────────────

@forge_bp.route('/api/forge/models', methods=['GET'])
def list_models():
    try:
        enabled_only = request.args.get('enabled') == '1'
        return jsonify({'success': True, 'data': forge_db.list_models(enabled_only=enabled_only)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/models', methods=['POST'])
def create_model():
    try:
        model_id = forge_service.import_model(request.json or {})
        return jsonify({'success': True, 'id': model_id, 'data': forge_db.get_model(model_id)})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    try:
        forge_db.delete_model(model_id)
        return jsonify({'success': True})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/models/<int:model_id>/health', methods=['POST'])
def model_health(model_id):
    """加载健康检查：尝试加载权重再释放（需要 torch/hq_det 环境）。"""
    try:
        model = forge_db.get_model(model_id)
        if not model:
            return jsonify({'success': False, 'error': '模型不存在'}), 404
        device = (request.json or {}).get('device')
        info = forge_predict.health_check_model(model, device=device)
        return jsonify({'success': True, **info})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/models/<int:model_id>/enabled', methods=['POST'])
def set_model_enabled(model_id):
    try:
        enabled = bool((request.json or {}).get('enabled', True))
        forge_db.set_model_enabled(model_id, enabled)
        return jsonify({'success': True})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/platform/models/import-all', methods=['POST'])
def import_all_platform_models():
    """批量导入本地总控部署/训练模型到注册表。"""
    try:
        data = request.json or {}
        approach_id = data.get('approach_id')
        deploy_approach_id = data.get('deploy_approach_id')
        train_approach_id = data.get('train_approach_id')
        if not any([approach_id, deploy_approach_id, train_approach_id]):
            from server.core import load_config
            from studio.query.approach_context import resolve_local_approach_id
            deploy_approach_id = resolve_local_approach_id(load_config())
        result = forge_service.import_all_platform_models(
            approach_id=int(approach_id) if approach_id else None,
            deploy_approach_id=int(deploy_approach_id) if deploy_approach_id else None,
            train_approach_id=int(train_approach_id) if train_approach_id else None,
            include_deploy=bool(data.get('include_deploy', True)),
            include_train=bool(data.get('include_train', True)),
            limit=int(data.get('limit') or 200),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ── 作业 ───────────────────────────────────────────────────────────

@forge_bp.route('/api/forge/jobs', methods=['GET'])
def list_jobs():
    try:
        status = request.args.get('status')
        job_type = request.args.get('job_type')
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        kw = dict(status=status, job_type=job_type)
        data = forge_db.list_jobs(limit=limit, offset=offset, **kw)
        total = forge_db.count_jobs(**kw)
        return jsonify({'success': True, 'data': data, 'total': total, 'offset': offset, 'limit': limit})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/exports/download', methods=['GET'])
def export_file_download():
    """下载 exports/ 下的文件（ZIP 等）。"""
    try:
        rel = (request.args.get('path') or '').strip()
        if not rel:
            return jsonify({'success': False, 'error': '缺少 path'}), 400
        base = os.path.join(forge_paths.BASE_DIR, 'exports')
        full = os.path.abspath(os.path.join(base, rel.lstrip('/\\')))
        if not forge_paths.is_within(full, [base]) or not os.path.isfile(full):
            return jsonify({'success': False, 'error': '文件不存在或路径非法'}), 404
        return send_file(full, as_attachment=True, download_name=os.path.basename(full))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    try:
        job = forge_db.get_job(job_id)
        if not job:
            return jsonify({'success': False, 'error': '作业不存在'}), 404
        return jsonify({'success': True, 'data': job})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>/log', methods=['GET'])
def get_job_log(job_id):
    try:
        from studio.forge import job_log
        lines = job_log.read_tail(job_id)
        return jsonify({'success': True, 'lines': lines})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/predict', methods=['POST'])
def enqueue_predict():
    try:
        data = request.json or {}
        model_ids = data.get('model_ids')
        deploy_model_ids = data.get('deploy_model_ids')
        train_model_ids = data.get('train_model_ids')
        if model_ids or deploy_model_ids or train_model_ids:
            result = forge_service.enqueue_predict_jobs_batch(
                model_ids=model_ids,
                deploy_model_ids=deploy_model_ids,
                train_model_ids=train_model_ids,
                image_source=data.get('image_source') or {},
                sync_dataset_id=data.get('sync_dataset_id'),
                name_prefix=data.get('name_prefix'),
                threshold=data.get('threshold'),
                device=data.get('device'),
                max_size=data.get('max_size'),
                intra_concurrency=data.get('intra_concurrency', 1),
                priority=data.get('priority', 100),
                platform_project_id=data.get('platform_project_id'),
            )
            return jsonify({'success': True, **result})
        result = forge_service.enqueue_predict_job(
            model_id=data.get('model_id'),
            name=data.get('name'),
            image_source=data.get('image_source') or {},
            threshold=data.get('threshold'),
            device=data.get('device'),
            max_size=data.get('max_size'),
            intra_concurrency=data.get('intra_concurrency', 1),
            priority=data.get('priority', 100),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/predict/batch', methods=['POST'])
def enqueue_predict_batch():
    try:
        data = request.json or {}
        result = forge_service.enqueue_predict_jobs_batch(
            model_ids=data.get('model_ids'),
            deploy_model_ids=data.get('deploy_model_ids'),
            train_model_ids=data.get('train_model_ids'),
            image_source=data.get('image_source') or {},
            sync_dataset_id=data.get('sync_dataset_id'),
            name_prefix=data.get('name_prefix'),
            threshold=data.get('threshold'),
            device=data.get('device'),
            max_size=data.get('max_size'),
            intra_concurrency=data.get('intra_concurrency', 1),
            priority=data.get('priority', 100),
            platform_project_id=data.get('platform_project_id'),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>/control', methods=['POST'])
def control_job(job_id):
    try:
        action = (request.json or {}).get('action')
        if action not in ('pause', 'resume', 'cancel', 'retry'):
            return jsonify({'success': False, 'error': '无效 action'}), 400
        new_status = forge_db.job_control(job_id, action)
        if new_status is None:
            return jsonify({'success': False, 'error': '作业不存在'}), 404
        return jsonify({'success': True, 'status': new_status})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>/items', methods=['GET'])
def job_items(job_id):
    try:
        status = request.args.get('status') or None
        limit = request.args.get('limit', default=200, type=int)
        return jsonify({'success': True, 'data': forge_db.list_job_items(job_id, status=status, limit=limit)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>/results', methods=['GET'])
def job_results(job_id):
    try:
        limit = request.args.get('limit', default=200, type=int)
        offset = request.args.get('offset', default=0, type=int)
        filters = {}
        for key in ('min_box_count', 'only_with_boxes', 'q', 'product_no', 'sort'):
            val = request.args.get(key)
            if val is not None and val != '':
                filters[key] = val
        if request.args.get('only_with_boxes') in ('1', 'true', 'yes'):
            filters['only_with_boxes'] = True
        for fkey in ('min_max_score', 'max_max_score'):
            val = request.args.get(fkey, type=float)
            if val is not None:
                filters[fkey] = val
        result_ids = request.args.get('result_ids')
        ids = None
        if result_ids:
            ids = [int(x) for x in str(result_ids).split(',') if x.strip().isdigit()]
        data = forge_db.list_predict_results(
            job_id, limit=limit, offset=offset, filters=filters or None, result_ids=ids,
        )
        total = forge_db.count_predict_results(job_id, filters=filters or None, result_ids=ids)
        return jsonify({'success': True, 'data': data, 'total': total})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/jobs/<int:job_id>/viz', methods=['POST'])
def job_open_viz(job_id):
    """将预测作业结果导出为 COCO 并打开样本图库。"""
    try:
        from studio.forge.predict_job_viz import open_predict_job_viz
        data = request.json or {}
        filters = data.get('filters') or {}
        result_ids = data.get('result_ids')
        result = open_predict_job_viz(
            job_id,
            filters=filters,
            result_ids=result_ids,
            dataset_name=data.get('dataset_name'),
        )
        return jsonify({'success': True, **result})
    except FileNotFoundError as e:
        return _err(e, 404)
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/predict-result/<int:result_id>/preview', methods=['GET'])
def predict_result_preview(result_id):
    """渲染预测结果带框预览图（从 ext.original_predictions 画框）。"""
    try:
        import io
        from PIL import Image, ImageDraw
        row = forge_db.get_predict_result(result_id)
        if not row:
            return jsonify({'success': False, 'error': '结果不存在'}), 404
        img_path = str(row.get('img_path') or '').strip()
        if not img_path or not os.path.isfile(img_path):
            return jsonify({'success': False, 'error': '原图不可用'}), 404
        if not forge_paths.safe_read_path(img_path):
            return jsonify({'success': False, 'error': '原图路径不在允许范围内'}), 403
        img = Image.open(img_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        preds = ((row.get('ext') or {}).get('original_predictions')) or []
        for p in preds:
            for pt in (p.get('points') or []):
                x, y, w, h = pt.get('x', 0), pt.get('y', 0), pt.get('w', 0), pt.get('h', 0)
                draw.rectangle([x, y, x + w, y + h], outline=(255, 64, 64), width=3)
                label = f"{p.get('name', '')} {float(p.get('confidence', 0)):.2f}"
                draw.text((x + 2, max(0, y - 12)), label, fill=(255, 64, 64))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/predict-result/source', methods=['GET'])
def predict_result_source():
    """供查询页「数据源=预测结果表」使用的限定表名与默认 SQL。"""
    try:
        table = forge_db.predict_result_select_sql()
        return jsonify({
            'success': True,
            'table': table,
            'default_sql': f"SELECT * FROM {table}",
        })
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ── 人工质检归档 ───────────────────────────────────────────────────

@forge_bp.route('/api/forge/manual-qc/lookup', methods=['GET'])
def manual_qc_lookup():
    try:
        sn = request.args.get('sn', '')
        limit = request.args.get('limit', default=50, type=int)
        records = forge_manual_qc.find_platform_records_by_sn(sn, limit=limit)
        return jsonify({'success': True, 'sn': sn, 'count': len(records), 'records': records})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/categories', methods=['GET'])
def manual_qc_categories():
    try:
        return jsonify({'success': True, **forge_manual_qc.get_categories()})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/summary', methods=['GET'])
def manual_qc_summary():
    """归档库概览：条数统计、当日批次、交接收件箱路径。"""
    try:
        return jsonify({'success': True, **forge_manual_qc.get_workflow_summary()})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/batches', methods=['GET'])
def manual_qc_batches():
    """按日/批次汇总归档记录。"""
    try:
        limit = min(int(request.args.get('limit', 60)), 200)
        data = forge_manual_qc.list_batch_groups(limit=limit)
        return jsonify({'success': True, 'data': data, 'daily_batch_id': forge_manual_qc.default_daily_batch_id()})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/categories', methods=['POST'])
def manual_qc_save_categories():
    try:
        data = request.json or {}
        result = forge_manual_qc.save_categories(
            imaging_categories=data.get('imaging_categories'),
            defect_types=data.get('defect_types'),
            defect_strict=data.get('defect_strict'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/export', methods=['POST'])
def manual_qc_export():
    """按时段 + 类别导出图片。

    - async=true：放后台作业（大批量）；
    - as_zip=true：打包并直接下载 zip；
    - 否则：同步拷贝到服务器目录并返回摘要。
    """
    try:
        data = request.json or {}
        export_params = {
            'start': data.get('start') or None,
            'end': data.get('end') or None,
            'categories': data.get('categories') or None,
            'defect_types': data.get('defect_types') or None,
            'out_dir': (data.get('out_dir') or '').strip() or None,
            'include': data.get('include') or 'both',
        }
        if data.get('async'):
            res = forge_service.enqueue_export_job(export_params, name=data.get('name'))
            return jsonify({'success': True, 'mode': 'async', **res})
        if data.get('as_zip'):
            result = forge_manual_qc.export_records(**export_params, as_zip=True)
            zip_path = result.get('zip_path')
            if not zip_path or not os.path.exists(zip_path):
                return jsonify({'success': False, 'error': '没有可导出的图片'}), 400
            return send_file(zip_path, as_attachment=True,
                             download_name=os.path.basename(zip_path), mimetype='application/zip')
        result = forge_manual_qc.export_records(**export_params)
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/cleanup-uploads', methods=['POST'])
def manual_qc_cleanup_uploads():
    try:
        dry_run = bool((request.json or {}).get('dry_run', True))
        return jsonify({'success': True, **forge_manual_qc.cleanup_orphan_uploads(dry_run=dry_run)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/upload', methods=['POST'])
def manual_qc_upload():
    """拖拽/选择客户图上传，存到 uploads/manual_qc/<日期>/，返回服务器绝对路径供归档。"""
    try:
        files = request.files.getlist('files') or request.files.getlist('files[]')
        files = [f for f in files if f and f.filename]
        if not files:
            return jsonify({'success': False, 'error': '未收到图片文件'}), 400
        if len(files) > _MAX_UPLOAD_FILES:
            return jsonify({'success': False, 'error': f'单次最多上传 {_MAX_UPLOAD_FILES} 张'}), 400
        day_dir = os.path.join(MANUAL_QC_UPLOAD_DIR, datetime.now().strftime('%Y%m%d'))
        os.makedirs(day_dir, exist_ok=True)
        saved = []
        for f in files:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in _ALLOWED_IMG_EXT:
                continue
            stored = f"{uuid.uuid4().hex[:12]}{ext}"
            abs_path = os.path.join(day_dir, stored)
            f.save(abs_path)
            saved.append({'name': f.filename, 'path': abs_path})
        if not saved:
            return jsonify({'success': False, 'error': '没有有效图片（仅支持 jpg/png/bmp/webp/gif）'}), 400
        return jsonify({'success': True, 'data': saved})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc', methods=['GET'])
def manual_qc_list():
    try:
        cats = request.args.getlist('category') or None
        defects = request.args.getlist('defect_type') or None
        kw = dict(
            batch_id=request.args.get('batch_id'),
            product_no=request.args.get('product_no'),
            start=request.args.get('start') or None,
            end=request.args.get('end') or None,
            categories=cats,
            defect_types=defects,
            match_status=request.args.get('match_status') or None,
            training_status=request.args.get('training_status') or None,
        )
        limit = request.args.get('limit', default=200, type=int)
        offset = request.args.get('offset', default=0, type=int)
        data = forge_db.list_manual_qc(limit=limit, offset=offset, **kw)
        total = forge_db.count_manual_qc(**kw)
        return jsonify({'success': True, 'data': data, 'total': total, 'offset': offset, 'limit': limit})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/<int:qc_id>', methods=['PATCH', 'PUT'])
def manual_qc_update(qc_id):
    try:
        n = forge_db.update_manual_qc(qc_id, request.json or {})
        return jsonify({'success': True, 'updated': n, 'data': forge_db.get_manual_qc(qc_id)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/<int:qc_id>', methods=['DELETE'])
def manual_qc_delete(qc_id):
    try:
        return jsonify({'success': True, 'deleted': forge_db.delete_manual_qc(qc_id)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc', methods=['POST'])
def manual_qc_archive():
    """单条或批量归档。body: {entry:{...}} 或 {entries:[...], batch_id}。"""
    try:
        data = request.json or {}
        if data.get('entries'):
            result = forge_manual_qc.archive_batch(data['entries'], batch_id=data.get('batch_id'))
            return jsonify({'success': True, **result})
        entry = data.get('entry') or data
        res = forge_manual_qc.archive_one(
            product_no=entry.get('product_no'),
            customer_img_path=entry.get('customer_img_path'),
            batch_id=entry.get('batch_id'),
            note=entry.get('note'),
            position=entry.get('position'),
            defect_type=entry.get('defect_type'),
            qc_category=entry.get('qc_category'),
            matched_detail_id=entry.get('matched_detail_id'),
            no_match=bool(entry.get('no_match')),
            force=bool(entry.get('force')),
        )
        return jsonify({'success': True, 'result': res})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ── 数据集同步（Magic-Fox） ────────────────────────────────────────

@forge_bp.route('/api/forge/sync/test-auth', methods=['POST'])
def sync_test_auth():
    try:
        from studio.sync import magic_fox_bridge
        magic_fox_bridge.test_connection()
        status = magic_fox_bridge.auth_status()
        return jsonify({'success': True, 'connected': True, 'auth': status})
    except Exception as e:  # noqa: BLE001
        return _err(e, 400)


@forge_bp.route('/api/forge/sync/discover', methods=['POST'])
def sync_discover():
    """从 Magic-Fox URL 发现数据集与训练快照。"""
    try:
        from studio.sync import magic_fox_discover
        data = request.json or {}
        result = magic_fox_discover.discover_resources(
            url=data.get('url'),
            approach_id=data.get('approach_id'),
            subject_id=data.get('subject_id'),
            include_datasets=data.get('include_datasets', True),
            include_snapshots=data.get('include_snapshots', True),
            dataset_ids=data.get('dataset_ids'),
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e, 400)


@forge_bp.route('/api/forge/sync/discover/import', methods=['POST'])
def sync_discover_import():
    """将发现结果批量导入 sync 项目。"""
    try:
        from studio.sync import magic_fox_discover
        data = request.json or {}
        items = data.get('items') or []
        result = magic_fox_discover.import_discovered_items(
            items,
            project_id=data.get('project_id'),
            project_name=data.get('project_name'),
            approach_id=data.get('approach_id'),
            subject_id=data.get('subject_id'),
            training_page_url=data.get('training_page_url'),
            local_root=data.get('local_root'),
            write_db=bool(data.get('write_db', True)),
            strip_prefix=data.get('strip_prefix', True),
            split_subdirs=bool(data.get('split_subdirs')),
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/projects', methods=['GET'])
def sync_list_projects():
    try:
        enabled = request.args.get('enabled') == '1'
        return jsonify({'success': True, 'data': forge_db.list_sync_projects(enabled_only=enabled)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/projects', methods=['POST'])
def sync_save_project():
    try:
        pid = forge_db.upsert_sync_project(request.json or {})
        return jsonify({'success': True, 'id': pid, 'data': forge_db.get_sync_project(pid)})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/projects/<int:project_id>', methods=['DELETE'])
def sync_delete_project(project_id):
    try:
        return jsonify({'success': True, 'deleted': forge_db.delete_sync_project(project_id)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets', methods=['GET'])
def sync_list_datasets():
    try:
        project_id = request.args.get('project_id')
        enabled = request.args.get('enabled') == '1'
        data = forge_db.list_sync_datasets(
            project_id=int(project_id) if project_id else None,
            enabled_only=enabled,
        )
        return jsonify({'success': True, 'data': data})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets', methods=['POST'])
def sync_save_dataset():
    try:
        payload = request.json or {}
        local_dir = str(payload.get('local_dir') or '').strip()
        if local_dir:
            project = forge_db.get_sync_project(payload.get('project_id'))
            if project:
                from studio.sync.forge_sync import resolve_dataset_output_dir
                resolve_dataset_output_dir(project, payload)
        did = forge_db.upsert_sync_dataset(payload)
        return jsonify({'success': True, 'id': did, 'data': forge_db.get_sync_dataset(did)})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>', methods=['DELETE'])
def sync_delete_dataset(dataset_id):
    try:
        return jsonify({'success': True, 'deleted': forge_db.delete_sync_dataset(dataset_id)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>/status', methods=['GET'])
def sync_dataset_status(dataset_id):
    try:
        from studio.sync.forge_sync import preview_sync_status
        return jsonify({'success': True, 'data': preview_sync_status(dataset_id)})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>/run', methods=['POST'])
def sync_dataset_run(dataset_id):
    try:
        async_mode = (request.json or {}).get('async', True)
        if async_mode:
            result = forge_service.enqueue_dataset_sync(dataset_id)
            return jsonify({'success': True, **result})
        from studio.sync.forge_sync import sync_dataset
        summary = sync_dataset(int(dataset_id))
        return jsonify({'success': True, 'sync': summary})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>/viz', methods=['POST'])
def sync_dataset_viz(dataset_id):
    """打开已同步数据集的 COCO 样本图库。"""
    try:
        from studio.sync.forge_sync import open_sync_dataset
        result = open_sync_dataset(int(dataset_id))
        return jsonify({'success': True, **result})
    except FileNotFoundError as e:
        return _err(e, 404)
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/train-models', methods=['GET'])
def sync_list_train_models():
    try:
        project_id = request.args.get('project_id', type=int)
        if not project_id:
            return _err('缺少 project_id', 400)
        from studio.sync import platform_models
        return jsonify({'success': True, **platform_models.list_project_train_models(project_id)})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/train-models', methods=['POST'])
def sync_train_models():
    try:
        data = request.json or {}
        project_id = data.get('project_id')
        if not project_id:
            return _err('缺少 project_id', 400)
        from studio.sync import platform_models
        result = platform_models.sync_project_train_models(
            int(project_id), force=bool(data.get('force')),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>/items', methods=['GET'])
def sync_dataset_items(dataset_id):
    try:
        limit = int(request.args.get('limit') or 50)
        offset = int(request.args.get('offset') or 0)
        filters = {
            'q': request.args.get('q'),
            'product_no': request.args.get('product_no') or request.args.get('sn'),
            'product_type': request.args.get('product_type'),
            'trace_status': request.args.get('trace_status'),
            'start': request.args.get('start'),
            'end': request.args.get('end'),
        }
        items = forge_db.list_dataset_items(dataset_id, limit=limit, offset=offset, filters=filters)
        total = forge_db.count_dataset_items(dataset_id, filters=filters)
        trace_summary = forge_db.dataset_item_trace_summary(dataset_id)
        from server.core import load_config, DEFAULT_CONFIG
        cfg = load_config()
        base = str(cfg.get('img_base_path') or DEFAULT_CONFIG['img_base_path'] or '').strip()
        if base and not base.endswith(('/', '\\')):
            base += '/'
        for row in items:
            ok = row.get('object_key')
            row['platform_img_path'] = (base + str(ok)) if ok and base else None
        return jsonify({
            'success': True,
            'data': items,
            'total': total,
            'trace_summary': trace_summary,
        })
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/sync/datasets/<int:dataset_id>/retrace', methods=['POST'])
def sync_dataset_retrace(dataset_id):
    """对已同步样本重新执行 vision_backend 联合溯源。"""
    try:
        dataset = forge_db.get_sync_dataset(dataset_id)
        if not dataset:
            return _err('数据集不存在', 404)
        if not dataset.get('write_db'):
            return _err('该数据集未开启「标注写入数据库」，无法溯源', 400)
        from studio.sync import dataset_provenance
        result = dataset_provenance.retrace_dataset_items(int(dataset_id))
        return jsonify({'success': True, **result})
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ── 筛选批次（捞图 → 外部筛选 → 归档）────────────────────────────

@forge_bp.route('/api/forge/curation', methods=['GET'])
def curation_list():
    try:
        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
        data = forge_db.list_curation_batches(status=status or None, limit=limit, offset=offset)
        total = forge_db.count_curation_batches(status=status or None)
        return jsonify({'success': True, 'data': data, 'total': total})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-eval/preview', methods=['GET', 'POST'])
def replay_eval_preview():
    try:
        from studio.curation import replay_eval_service
        if request.method == 'POST':
            body = request.json or {}
            job_id = body.get('job_id')
        else:
            body = {
                'filter_mode': request.args.get('filter_mode'),
                'min_max_score': request.args.get('min_max_score'),
                'max_max_score': request.args.get('max_max_score'),
                'product_type': request.args.get('product_type'),
                'product_no': request.args.get('product_no'),
            }
            job_id = request.args.get('job_id', type=int)
        if not job_id:
            return _err('缺少 job_id', 400)
        data = replay_eval_service.preview(int(job_id), body=body)
        return jsonify({'success': True, **data})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-eval/create', methods=['POST'])
def replay_eval_create():
    try:
        from studio.curation import replay_eval_service
        body = request.json or {}
        job_id = body.get('job_id')
        if not job_id:
            return _err('缺少 job_id', 400)
        result = replay_eval_service.create_replay_batch(
            int(job_id),
            body=body,
            reviewer=body.get('reviewer'),
            note=body.get('note'),
            limit=body.get('limit') or 50000,
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except RuntimeError as e:
        return _err(e, 503)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-runs/variables', methods=['GET', 'POST'])
def replay_runs_variables():
    try:
        from studio.curation import replay_run_service
        body = request.json if request.method == 'POST' else {}
        if request.method == 'GET':
            body = {
                'stage1': {'strategy_id': request.args.get('stage1_id')},
                'stage2': {'strategy_id': request.args.get('stage2_id')},
                'time_window': {'preset': request.args.get('preset') or 'yesterday'},
                'predict': {'threshold': request.args.get('threshold', type=float)},
            }
        data = replay_run_service.describe_workflow_variables(body)
        return jsonify({'success': True, **data})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-runs/preview', methods=['POST'])
def replay_runs_preview():
    try:
        from studio.curation import replay_run_service
        body = request.json or {}
        data = replay_run_service.preview(body)
        return jsonify({'success': True, **data})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-runs', methods=['GET'])
def replay_runs_list():
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        data = forge_db.list_replay_runs(limit=limit, offset=offset)
        return jsonify({'success': True, 'data': data, 'total': len(data)})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-runs', methods=['POST'])
def replay_runs_create():
    try:
        from studio.curation import replay_run_service
        from flask import current_app
        body = request.json or {}
        run = replay_run_service.start_run(body, app=current_app._get_current_object())
        return jsonify({'success': True, 'data': run})
    except ValueError as e:
        return _err(e, 400)
    except RuntimeError as e:
        return _err(e, 503)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/replay-runs/<int:run_id>', methods=['GET'])
def replay_runs_get(run_id):
    try:
        from studio.curation import replay_run_service
        run = replay_run_service.get_run(run_id)
        return jsonify({'success': True, 'data': run})
    except ValueError as e:
        return _err(e, 404)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation', methods=['POST'])
def curation_create():
    try:
        from studio.curation import curation_service
        body = request.json or {}
        task_id = (body.get('task_id') or '').strip()
        if not task_id:
            return _err('缺少 task_id', 400)
        batch = curation_service.create_from_task(
            task_id,
            strategy_id=body.get('strategy_id'),
            strategy_name=body.get('strategy_name'),
            reviewer=body.get('reviewer'),
            note=body.get('note'),
            data_source=body.get('data_source'),
            intent_type=body.get('intent_type'),
        )
        return jsonify({'success': True, 'data': batch})
    except ValueError as e:
        return _err(e, 400)
    except RuntimeError as e:
        return _err(e, 503)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>', methods=['GET'])
def curation_get(batch_id):
    try:
        batch = forge_db.get_curation_batch(batch_id)
        if not batch:
            return _err('批次不存在', 404)
        return jsonify({'success': True, 'data': batch})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>', methods=['DELETE'])
def curation_delete(batch_id):
    try:
        from studio.curation import curation_service
        result = curation_service.delete_batch(batch_id)
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 404)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/items', methods=['GET'])
def curation_items(batch_id):
    try:
        decision = request.args.get('decision')
        limit = min(int(request.args.get('limit', 500)), 5000)
        offset = int(request.args.get('offset', 0))
        items = forge_db.list_curation_items(batch_id, decision=decision or None, limit=limit, offset=offset)
        total = forge_db.count_curation_items(batch_id, decision=decision or None)
        return jsonify({'success': True, 'data': items, 'total': total})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/export', methods=['POST'])
def curation_export(batch_id):
    try:
        from studio.curation import curation_service
        body = request.json or {}
        result = curation_service.export_batch(
            batch_id, include_images=body.get('include_images', True),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/import', methods=['POST'])
def curation_import(batch_id):
    try:
        from studio.curation import curation_service
        file_text = None
        filename = ''
        if request.files and 'file' in request.files:
            f = request.files['file']
            file_text = f.read().decode('utf-8-sig', errors='replace')
            filename = f.filename or ''
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            file_text = body.get('coco_json') or body.get('csv_text') or body.get('manifest')
            filename = body.get('filename') or ('.json' if body.get('coco_json') else '.csv')
        if not file_text:
            return _err('请上传 _annotations.coco.json 或提供 coco_json', 400)
        result = curation_service.import_filter_result(batch_id, file_text, filename=filename)
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/archive', methods=['POST'])
def curation_archive(batch_id):
    try:
        from studio.curation import curation_service
        body = request.json or {}
        result = curation_service.archive_batch(
            batch_id,
            archive_dir=body.get('archive_dir'),
            copy_images=body.get('copy_images', True),
            treat_pending_as=body.get('treat_pending_as', 'reject'),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/handoff', methods=['POST'])
def curation_handoff(batch_id):
    try:
        from studio.curation import curation_service
        body = request.json or {}
        result = curation_service.generate_handoff(
            batch_id, handoff_note=body.get('note'), split=body.get('split', 'both'),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/handoff-done', methods=['POST'])
def curation_handoff_done(batch_id):
    try:
        from studio.curation import curation_service
        body = request.json or {}
        batch = curation_service.mark_handoff_done(
            batch_id,
            sync_dataset_id=body.get('sync_dataset_id'),
            note=body.get('note'),
        )
        return jsonify({'success': True, 'data': batch})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/curation/<int:batch_id>/download', methods=['GET'])
def curation_download(batch_id):
    """下载出站包 ZIP。"""
    import shutil
    try:
        batch = forge_db.get_curation_batch(batch_id)
        if not batch:
            return _err('批次不存在', 404)
        out_dir = batch.get('export_dir')
        if not out_dir or not os.path.isdir(out_dir):
            return _err('请先执行「生成出站包」', 400)
        zip_base = out_dir.rstrip('/\\')
        zip_path = shutil.make_archive(zip_base, 'zip', root_dir=out_dir)
        return send_file(zip_path, as_attachment=True, download_name=f"{batch['batch_code']}.zip")
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/archive-handoff', methods=['GET'])
def archive_handoff_list():
    """统一筛选归档视图：批次列表 + 人工质检汇总。"""
    try:
        from studio.curation import curation_service
        limit = min(int(request.args.get('limit', 50)), 200)
        data = curation_service.list_archive_handoff(limit=limit)
        return jsonify({'success': True, **data})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@forge_bp.route('/api/forge/manual-qc/handoff', methods=['POST'])
def manual_qc_handoff():
    """人工质检 → 标准训练交接包。"""
    try:
        body = request.json or {}
        result = forge_manual_qc.generate_training_handoff(
            start=body.get('start'),
            end=body.get('end'),
            categories=body.get('categories'),
            batch_id=body.get('batch_id'),
            training_status=body.get('training_status', 'pending'),
            note=body.get('note'),
        )
        return jsonify({'success': True, **result})
    except ValueError as e:
        return _err(e, 400)
    except Exception as e:  # noqa: BLE001
        return _err(e)
