"""从 Magic-Fox 训练页同步训练模型列表（Playwright 抓取，写入 detforge.platform_train_model）。"""
import csv
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from studio.forge import forge_db

logger = logging.getLogger('detforge.platform_models')

ORIGIN = 'https://www.ai.magic-fox.com'


def find_fetch_script():
    from studio.sync import magic_fox_bridge
    return magic_fox_bridge.vendor_fetch_training_models_script()


def parse_subject_id(url):
    if not url:
        return None
    m = re.search(r'subjectId=(\d+)', str(url))
    return m.group(1) if m else None


def build_training_page_url(project):
    """与前端 platformUtils.buildPlatformPages 一致。"""
    approach_id = project.get('approach_id')
    if not approach_id:
        raise ValueError('项目未配置 Approach ID')
    subject_id = parse_subject_id(project.get('training_page_url'))
    subject_q = f'&subjectId={subject_id}' if subject_id else ''
    training = str(project.get('training_page_url') or '').strip()
    if training:
        if not training.startswith('http'):
            training = (
                f'{ORIGIN}/{training.lstrip("/")}'
                if training.startswith('#')
                else f'{ORIGIN}/#/{training.lstrip("/")}'
            )
    else:
        training = f'{ORIGIN}/#/training?approachId={approach_id}{subject_q}'
    return training


def scrape_training_models(training_url, timeout=180, config=None):
    """调用内置脚本抓取训练模型 CSV（凭据来自 config.json / 环境变量）。"""
    from studio.sync import magic_fox_bridge
    script = find_fetch_script()
    _, token = magic_fox_bridge.get_api_token(config)
    fd, csv_path = tempfile.mkstemp(suffix='.csv', prefix='forge_train_models_')
    os.close(fd)
    try:
        cmd = [
            sys.executable, str(script),
            '--url', training_url,
            '--csv', csv_path,
        ]
        logger.info('抓取训练模型: %s', training_url)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **os.environ,
                'PYTHONIOENCODING': 'utf-8',
                'MAGIC_FOX_TOKEN': token,
                'MAGIC_FOX_ACCESS_TOKEN': token,
            },
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or '').strip()
            raise RuntimeError(err or f'抓取脚本退出码 {proc.returncode}')
        return _parse_csv(csv_path)
    finally:
        try:
            os.unlink(csv_path)
        except OSError:
            pass


def _parse_csv(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            train_id = str(row.get('train_id') or '').strip()
            if not train_id or not train_id.isdigit():
                continue
            rows.append({
                'train_id': int(train_id),
                'model_name': str(row.get('模型版本') or row.get('model_name') or '').strip(),
                'model_type': str(row.get('模型类型') or row.get('model_type') or '').strip(),
                'c_time': str(row.get('创建时间') or row.get('c_time') or '').strip(),
                'train_duration': str(row.get('训练时长') or '').strip(),
                'creator': str(row.get('创建人') or '').strip(),
                'train_progress': str(row.get('训练进度') or '').strip(),
                'snapshot_note': str(row.get('数据集快照') or '').strip(),
                'remark': str(row.get('备注') or '').strip(),
            })
    return rows


def sync_project_train_models(project_id, force=False):
    """从 Magic-Fox 训练页抓取并写入 detforge.platform_train_model。"""
    project = forge_db.get_sync_project(int(project_id))
    if not project:
        raise ValueError(f'项目不存在: {project_id}')
    if not force:
        cached = forge_db.list_platform_train_models(int(project_id))
        if cached:
            return {
                'project_id': int(project_id),
                'synced_count': len(cached),
                'skipped': True,
                'models': _normalize_for_api(cached, project),
            }
    url = build_training_page_url(project)
    scraped = scrape_training_models(url)
    if not scraped:
        raise ValueError('训练页未抓取到任何模型，请检查 Magic-Fox 认证与训练页 URL')
    n = forge_db.replace_platform_train_models(int(project_id), scraped)
    rows = forge_db.list_platform_train_models(int(project_id))
    return {
        'project_id': int(project_id),
        'synced_count': n,
        'skipped': False,
        'training_url': url,
        'models': _normalize_for_api(rows, project),
    }


def list_project_train_models(project_id):
    project = forge_db.get_sync_project(int(project_id))
    if not project:
        raise ValueError(f'项目不存在: {project_id}')
    rows = forge_db.list_platform_train_models(int(project_id))
    return {
        'project_id': int(project_id),
        'approach_id': project.get('approach_id'),
        'count': len(rows),
        'models': _normalize_for_api(rows, project),
        'source': 'platform_cache',
    }


def _normalize_for_api(rows, project):
    aid = project.get('approach_id')
    out = []
    for r in rows or []:
        tid = int(r.get('train_id') or r.get('id') or 0)
        if not tid:
            continue
        out.append({
            'id': tid,
            'train_id': tid,
            'model_name': r.get('model_name') or f'train-{tid}',
            'model_type': r.get('model_type') or '',
            'c_time': r.get('c_time_platform') or r.get('c_time') or '',
            'train_duration': r.get('train_duration') or '',
            'creator': r.get('creator') or '',
            'train_progress': r.get('train_progress') or '',
            'snapshot_note': r.get('snapshot_note') or '',
            'remark': r.get('remark') or '',
            'approach_id': aid,
            'path_resolvable': True,
            'source': 'platform',
        })
    return out


def resolve_train_model_name(train_id, project_id=None, approach_id=None):
    tid = int(train_id)
    if project_id:
        row = forge_db.get_platform_train_model(int(project_id), tid)
        if row and row.get('model_name'):
            return row['model_name']
    if approach_id:
        row = forge_db.find_platform_train_model_by_train_id(tid, approach_id=int(approach_id))
        if row and row.get('model_name'):
            return row['model_name']
    return f'train-{tid}'
