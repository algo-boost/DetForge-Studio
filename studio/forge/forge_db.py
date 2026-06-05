"""detforge 写库数据访问层。

新库 `detforge` 与平台库 `vision_backend` 同一 MySQL 实例，故所有写库表
均以跨库限定名 `detforge`.`table` 访问；平台只读表仍按现有 SQL（连接 vision_backend）。
表不加前缀：model_registry / job / job_item / predict_result / manual_qc。
"""
import json
import threading

DEFAULT_FORGE_DB = 'detforge'

# 作业 / 作业项状态机
JOB_STATUSES = ('pending', 'running', 'paused', 'done', 'failed', 'canceled')
ITEM_STATUSES = ('pending', 'running', 'done', 'failed', 'skipped')

_claim_lock = threading.Lock()


def forge_db_name(config=None):
    """写库名（默认 detforge），来自配置 forge_database。"""
    if config is None:
        from server.core import load_config
        config = load_config()
    name = str(config.get('forge_database') or DEFAULT_FORGE_DB).strip()
    return name or DEFAULT_FORGE_DB


def _t(table, config=None):
    """生成跨库限定表名，如 `detforge`.`job`。"""
    return f"`{forge_db_name(config)}`.`{table}`"


def _client():
    from server.core import get_db_client
    return get_db_client()


def _json_dump(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _json_load(value):
    if value is None or value == '':
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


# ── Schema 初始化 ──────────────────────────────────────────────────

def schema_statements(db=None):
    """返回建库 + 5 张表的 DDL 语句列表（幂等）。"""
    db = db or DEFAULT_FORGE_DB
    return [
        f"CREATE DATABASE IF NOT EXISTS `{db}` DEFAULT CHARSET=utf8mb4",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`model_registry` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          name VARCHAR(255) NOT NULL,
          framework VARCHAR(32) NOT NULL,
          sub_type VARCHAR(32) DEFAULT NULL,
          checkpoint_path TEXT NOT NULL,
          labels JSON DEFAULT NULL,
          source VARCHAR(32) DEFAULT 'manual',
          source_ref VARCHAR(64) DEFAULT NULL,
          approach_id INT DEFAULT NULL,
          default_params JSON DEFAULT NULL,
          enabled TINYINT DEFAULT 1,
          c_time DATETIME DEFAULT CURRENT_TIMESTAMP,
          u_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_path (checkpoint_path(255))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`job` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_type VARCHAR(32) NOT NULL,
          name VARCHAR(255) DEFAULT NULL,
          params JSON NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'pending',
          priority INT DEFAULT 100,
          intra_concurrency INT DEFAULT 1,
          total INT DEFAULT 0,
          done INT DEFAULT 0,
          failed INT DEFAULT 0,
          error TEXT DEFAULT NULL,
          worker_id VARCHAR(64) DEFAULT NULL,
          heartbeat DATETIME DEFAULT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          started_at DATETIME DEFAULT NULL,
          finished_at DATETIME DEFAULT NULL,
          KEY idx_status (status, priority, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`job_item` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          seq INT DEFAULT 0,
          ref_key VARCHAR(512) NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'pending',
          attempts INT DEFAULT 0,
          result_ref BIGINT DEFAULT NULL,
          error TEXT DEFAULT NULL,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_job (job_id, status),
          UNIQUE KEY uk_job_ref (job_id, ref_key(255))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`predict_result` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          job_id BIGINT NOT NULL,
          model_id BIGINT NOT NULL,
          model_name VARCHAR(255) DEFAULT NULL,
          source_detail_id BIGINT DEFAULT NULL,
          origin_object_key TEXT DEFAULT NULL,
          img_path TEXT DEFAULT NULL,
          product_no VARCHAR(128) DEFAULT NULL,
          product_id VARCHAR(128) DEFAULT NULL,
          product_type VARCHAR(128) DEFAULT NULL,
          position VARCHAR(128) DEFAULT NULL,
          img_width INT DEFAULT NULL,
          img_height INT DEFAULT NULL,
          ext JSON DEFAULT NULL,
          box_count INT DEFAULT 0,
          max_score FLOAT DEFAULT NULL,
          threshold FLOAT DEFAULT NULL,
          predict_status VARCHAR(16) DEFAULT 'done',
          c_time DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_job (job_id),
          KEY idx_sn (product_no),
          KEY idx_type (product_type),
          UNIQUE KEY uk_job_img (job_id, img_path(255))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`manual_qc` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          batch_id VARCHAR(64) DEFAULT NULL,
          product_no VARCHAR(128) NOT NULL,
          customer_img_path TEXT DEFAULT NULL,
          matched_detail_id BIGINT DEFAULT NULL,
          matched_img_path TEXT DEFAULT NULL,
          matched_object_key TEXT DEFAULT NULL,
          defect_info JSON DEFAULT NULL,
          defect_type VARCHAR(128) DEFAULT NULL,
          qc_category VARCHAR(64) DEFAULT NULL,
          product_type VARCHAR(128) DEFAULT NULL,
          position VARCHAR(128) DEFAULT NULL,
          match_status VARCHAR(16) DEFAULT 'matched',
          note TEXT DEFAULT NULL,
          disposition VARCHAR(32) DEFAULT NULL,
          training_status VARCHAR(32) DEFAULT 'pending' COMMENT 'pending|handoff_ready|closed',
          handoff_dir TEXT DEFAULT NULL,
          workflow_status VARCHAR(32) DEFAULT 'archived' COMMENT 'intake|confirmed|archived|void',
          source VARCHAR(32) DEFAULT NULL COMMENT 'ui|api|script',
          external_ref VARCHAR(128) DEFAULT NULL,
          intake_at DATETIME DEFAULT NULL,
          archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_sn (product_no),
          KEY idx_workflow (workflow_status),
          KEY idx_batch (batch_id),
          KEY idx_category (qc_category),
          KEY idx_archived (archived_at),
          KEY idx_training (training_status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`curation_batch` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          batch_code VARCHAR(64) NOT NULL,
          source_task_id VARCHAR(64) NOT NULL,
          strategy_id VARCHAR(128) DEFAULT NULL,
          strategy_name VARCHAR(255) DEFAULT NULL,
          data_source VARCHAR(32) DEFAULT 'detail',
          intent_type VARCHAR(32) DEFAULT 'daily_ng' COMMENT 'daily_ng|replay_eval|customer_qc',
          status VARCHAR(32) NOT NULL DEFAULT 'created',
          reviewer VARCHAR(128) DEFAULT NULL,
          note TEXT DEFAULT NULL,
          total_count INT DEFAULT 0,
          keep_count INT DEFAULT 0,
          reject_count INT DEFAULT 0,
          pending_count INT DEFAULT 0,
          export_dir TEXT DEFAULT NULL,
          archive_dir TEXT DEFAULT NULL,
          handoff_dir TEXT DEFAULT NULL,
          sync_dataset_id BIGINT DEFAULT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          exported_at DATETIME DEFAULT NULL,
          imported_at DATETIME DEFAULT NULL,
          archived_at DATETIME DEFAULT NULL,
          handoff_at DATETIME DEFAULT NULL,
          UNIQUE KEY uk_batch_code (batch_code),
          KEY idx_status (status),
          KEY idx_task (source_task_id),
          KEY idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`curation_item` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          batch_id BIGINT NOT NULL,
          batch_row_id VARCHAR(96) NOT NULL,
          seq INT DEFAULT 0,
          img_name VARCHAR(512) DEFAULT NULL,
          img_path TEXT DEFAULT NULL,
          product_no VARCHAR(128) DEFAULT NULL,
          product_type VARCHAR(128) DEFAULT NULL,
          check_status VARCHAR(32) DEFAULT NULL,
          categories_summary VARCHAR(512) DEFAULT NULL,
          decision VARCHAR(16) DEFAULT 'pending' COMMENT 'keep|reject|pending',
          disposition VARCHAR(32) DEFAULT NULL COMMENT 'ng_confirmed|need_label|fp_model|fn_missed|…',
          need_platform_label TINYINT DEFAULT 0,
          reject_reason VARCHAR(255) DEFAULT NULL,
          note TEXT DEFAULT NULL,
          source_meta JSON DEFAULT NULL,
          KEY idx_batch (batch_id),
          KEY idx_decision (batch_id, decision),
          KEY idx_disposition (batch_id, disposition),
          UNIQUE KEY uk_batch_row (batch_id, batch_row_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`replay_run` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          status VARCHAR(32) NOT NULL DEFAULT 'pending',
          stage VARCHAR(32) DEFAULT NULL,
          spec_json JSON NOT NULL,
          stage1_task_id VARCHAR(64) DEFAULT NULL,
          predict_job_id BIGINT DEFAULT NULL,
          stage2_task_id VARCHAR(64) DEFAULT NULL,
          curation_batch_id BIGINT DEFAULT NULL,
          result_json JSON DEFAULT NULL,
          error TEXT DEFAULT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_status (status),
          KEY idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`sync_project` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          name VARCHAR(255) NOT NULL,
          approach_id INT DEFAULT NULL,
          training_page_url TEXT DEFAULT NULL,
          local_root TEXT DEFAULT NULL,
          note TEXT DEFAULT NULL,
          enabled TINYINT DEFAULT 1,
          c_time DATETIME DEFAULT CURRENT_TIMESTAMP,
          u_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`sync_dataset` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          project_id BIGINT NOT NULL,
          name VARCHAR(255) NOT NULL,
          source_type VARCHAR(16) NOT NULL DEFAULT 'dataset',
          source_id BIGINT NOT NULL,
          data_view_url TEXT DEFAULT NULL,
          local_dir TEXT NOT NULL,
          split_subdirs TINYINT DEFAULT 0,
          strip_prefix TINYINT DEFAULT 1,
          write_db TINYINT DEFAULT 1,
          remote_count INT DEFAULT 0,
          local_count INT DEFAULT 0,
          last_sync_at DATETIME DEFAULT NULL,
          last_sync_job_id BIGINT DEFAULT NULL,
          last_sync_error TEXT DEFAULT NULL,
          enabled TINYINT DEFAULT 1,
          c_time DATETIME DEFAULT CURRENT_TIMESTAMP,
          u_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_project (project_id),
          UNIQUE KEY uk_source (project_id, source_type, source_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`dataset_item` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          dataset_id BIGINT NOT NULL,
          remote_item_id BIGINT NOT NULL,
          file_name VARCHAR(512) NOT NULL,
          local_path TEXT DEFAULT NULL,
          object_key TEXT DEFAULT NULL,
          split_type VARCHAR(16) DEFAULT NULL,
          annotations JSON DEFAULT NULL,
          box_count INT DEFAULT 0,
          remote_mtime DATETIME DEFAULT NULL,
          source_detail_id BIGINT DEFAULT NULL COMMENT 'vision_backend.product_detection_detail_result.id',
          product_no VARCHAR(128) DEFAULT NULL COMMENT 'SN',
          product_id VARCHAR(128) DEFAULT NULL,
          product_type VARCHAR(128) DEFAULT NULL COMMENT '款型',
          position VARCHAR(128) DEFAULT NULL,
          platform_c_time DATETIME DEFAULT NULL COMMENT '平台检测时间',
          trace_status VARCHAR(16) DEFAULT NULL COMMENT 'matched|sn_only|path_only|unmatched',
          synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_dataset (dataset_id),
          KEY idx_file (file_name(255)),
          KEY idx_item_sn (product_no),
          KEY idx_item_type (product_type),
          KEY idx_item_time (platform_c_time),
          KEY idx_trace (trace_status),
          UNIQUE KEY uk_remote (dataset_id, remote_item_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        f"""CREATE TABLE IF NOT EXISTS `{db}`.`platform_train_model` (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          project_id BIGINT NOT NULL,
          train_id BIGINT NOT NULL,
          model_name VARCHAR(255) DEFAULT NULL,
          model_type VARCHAR(128) DEFAULT NULL,
          train_duration VARCHAR(64) DEFAULT NULL,
          creator VARCHAR(64) DEFAULT NULL,
          train_progress VARCHAR(64) DEFAULT NULL,
          snapshot_note TEXT DEFAULT NULL,
          remark TEXT DEFAULT NULL,
          c_time_platform VARCHAR(32) DEFAULT NULL,
          synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_project (project_id),
          UNIQUE KEY uk_proj_train (project_id, train_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]


# 旧库平滑升级：表已存在时补齐新列（MySQL 不支持 ADD COLUMN IF NOT EXISTS）
_EXTRA_COLUMNS = [
    ('manual_qc', 'defect_type', "ADD COLUMN defect_type VARCHAR(128) DEFAULT NULL"),
    ('manual_qc', 'qc_category', "ADD COLUMN qc_category VARCHAR(64) DEFAULT NULL"),
    ('manual_qc', 'disposition', "ADD COLUMN disposition VARCHAR(32) DEFAULT NULL"),
    ('manual_qc', 'training_status', "ADD COLUMN training_status VARCHAR(32) DEFAULT 'pending'"),
    ('manual_qc', 'handoff_dir', "ADD COLUMN handoff_dir TEXT DEFAULT NULL"),
    ('manual_qc', 'workflow_status', "ADD COLUMN workflow_status VARCHAR(32) DEFAULT 'archived'"),
    ('manual_qc', 'source', "ADD COLUMN source VARCHAR(32) DEFAULT NULL"),
    ('manual_qc', 'external_ref', "ADD COLUMN external_ref VARCHAR(128) DEFAULT NULL"),
    ('manual_qc', 'intake_at', "ADD COLUMN intake_at DATETIME DEFAULT NULL"),
    ('curation_batch', 'intent_type', "ADD COLUMN intent_type VARCHAR(32) DEFAULT 'daily_ng'"),
    ('curation_item', 'disposition', "ADD COLUMN disposition VARCHAR(32) DEFAULT NULL"),
    ('curation_item', 'need_platform_label', "ADD COLUMN need_platform_label TINYINT DEFAULT 0"),
    ('job_item', 'next_retry_at', "ADD COLUMN next_retry_at DATETIME DEFAULT NULL"),
    ('dataset_item', 'source_detail_id', "ADD COLUMN source_detail_id BIGINT DEFAULT NULL"),
    ('dataset_item', 'product_no', "ADD COLUMN product_no VARCHAR(128) DEFAULT NULL"),
    ('dataset_item', 'product_id', "ADD COLUMN product_id VARCHAR(128) DEFAULT NULL"),
    ('dataset_item', 'product_type', "ADD COLUMN product_type VARCHAR(128) DEFAULT NULL"),
    ('dataset_item', 'position', "ADD COLUMN position VARCHAR(128) DEFAULT NULL"),
    ('dataset_item', 'platform_c_time', "ADD COLUMN platform_c_time DATETIME DEFAULT NULL"),
    ('dataset_item', 'trace_status', "ADD COLUMN trace_status VARCHAR(16) DEFAULT NULL"),
]

_EXTRA_INDEXES = [
    ('manual_qc', 'uk_sn_customer_img', 'ADD UNIQUE KEY uk_sn_customer_img (product_no, customer_img_path(255))'),
    ('manual_qc', 'idx_training', 'ADD KEY idx_training (training_status)'),
    ('manual_qc', 'idx_workflow', 'ADD KEY idx_workflow (workflow_status)'),
    ('curation_item', 'idx_disposition', 'ADD KEY idx_disposition (batch_id, disposition)'),
    ('dataset_item', 'idx_item_sn', 'ADD KEY idx_item_sn (product_no)'),
    ('dataset_item', 'idx_item_type', 'ADD KEY idx_item_type (product_type)'),
    ('dataset_item', 'idx_item_time', 'ADD KEY idx_item_time (platform_c_time)'),
    ('dataset_item', 'idx_trace', 'ADD KEY idx_trace (trace_status)'),
]

RETRY_BACKOFF_BASE_SECONDS = 30  # 失败重试退避基数：第 n 次失败后等待 n*base 秒


def _column_exists(client, db, table, col):
    row = client.fetchone(
        "SELECT 1 AS x FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (db, table, col),
    )
    return bool(row)


def _ensure_extra_columns(client, db):
    n = 0
    for table, col, clause in _EXTRA_COLUMNS:
        try:
            if not _column_exists(client, db, table, col):
                client.execute(f"ALTER TABLE `{db}`.`{table}` {clause}")
                n += 1
        except Exception:  # noqa: BLE001 表尚未建好等情况忽略
            pass
    return n


def _index_exists(client, db, table, index_name):
    row = client.fetchone(
        "SELECT 1 AS x FROM information_schema.statistics "
        "WHERE table_schema=%s AND table_name=%s AND index_name=%s LIMIT 1",
        (db, table, index_name),
    )
    return bool(row)


def _ensure_extra_indexes(client, db):
    n = 0
    for table, idx_name, clause in _EXTRA_INDEXES:
        try:
            if not _index_exists(client, db, table, idx_name):
                client.execute(f"ALTER TABLE `{db}`.`{table}` {clause}")
                n += 1
        except Exception:  # noqa: BLE001 已有重复数据时建唯一索引会失败，忽略
            pass
    return n


def ensure_schema(client=None, config=None):
    """建库 + 建表（幂等）+ 补齐新增列/索引。返回执行的语句数。"""
    client = client or _client()
    db = forge_db_name(config)
    count = 0
    for stmt in schema_statements(db):
        client.execute(stmt)
        count += 1
    count += _ensure_extra_columns(client, db)
    count += _ensure_extra_indexes(client, db)
    return count


def schema_ready(client=None, config=None):
    """检测写库 5 张表是否都已存在。"""
    client = client or _client()
    db = forge_db_name(config)
    try:
        rows = client.fetchall(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
            (db,),
        )
    except Exception:
        return False
    have = {str(r.get('table_name') or r.get('TABLE_NAME') or '').lower() for r in rows}
    need = {
        'model_registry', 'job', 'job_item', 'predict_result', 'manual_qc',
        'curation_batch', 'curation_item', 'replay_run',
        'sync_project', 'sync_dataset', 'dataset_item', 'platform_train_model',
    }
    return need.issubset(have)


# ── 模型注册 ───────────────────────────────────────────────────────

def list_models(enabled_only=False):
    sql = f"SELECT * FROM {_t('model_registry')}"
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY id DESC"
    rows = _client().fetchall(sql)
    for r in rows:
        r['labels'] = _json_load(r.get('labels'))
        r['default_params'] = _json_load(r.get('default_params'))
    return rows


def get_model(model_id):
    row = _client().fetchone(f"SELECT * FROM {_t('model_registry')} WHERE id=%s", (int(model_id),))
    if row:
        row['labels'] = _json_load(row.get('labels'))
        row['default_params'] = _json_load(row.get('default_params'))
    return row


def upsert_model(data):
    """按 checkpoint_path 唯一键插入或更新，返回 model_id。"""
    sql = f"""
        INSERT INTO {_t('model_registry')}
            (name, framework, sub_type, checkpoint_path, labels, source, source_ref,
             approach_id, default_params, enabled)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), framework=VALUES(framework), sub_type=VALUES(sub_type),
            labels=VALUES(labels), source=VALUES(source), source_ref=VALUES(source_ref),
            approach_id=VALUES(approach_id), default_params=VALUES(default_params),
            enabled=VALUES(enabled)
    """
    args = (
        str(data.get('name') or '').strip() or 'unnamed',
        str(data.get('framework') or '').strip(),
        (data.get('sub_type') or None),
        str(data.get('checkpoint_path') or '').strip(),
        _json_dump(data.get('labels')),
        str(data.get('source') or 'manual'),
        (data.get('source_ref') or None),
        data.get('approach_id'),
        _json_dump(data.get('default_params')),
        1 if data.get('enabled', 1) else 0,
    )
    client = _client()
    client.execute(sql, args)
    row = client.fetchone(
        f"SELECT id FROM {_t('model_registry')} WHERE checkpoint_path=%s",
        (args[3],),
    )
    return int(row['id']) if row else None


def delete_model(model_id):
    return _client().execute(f"DELETE FROM {_t('model_registry')} WHERE id=%s", (int(model_id),))


def set_model_enabled(model_id, enabled):
    return _client().execute(
        f"UPDATE {_t('model_registry')} SET enabled=%s WHERE id=%s",
        (1 if enabled else 0, int(model_id)),
    )


# ── 作业 / 作业项 ──────────────────────────────────────────────────

def create_job(job_type, name, params, items=None, priority=100, intra_concurrency=1):
    """创建作业并批量写入作业项；total=作业项数。返回 job_id。"""
    client = _client()
    job_id = client.execute_returning_id(
        f"""INSERT INTO {_t('job')} (job_type, name, params, status, priority, intra_concurrency, total)
            VALUES (%s,%s,%s,'pending',%s,%s,%s)""",
        (
            str(job_type), (name or None), _json_dump(params or {}),
            int(priority), max(1, int(intra_concurrency or 1)),
            len(items or []),
        ),
    )
    if items:
        add_job_items(job_id, items)
    return job_id


def add_job_items(job_id, ref_keys):
    """批量追加作业项（忽略重复 ref_key）。"""
    rows = []
    for seq, ref in enumerate(ref_keys):
        rows.append((int(job_id), seq, str(ref)))
    sql = f"""INSERT IGNORE INTO {_t('job_item')} (job_id, seq, ref_key, status)
              VALUES (%s,%s,%s,'pending')"""
    n = _client().executemany(sql, rows)
    _client().execute(
        f"UPDATE {_t('job')} SET total=(SELECT COUNT(*) FROM {_t('job_item')} WHERE job_id=%s) WHERE id=%s",
        (int(job_id), int(job_id)),
    )
    return n


def get_job(job_id):
    row = _client().fetchone(f"SELECT * FROM {_t('job')} WHERE id=%s", (int(job_id),))
    if row:
        row['params'] = _json_load(row.get('params'))
    return row


def list_jobs(status=None, job_type=None, limit=100, offset=0):
    where, args = [], []
    if status:
        where.append("status=%s")
        args.append(status)
    if job_type:
        where.append("job_type=%s")
        args.append(job_type)
    sql = f"SELECT * FROM {_t('job')}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT %s"
    args.append(int(limit))
    if offset:
        sql += " OFFSET %s"
        args.append(int(offset))
    rows = _client().fetchall(sql, tuple(args))
    for r in rows:
        r['params'] = _json_load(r.get('params'))
    return rows


def count_jobs(status=None, job_type=None):
    where, args = [], []
    if status:
        where.append("status=%s"); args.append(status)
    if job_type:
        where.append("job_type=%s"); args.append(job_type)
    sql = f"SELECT COUNT(*) AS n FROM {_t('job')}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    row = _client().fetchone(sql, tuple(args))
    return int(row['n']) if row else 0


def update_job(job_id, **fields):
    if not fields:
        return 0
    cols = ', '.join(f"{k}=%s" for k in fields)
    args = list(fields.values()) + [int(job_id)]
    return _client().execute(f"UPDATE {_t('job')} SET {cols} WHERE id=%s", tuple(args))


def recompute_job_progress(job_id):
    """根据 job_item 统计 done/failed，并在全部完成时收尾作业状态。"""
    client = _client()
    stat = client.fetchone(
        f"""SELECT
              COUNT(*) AS total,
              SUM(status='done') AS done,
              SUM(status='failed') AS failed,
              SUM(status IN ('pending','running')) AS remaining
            FROM {_t('job_item')} WHERE job_id=%s""",
        (int(job_id),),
    ) or {}
    done = int(stat.get('done') or 0)
    failed = int(stat.get('failed') or 0)
    remaining = int(stat.get('remaining') or 0)
    client.execute(
        f"UPDATE {_t('job')} SET done=%s, failed=%s WHERE id=%s",
        (done, failed, int(job_id)),
    )
    return {'done': done, 'failed': failed, 'remaining': remaining}


def claim_next_job(worker_id, job_types=None):
    """领取一个 pending 作业，置为 running（进程内加锁避免并发争抢）。返回 job 或 None。"""
    client = _client()
    type_clause, args = '', []
    if job_types:
        placeholders = ','.join(['%s'] * len(job_types))
        type_clause = f" AND job_type IN ({placeholders})"
        args.extend(job_types)
    with _claim_lock:
        cand = client.fetchone(
            f"SELECT id FROM {_t('job')} WHERE status='pending'{type_clause} "
            f"ORDER BY priority, id LIMIT 1",
            tuple(args),
        )
        if not cand:
            return None
        job_id = int(cand['id'])
        affected = client.execute(
            f"""UPDATE {_t('job')}
                SET status='running', worker_id=%s, started_at=COALESCE(started_at, NOW()), heartbeat=NOW()
                WHERE id=%s AND status='pending'""",
            (str(worker_id), job_id),
        )
        if not affected:
            return None
    return get_job(job_id)


def heartbeat(job_id, worker_id=None):
    if worker_id is not None:
        return _client().execute(
            f"UPDATE {_t('job')} SET heartbeat=NOW() WHERE id=%s AND worker_id=%s",
            (int(job_id), str(worker_id)),
        )
    return _client().execute(f"UPDATE {_t('job')} SET heartbeat=NOW() WHERE id=%s", (int(job_id),))


def finish_job(job_id, status='done', error=None):
    return _client().execute(
        f"UPDATE {_t('job')} SET status=%s, error=%s, finished_at=NOW() WHERE id=%s",
        (status, error, int(job_id)),
    )


def job_control(job_id, action):
    """暂停/继续/取消/重试。返回新状态或 None。"""
    job = get_job(job_id)
    if not job:
        return None
    status = job['status']
    if action == 'pause' and status in ('pending', 'running'):
        update_job(job_id, status='paused')
        return 'paused'
    if action == 'resume' and status in ('paused', 'failed', 'canceled'):
        update_job(job_id, status='pending', worker_id=None, error=None, finished_at=None)
        return 'pending'
    if action == 'cancel' and status in ('pending', 'running', 'paused'):
        update_job(job_id, status='canceled')
        return 'canceled'
    if action == 'retry':
        reset_failed_items(job_id)
        update_job(job_id, status='pending', worker_id=None, error=None, finished_at=None)
        return 'pending'
    return status


def reclaim_stale_jobs(timeout_seconds=120):
    """心跳超时的 running 作业回收为 pending，便于续跑。"""
    return _client().execute(
        f"""UPDATE {_t('job')}
            SET status='pending', worker_id=NULL
            WHERE status='running'
              AND heartbeat IS NOT NULL
              AND heartbeat < (NOW() - INTERVAL %s SECOND)""",
        (int(timeout_seconds),),
    )


def pending_items(job_id, limit=None):
    """取待处理项；退避窗口内（next_retry_at>NOW）的失败重试项暂不返回。"""
    sql = (f"SELECT * FROM {_t('job_item')} WHERE job_id=%s AND status IN ('pending','running') "
           f"AND (next_retry_at IS NULL OR next_retry_at <= NOW()) "
           f"ORDER BY seq, id")
    args = [int(job_id)]
    if limit:
        sql += " LIMIT %s"
        args.append(int(limit))
    return _client().fetchall(sql, tuple(args))


def mark_item_running(item_id):
    return _client().execute(
        f"UPDATE {_t('job_item')} SET status='running', attempts=attempts+1 WHERE id=%s",
        (int(item_id),),
    )


def mark_item_done(item_id, result_ref=None):
    return _client().execute(
        f"UPDATE {_t('job_item')} SET status='done', result_ref=%s, error=NULL WHERE id=%s",
        (result_ref, int(item_id)),
    )


def mark_item_failed(item_id, error=None, max_attempts=3):
    """超过 max_attempts 标记 failed，否则回退 pending 并设置退避时间以便延迟重试。"""
    return _client().execute(
        f"""UPDATE {_t('job_item')}
            SET status=IF(attempts >= %s, 'failed', 'pending'),
                next_retry_at=IF(attempts >= %s, NULL, NOW() + INTERVAL (attempts * %s) SECOND),
                error=%s
            WHERE id=%s""",
        (int(max_attempts), int(max_attempts), int(RETRY_BACKOFF_BASE_SECONDS),
         (str(error) if error else None), int(item_id)),
    )


def reset_failed_items(job_id):
    return _client().execute(
        f"UPDATE {_t('job_item')} SET status='pending', attempts=0, error=NULL, next_retry_at=NULL "
        f"WHERE job_id=%s AND status='failed'",
        (int(job_id),),
    )


# ── 预测结果 ───────────────────────────────────────────────────────

def insert_predict_result(row):
    """写入一行预测结果，返回 predict_result.id。"""
    sql = f"""
        INSERT INTO {_t('predict_result')}
            (job_id, model_id, model_name, source_detail_id, origin_object_key, img_path,
             product_no, product_id, product_type, position, img_width, img_height,
             ext, box_count, max_score, threshold, predict_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            model_id=VALUES(model_id), model_name=VALUES(model_name),
            ext=VALUES(ext), box_count=VALUES(box_count), max_score=VALUES(max_score),
            threshold=VALUES(threshold), predict_status=VALUES(predict_status)
    """
    args = (
        int(row['job_id']), int(row['model_id']), (row.get('model_name') or None),
        row.get('source_detail_id'), (row.get('origin_object_key') or None),
        (row.get('img_path') or None), (row.get('product_no') or None),
        (row.get('product_id') or None), (row.get('product_type') or None),
        (row.get('position') or None), row.get('img_width'), row.get('img_height'),
        _json_dump(row.get('ext')), int(row.get('box_count') or 0),
        row.get('max_score'), row.get('threshold'),
        str(row.get('predict_status') or 'done'),
    )
    client = _client()
    client.execute(sql, args)
    found = client.fetchone(
        f"SELECT id FROM {_t('predict_result')} WHERE job_id=%s AND img_path=%s",
        (int(row['job_id']), (row.get('img_path') or None)),
    )
    return int(found['id']) if found else None


def predict_result_select_sql(config=None):
    """供查询页「数据源=预测结果表」拼接的限定表名。"""
    return _t('predict_result', config)


def get_predict_result(result_id):
    row = _client().fetchone(f"SELECT * FROM {_t('predict_result')} WHERE id=%s", (int(result_id),))
    if row:
        row['ext'] = _json_load(row.get('ext'))
    return row


def fetch_predict_ext_by_ids(result_ids, config=None):
    """按主键批量拉取 ext（查询 SQL 未 SELECT ext 时供规则筛选补全）。"""
    ids = []
    for raw in result_ids or []:
        if raw is None or str(raw).strip() == '':
            continue
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    if len(ids) > 10000:
        ids = ids[:10000]
    placeholders = ','.join(['%s'] * len(ids))
    rows = _client().fetchall(
        f"SELECT id, ext FROM {_t('predict_result', config)} WHERE id IN ({placeholders})",
        tuple(ids),
    )
    return {int(r['id']): r.get('ext') for r in rows}


def _predict_result_where(job_id, filters=None, result_ids=None):
    from studio.forge.predict_result_filters import append_predict_result_filter_sql, normalize_filter_dict

    where = ['job_id=%s']
    args = [int(job_id)]
    if result_ids:
        ids = [int(i) for i in result_ids if i is not None and str(i).strip() != '']
        if ids:
            placeholders = ','.join(['%s'] * len(ids))
            where.append(f'id IN ({placeholders})')
            args.extend(ids)
    append_predict_result_filter_sql(where, args, normalize_filter_dict(filters))
    return where, args


def _predict_result_order(filters=None):
    sort = (filters or {}).get('sort') or 'id_desc'
    order_map = {
        'id_desc': 'id DESC',
        'id_asc': 'id ASC',
        'score_desc': 'max_score DESC, id DESC',
        'score_asc': 'max_score ASC, id DESC',
        'boxes_desc': 'box_count DESC, id DESC',
        'boxes_asc': 'box_count ASC, id DESC',
    }
    return order_map.get(sort, 'id DESC')


def count_predict_results(job_id, filters=None, result_ids=None):
    where, args = _predict_result_where(job_id, filters, result_ids)
    row = _client().fetchone(
        f"SELECT COUNT(*) AS c FROM {_t('predict_result')} WHERE {' AND '.join(where)}",
        tuple(args),
    )
    return int(row['c']) if row else 0


def list_predict_results(job_id, limit=200, offset=0, filters=None, result_ids=None):
    where, args = _predict_result_where(job_id, filters, result_ids)
    order = _predict_result_order(filters)
    sql = (
        f"SELECT * FROM {_t('predict_result')} WHERE {' AND '.join(where)} "
        f"ORDER BY {order} LIMIT %s OFFSET %s"
    )
    rows = _client().fetchall(sql, tuple(args + [int(limit), int(offset)]))
    for r in rows:
        r['ext'] = _json_load(r.get('ext'))
    return rows


def list_job_items(job_id, status=None, limit=200):
    where, args = ["job_id=%s"], [int(job_id)]
    if status:
        where.append("status=%s")
        args.append(status)
    args.append(int(limit))
    return _client().fetchall(
        f"SELECT * FROM {_t('job_item')} WHERE {' AND '.join(where)} ORDER BY id LIMIT %s",
        tuple(args),
    )


# ── 人工质检归档 ───────────────────────────────────────────────────

def insert_manual_qc(row):
    sql = f"""
        INSERT INTO {_t('manual_qc')}
            (batch_id, product_no, customer_img_path, matched_detail_id, matched_img_path,
             matched_object_key, defect_info, defect_type, qc_category,
             product_type, position, match_status, note, disposition, training_status,
             workflow_status, source, external_ref, intake_at, archived_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    args = (
        (row.get('batch_id') or None), str(row.get('product_no') or '').strip(),
        (row.get('customer_img_path') or None), row.get('matched_detail_id'),
        (row.get('matched_img_path') or None), (row.get('matched_object_key') or None),
        _json_dump(row.get('defect_info')), (row.get('defect_type') or None),
        (row.get('qc_category') or None), (row.get('product_type') or None),
        (row.get('position') or None), str(row.get('match_status') or 'matched'),
        (row.get('note') or None), (row.get('disposition') or None),
        str(row.get('training_status') or 'pending'),
        str(row.get('workflow_status') or 'archived'),
        (row.get('source') or None), (row.get('external_ref') or None),
        row.get('intake_at'), row.get('archived_at'),
    )
    return _client().execute_returning_id(sql, args)


def insert_manual_qc_batch(rows):
    return [insert_manual_qc(r) for r in rows]


_MANUAL_QC_EDITABLE = ('defect_type', 'qc_category', 'note', 'product_no',
                       'customer_img_path', 'match_status', 'disposition',
                       'training_status', 'handoff_dir', 'workflow_status',
                       'matched_detail_id', 'matched_img_path', 'matched_object_key',
                       'defect_info', 'product_type', 'position', 'batch_id',
                       'source', 'external_ref', 'archived_at', 'intake_at')


def get_manual_qc(qc_id):
    row = _client().fetchone(f"SELECT * FROM {_t('manual_qc')} WHERE id=%s", (int(qc_id),))
    if row:
        row['defect_info'] = _json_load(row.get('defect_info'))
    return row


def update_manual_qc(qc_id, fields):
    """更新 manual_qc 允许字段。返回受影响行数。"""
    sets = {}
    for k, v in (fields or {}).items():
        if k not in _MANUAL_QC_EDITABLE:
            continue
        if k == 'defect_info':
            sets[k] = _json_dump(v)
        else:
            sets[k] = v
    if not sets:
        return 0
    cols = ', '.join(f"{k}=%s" for k in sets)
    args = list(sets.values()) + [int(qc_id)]
    return _client().execute(f"UPDATE {_t('manual_qc')} SET {cols} WHERE id=%s", tuple(args))


def delete_manual_qc(qc_id):
    return _client().execute(f"DELETE FROM {_t('manual_qc')} WHERE id=%s", (int(qc_id),))


def find_manual_qc_duplicate(product_no, customer_img_path, *, workflow_status=None):
    """按 SN + 客户图路径查已存在记录（默认仅已定案 archived）。"""
    if not customer_img_path:
        return None
    where = ["product_no=%s", "customer_img_path=%s"]
    args = [str(product_no or '').strip(), customer_img_path]
    if workflow_status:
        if isinstance(workflow_status, (list, tuple)):
            where.append(f"workflow_status IN ({','.join(['%s'] * len(workflow_status))})")
            args.extend(workflow_status)
        else:
            where.append("workflow_status=%s")
            args.append(workflow_status)
    else:
        where.append("workflow_status='archived'")
    return _client().fetchone(
        f"SELECT id, qc_category, defect_type, archived_at, workflow_status FROM {_t('manual_qc')} "
        f"WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT 1",
        tuple(args),
    )


def referenced_customer_imgs():
    """所有被 manual_qc 引用的客户图绝对路径集合（用于清理孤儿上传文件）。"""
    rows = _client().fetchall(
        f"SELECT DISTINCT customer_img_path FROM {_t('manual_qc')} WHERE customer_img_path IS NOT NULL"
    )
    return {str(r.get('customer_img_path')) for r in rows if r.get('customer_img_path')}


def list_manual_qc(batch_id=None, product_no=None, limit=200, offset=0,
                   start=None, end=None, categories=None, defect_types=None,
                   match_status=None, training_status=None, workflow_status=None):
    """支持按批次/SN/时段(archived_at)/类别/工作流状态过滤。"""
    where, args = [], []
    if workflow_status:
        sts = [s for s in (workflow_status if isinstance(workflow_status, (list, tuple)) else [workflow_status]) if s]
        if len(sts) == 1:
            where.append("workflow_status=%s")
            args.append(sts[0])
        elif sts:
            where.append(f"workflow_status IN ({','.join(['%s'] * len(sts))})")
            args.extend(sts)
    if batch_id:
        where.append("batch_id=%s")
        args.append(batch_id)
    if product_no:
        where.append("product_no=%s")
        args.append(product_no)
    if start:
        where.append("archived_at >= %s")
        args.append(start)
    if end:
        where.append("archived_at <= %s")
        args.append(end)
    if categories:
        cats = [c for c in (categories if isinstance(categories, (list, tuple)) else [categories]) if c]
        if cats:
            where.append(f"qc_category IN ({','.join(['%s'] * len(cats))})")
            args.extend(cats)
    if defect_types:
        dts = [d for d in (defect_types if isinstance(defect_types, (list, tuple)) else [defect_types]) if d]
        if dts:
            where.append(f"defect_type IN ({','.join(['%s'] * len(dts))})")
            args.extend(dts)
    if match_status:
        where.append("match_status=%s")
        args.append(match_status)
    if training_status:
        where.append("training_status=%s")
        args.append(training_status)
    sql = f"SELECT * FROM {_t('manual_qc')}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    if limit:
        sql += " LIMIT %s"
        args.append(int(limit))
        if offset:
            sql += " OFFSET %s"
            args.append(int(offset))
    rows = _client().fetchall(sql, tuple(args))
    for r in rows:
        r['defect_info'] = _json_load(r.get('defect_info'))
    return rows


def manual_qc_training_summary():
    """按 training_status 汇总已定案 manual_qc 数量。"""
    rows = _client().fetchall(
        f"SELECT training_status, COUNT(*) AS c FROM {_t('manual_qc')} "
        f"WHERE workflow_status='archived' GROUP BY training_status"
    )
    summary = {'pending': 0, 'handoff_ready': 0, 'closed': 0, 'total': 0}
    for r in rows:
        st = str(r.get('training_status') or 'pending')
        n = int(r.get('c') or 0)
        if st in summary:
            summary[st] = n
        summary['total'] += n
    return summary


def list_manual_qc_batch_groups(limit=60):
    """按 batch_id 汇总；无 batch_id 时按归档日期归组。"""
    lim = max(1, min(int(limit or 60), 200))
    rows = _client().fetchall(
        f"""SELECT
              COALESCE(NULLIF(TRIM(batch_id), ''), DATE_FORMAT(archived_at, '%%Y-%%m-%%d')) AS batch_key,
              MAX(batch_id) AS batch_id,
              DATE(MIN(archived_at)) AS batch_day,
              COUNT(*) AS total,
              SUM(CASE WHEN training_status = 'pending' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN training_status = 'handoff_ready' THEN 1 ELSE 0 END) AS handoff_ready,
              SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS matched,
              MIN(archived_at) AS first_at,
              MAX(archived_at) AS last_at
            FROM {_t('manual_qc')}
            WHERE workflow_status='archived'
            GROUP BY batch_key
            ORDER BY last_at DESC
            LIMIT %s""",
        (lim,),
    )
    for r in rows:
        if r.get('batch_day') is not None:
            r['batch_day'] = str(r['batch_day'])
        if r.get('first_at') is not None:
            r['first_at'] = str(r['first_at'])
        if r.get('last_at') is not None:
            r['last_at'] = str(r['last_at'])
    return rows


def update_manual_qc_training_batch(qc_ids, training_status, handoff_dir=None):
    if not qc_ids:
        return 0
    ids = [int(x) for x in qc_ids]
    placeholders = ','.join(['%s'] * len(ids))
    if handoff_dir is not None:
        sql = f"UPDATE {_t('manual_qc')} SET training_status=%s, handoff_dir=%s WHERE id IN ({placeholders})"
        args = [training_status, handoff_dir] + ids
    else:
        sql = f"UPDATE {_t('manual_qc')} SET training_status=%s WHERE id IN ({placeholders})"
        args = [training_status] + ids
    return _client().execute(sql, tuple(args))


def manual_qc_workflow_counts():
    """按 workflow_status 统计案卷数量。"""
    rows = _client().fetchall(
        f"SELECT workflow_status, COUNT(*) AS c FROM {_t('manual_qc')} GROUP BY workflow_status"
    )
    out = {'intake': 0, 'confirmed': 0, 'archived': 0, 'void': 0, 'total': 0}
    for r in rows:
        st = str(r.get('workflow_status') or 'archived')
        n = int(r.get('c') or 0)
        if st in out:
            out[st] = n
        out['total'] += n
    return out


def count_manual_qc(batch_id=None, product_no=None, start=None, end=None,
                    categories=None, defect_types=None, match_status=None,
                    training_status=None, workflow_status=None):
    where, args = [], []
    if workflow_status:
        sts = [s for s in (workflow_status if isinstance(workflow_status, (list, tuple)) else [workflow_status]) if s]
        if len(sts) == 1:
            where.append("workflow_status=%s")
            args.append(sts[0])
        elif sts:
            where.append(f"workflow_status IN ({','.join(['%s'] * len(sts))})")
            args.extend(sts)
    if batch_id:
        where.append("batch_id=%s"); args.append(batch_id)
    if product_no:
        where.append("product_no=%s"); args.append(product_no)
    if start:
        where.append("archived_at >= %s"); args.append(start)
    if end:
        where.append("archived_at <= %s"); args.append(end)
    if categories:
        cats = [c for c in (categories if isinstance(categories, (list, tuple)) else [categories]) if c]
        if cats:
            where.append(f"qc_category IN ({','.join(['%s'] * len(cats))})"); args.extend(cats)
    if defect_types:
        dts = [d for d in (defect_types if isinstance(defect_types, (list, tuple)) else [defect_types]) if d]
        if dts:
            where.append(f"defect_type IN ({','.join(['%s'] * len(dts))})"); args.extend(dts)
    if match_status:
        where.append("match_status=%s"); args.append(match_status)
    if training_status:
        where.append("training_status=%s"); args.append(training_status)
    sql = f"SELECT COUNT(*) AS n FROM {_t('manual_qc')}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    row = _client().fetchone(sql, tuple(args))
    return int(row['n']) if row else 0


# ── 数据集同步：项目 / 数据集 / 标注项 ─────────────────────────────

def list_sync_projects(enabled_only=False):
    sql = f"SELECT * FROM {_t('sync_project')}"
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY name"
    return _client().fetchall(sql)


def get_sync_project(project_id):
    return _client().fetchone(
        f"SELECT * FROM {_t('sync_project')} WHERE id=%s", (int(project_id),)
    )


def upsert_sync_project(payload):
    pid = payload.get('id')
    fields = {
        'name': (payload.get('name') or '').strip(),
        'approach_id': payload.get('approach_id'),
        'training_page_url': payload.get('training_page_url'),
        'local_root': payload.get('local_root'),
        'note': payload.get('note'),
        'enabled': 1 if payload.get('enabled', 1) else 0,
    }
    if not fields['name']:
        raise ValueError('项目名称不能为空')
    client = _client()
    if pid:
        cols = ', '.join(f"{k}=%s" for k in fields)
        client.execute(
            f"UPDATE {_t('sync_project')} SET {cols} WHERE id=%s",
            (*fields.values(), int(pid)),
        )
        return int(pid)
    return client.execute_returning_id(
        f"""INSERT INTO {_t('sync_project')}
            (name, approach_id, training_page_url, local_root, note, enabled)
            VALUES (%s,%s,%s,%s,%s,%s)""",
        tuple(fields.values()),
    )


def delete_sync_project(project_id):
    client = _client()
    client.execute(
        f"DELETE FROM {_t('platform_train_model')} WHERE project_id=%s", (int(project_id),)
    )
    ds = client.fetchall(
        f"SELECT id FROM {_t('sync_dataset')} WHERE project_id=%s", (int(project_id),)
    )
    for row in ds:
        client.execute(f"DELETE FROM {_t('dataset_item')} WHERE dataset_id=%s", (int(row['id']),))
    client.execute(f"DELETE FROM {_t('sync_dataset')} WHERE project_id=%s", (int(project_id),))
    return client.execute(f"DELETE FROM {_t('sync_project')} WHERE id=%s", (int(project_id),))


def list_sync_datasets(project_id=None, enabled_only=False):
    where, args = [], []
    if project_id:
        where.append("project_id=%s")
        args.append(int(project_id))
    if enabled_only:
        where.append("enabled=1")
    sql = f"SELECT * FROM {_t('sync_dataset')}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY project_id, name"
    return _client().fetchall(sql, tuple(args))


def get_sync_dataset(dataset_id):
    return _client().fetchone(
        f"SELECT * FROM {_t('sync_dataset')} WHERE id=%s", (int(dataset_id),)
    )


def upsert_sync_dataset(payload):
    did = payload.get('id')
    fields = {
        'project_id': int(payload.get('project_id') or 0),
        'name': (payload.get('name') or '').strip(),
        'source_type': (payload.get('source_type') or 'dataset').strip(),
        'source_id': int(payload.get('source_id') or 0),
        'data_view_url': payload.get('data_view_url'),
        'local_dir': (payload.get('local_dir') or '').strip(),
        'split_subdirs': 1 if payload.get('split_subdirs') else 0,
        'strip_prefix': 1 if payload.get('strip_prefix', 1) else 0,
        'write_db': 1 if payload.get('write_db', True) else 0,
        'enabled': 1 if payload.get('enabled', 1) else 0,
    }
    if not fields['project_id']:
        raise ValueError('project_id 不能为空')
    if not fields['name']:
        raise ValueError('数据集名称不能为空')
    if fields['source_type'] not in ('dataset', 'snapshot'):
        raise ValueError('source_type 须为 dataset 或 snapshot')
    if not fields['source_id']:
        raise ValueError('source_id 不能为空')
    if not fields['local_dir']:
        raise ValueError('local_dir 不能为空')
    client = _client()
    if did:
        cols = ', '.join(f"{k}=%s" for k in fields)
        client.execute(
            f"UPDATE {_t('sync_dataset')} SET {cols} WHERE id=%s",
            (*fields.values(), int(did)),
        )
        return int(did)
    return client.execute_returning_id(
        f"""INSERT INTO {_t('sync_dataset')}
            (project_id, name, source_type, source_id, data_view_url, local_dir,
             split_subdirs, strip_prefix, write_db, enabled)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        tuple(fields.values()),
    )


def update_sync_dataset_stats(dataset_id, remote_count=None, local_count=None,
                              last_sync_job_id=None, last_sync_error=None, last_sync_at=True):
    sets, args = [], []
    if remote_count is not None:
        sets.append('remote_count=%s'); args.append(int(remote_count))
    if local_count is not None:
        sets.append('local_count=%s'); args.append(int(local_count))
    if last_sync_job_id is not None:
        sets.append('last_sync_job_id=%s'); args.append(int(last_sync_job_id))
    if last_sync_error is not None:
        sets.append('last_sync_error=%s'); args.append(last_sync_error)
    if last_sync_at:
        sets.append('last_sync_at=NOW()')
    if not sets:
        return 0
    args.append(int(dataset_id))
    return _client().execute(
        f"UPDATE {_t('sync_dataset')} SET {', '.join(sets)} WHERE id=%s", tuple(args)
    )


def delete_sync_dataset(dataset_id):
    client = _client()
    client.execute(f"DELETE FROM {_t('dataset_item')} WHERE dataset_id=%s", (int(dataset_id),))
    return client.execute(f"DELETE FROM {_t('sync_dataset')} WHERE id=%s", (int(dataset_id),))


def upsert_dataset_item(dataset_id, remote_item_id, file_name, local_path=None,
                        object_key=None, split_type=None, annotations=None,
                        box_count=0, remote_mtime=None, source_detail_id=None,
                        product_no=None, product_id=None, product_type=None,
                        position=None, platform_c_time=None, trace_status=None):
    ann_json = _json_dump(annotations)
    client = _client()
    existing = client.fetchone(
        f"SELECT id FROM {_t('dataset_item')} WHERE dataset_id=%s AND remote_item_id=%s",
        (int(dataset_id), int(remote_item_id)),
    )
    if existing:
        return client.execute(
            f"""UPDATE {_t('dataset_item')}
                SET file_name=%s, local_path=%s, object_key=%s, split_type=%s,
                    annotations=%s, box_count=%s, remote_mtime=%s,
                    source_detail_id=%s, product_no=%s, product_id=%s, product_type=%s,
                    position=%s, platform_c_time=%s, trace_status=%s, synced_at=NOW()
                WHERE id=%s""",
            (file_name, local_path, object_key, split_type, ann_json,
             int(box_count or 0), remote_mtime,
             source_detail_id, product_no, product_id, product_type,
             position, platform_c_time, trace_status,
             int(existing['id'])),
        )
    return client.execute_returning_id(
        f"""INSERT INTO {_t('dataset_item')}
            (dataset_id, remote_item_id, file_name, local_path, object_key,
             split_type, annotations, box_count, remote_mtime,
             source_detail_id, product_no, product_id, product_type,
             position, platform_c_time, trace_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (int(dataset_id), int(remote_item_id), file_name, local_path, object_key,
         split_type, ann_json, int(box_count or 0), remote_mtime,
         source_detail_id, product_no, product_id, product_type,
         position, platform_c_time, trace_status),
    )


def update_dataset_item_provenance(item_id, prov):
    """更新单条样本溯源字段。"""
    prov = prov or {}
    return _client().execute(
        f"""UPDATE {_t('dataset_item')}
            SET source_detail_id=%s, product_no=%s, product_id=%s, product_type=%s,
                position=%s, platform_c_time=%s, trace_status=%s
            WHERE id=%s""",
        (
            prov.get('source_detail_id'),
            prov.get('product_no'),
            prov.get('product_id'),
            prov.get('product_type'),
            prov.get('position'),
            prov.get('platform_c_time'),
            prov.get('trace_status'),
            int(item_id),
        ),
    )


def _dataset_item_filter_clauses(filters=None):
    """构建 dataset_item 查询 WHERE 子句。"""
    filters = filters or {}
    where = ['dataset_id=%s']
    args = [int(filters['dataset_id'])]
    q = str(filters.get('q') or '').strip()
    if q:
        like = f'%{q}%'
        where.append(
            '(file_name LIKE %s OR product_no LIKE %s OR product_type LIKE %s '
            'OR object_key LIKE %s OR position LIKE %s)'
        )
        args.extend([like, like, like, like, like])
    sn = str(filters.get('product_no') or '').strip()
    if sn:
        where.append('product_no LIKE %s')
        args.append(f'%{sn}%')
    ptype = str(filters.get('product_type') or '').strip()
    if ptype:
        where.append('product_type LIKE %s')
        args.append(f'%{ptype}%')
    trace = str(filters.get('trace_status') or '').strip()
    if trace:
        where.append('trace_status=%s')
        args.append(trace)
    start = filters.get('start')
    if start:
        where.append('platform_c_time >= %s')
        args.append(start)
    end = filters.get('end')
    if end:
        where.append('platform_c_time <= %s')
        args.append(end)
    return where, args


def count_dataset_items(dataset_id, filters=None):
    flt = dict(filters or {})
    flt['dataset_id'] = int(dataset_id)
    where, args = _dataset_item_filter_clauses(flt)
    row = _client().fetchone(
        f"SELECT COUNT(*) AS n FROM {_t('dataset_item')} WHERE {' AND '.join(where)}",
        tuple(args),
    )
    return int(row['n']) if row else 0


def list_dataset_items(dataset_id, limit=100, offset=0, filters=None):
    flt = dict(filters or {})
    flt['dataset_id'] = int(dataset_id)
    where, args = _dataset_item_filter_clauses(flt)
    args.extend([int(limit), int(offset)])
    return _client().fetchall(
        f"SELECT * FROM {_t('dataset_item')} WHERE {' AND '.join(where)} "
        f"ORDER BY platform_c_time DESC, id DESC LIMIT %s OFFSET %s",
        tuple(args),
    )


def dataset_item_trace_summary(dataset_id):
    """按 trace_status 统计样本溯源覆盖率。"""
    rows = _client().fetchall(
        f"""SELECT trace_status, COUNT(*) AS n FROM {_t('dataset_item')}
            WHERE dataset_id=%s GROUP BY trace_status""",
        (int(dataset_id),),
    )
    summary = {'total': 0, 'matched': 0, 'filename': 0, 'fuzzy': 0, 'sn_only': 0, 'path_only': 0, 'unmatched': 0, 'unknown': 0}
    for row in rows or []:
        st = str(row.get('trace_status') or 'unknown').strip() or 'unknown'
        n = int(row.get('n') or 0)
        summary['total'] += n
        if st in summary:
            summary[st] = n
        else:
            summary['unknown'] += n
    summary['traced'] = summary['matched'] + summary['filename'] + summary['fuzzy'] + summary['sn_only']
    return summary


# ── 筛选批次（捞图 → 外部筛选 → 归档）────────────────────────────

CURATION_STATUSES = (
    'created', 'exported', 'imported', 'archived',
    'handoff_ready', 'handoff_done', 'closed',
)
CURATION_DECISIONS = ('pending', 'keep', 'reject')


def insert_curation_batch(row):
    sql = f"""
        INSERT INTO {_t('curation_batch')}
            (batch_code, source_task_id, strategy_id, strategy_name, data_source, intent_type,
             status, reviewer, note, total_count, keep_count, reject_count, pending_count)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    args = (
        row['batch_code'], row['source_task_id'],
        row.get('strategy_id'), row.get('strategy_name'), row.get('data_source') or 'detail',
        row.get('intent_type') or 'daily_ng',
        row.get('status') or 'created', row.get('reviewer'), row.get('note'),
        int(row.get('total_count') or 0), int(row.get('keep_count') or 0),
        int(row.get('reject_count') or 0), int(row.get('pending_count') or 0),
    )
    return _client().execute_returning_id(sql, args)


def update_curation_batch(batch_id, **fields):
    allowed = {
        'status', 'reviewer', 'note', 'total_count', 'keep_count', 'reject_count',
        'pending_count', 'export_dir', 'archive_dir', 'handoff_dir', 'sync_dataset_id',
        'exported_at', 'imported_at', 'archived_at', 'handoff_at', 'intent_type',
    }
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"`{k}`=%s")
        args.append(v)
    if not sets:
        return 0
    args.append(int(batch_id))
    return _client().execute(
        f"UPDATE {_t('curation_batch')} SET {', '.join(sets)} WHERE id=%s",
        tuple(args),
    )


def get_curation_batch(batch_id):
    return _client().fetchone(f"SELECT * FROM {_t('curation_batch')} WHERE id=%s", (int(batch_id),))


def get_curation_batch_by_code(batch_code):
    return _client().fetchone(
        f"SELECT * FROM {_t('curation_batch')} WHERE batch_code=%s",
        (str(batch_code),),
    )


def list_curation_batches(status=None, limit=100, offset=0):
    sql = f"SELECT * FROM {_t('curation_batch')}"
    args = []
    if status:
        sql += " WHERE status=%s"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
    args.extend([int(limit), int(offset)])
    return _client().fetchall(sql, tuple(args))


def count_curation_batches(status=None):
    sql = f"SELECT COUNT(*) AS c FROM {_t('curation_batch')}"
    args = []
    if status:
        sql += " WHERE status=%s"
        args.append(status)
    row = _client().fetchone(sql, tuple(args) if args else None)
    return int(row.get('c') or 0) if row else 0


def insert_curation_items_batch(rows):
    if not rows:
        return 0
    sql = f"""
        INSERT INTO {_t('curation_item')}
            (batch_id, batch_row_id, seq, img_name, img_path, product_no, product_type,
             check_status, categories_summary, decision, disposition, need_platform_label, source_meta)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    args_list = []
    for r in rows:
        args_list.append((
            int(r['batch_id']), r['batch_row_id'], int(r.get('seq') or 0),
            r.get('img_name'), r.get('img_path'), r.get('product_no'),
            r.get('product_type'), r.get('check_status'), r.get('categories_summary'),
            r.get('decision') or 'pending', r.get('disposition'), 1 if r.get('need_platform_label') else 0,
            _json_dump(r.get('source_meta')),
        ))
    return _client().executemany(sql, args_list)


def list_curation_items(batch_id, decision=None, limit=5000, offset=0):
    sql = f"SELECT * FROM {_t('curation_item')} WHERE batch_id=%s"
    args = [int(batch_id)]
    if decision:
        sql += " AND decision=%s"
        args.append(decision)
    sql += " ORDER BY seq ASC LIMIT %s OFFSET %s"
    args.extend([int(limit), int(offset)])
    rows = _client().fetchall(sql, tuple(args))
    for r in rows:
        r['source_meta'] = _json_load(r.get('source_meta'))
    return rows


def count_curation_items(batch_id, decision=None):
    sql = f"SELECT COUNT(*) AS c FROM {_t('curation_item')} WHERE batch_id=%s"
    args = [int(batch_id)]
    if decision:
        sql += " AND decision=%s"
        args.append(decision)
    row = _client().fetchone(sql, tuple(args))
    return int(row.get('c') or 0) if row else 0


def delete_curation_items_by_batch(batch_id):
    return _client().execute(
        f"DELETE FROM {_t('curation_item')} WHERE batch_id=%s",
        (int(batch_id),),
    )


def delete_curation_batch(batch_id):
    return _client().execute(
        f"DELETE FROM {_t('curation_batch')} WHERE id=%s",
        (int(batch_id),),
    )


def update_curation_item_decision(
    batch_id, batch_row_id, decision, reject_reason=None, note=None,
    disposition=None, need_platform_label=None,
):
    sets = ['decision=%s', 'reject_reason=%s', 'note=%s']
    args = [decision, reject_reason, note]
    if disposition is not None:
        sets.append('disposition=%s')
        args.append(disposition)
    if need_platform_label is not None:
        sets.append('need_platform_label=%s')
        args.append(1 if need_platform_label else 0)
    args.extend([int(batch_id), batch_row_id])
    return _client().execute(
        f"""UPDATE {_t('curation_item')}
            SET {', '.join(sets)}
            WHERE batch_id=%s AND batch_row_id=%s""",
        tuple(args),
    )


def recompute_curation_counts(batch_id):
    client = _client()
    bid = int(batch_id)
    rows = client.fetchall(
        f"SELECT decision, COUNT(*) AS c FROM {_t('curation_item')} WHERE batch_id=%s GROUP BY decision",
        (bid,),
    )
    counts = {'keep': 0, 'reject': 0, 'pending': 0}
    for r in rows:
        d = str(r.get('decision') or 'pending')
        if d in counts:
            counts[d] = int(r.get('c') or 0)
    total = counts['keep'] + counts['reject'] + counts['pending']
    update_curation_batch(
        bid,
        total_count=total,
        keep_count=counts['keep'],
        reject_count=counts['reject'],
        pending_count=counts['pending'],
    )
    return {'total': total, **counts}


# ── 平台训练模型缓存（Magic-Fox 训练页抓取）────────────────────────

def list_platform_train_models(project_id):
    return _client().fetchall(
        f"SELECT * FROM {_t('platform_train_model')} WHERE project_id=%s ORDER BY train_id DESC",
        (int(project_id),),
    )


def get_platform_train_model(project_id, train_id):
    return _client().fetchone(
        f"SELECT * FROM {_t('platform_train_model')} WHERE project_id=%s AND train_id=%s",
        (int(project_id), int(train_id)),
    )


def find_platform_train_model_by_train_id(train_id, approach_id=None):
    sql = f"""
        SELECT m.* FROM {_t('platform_train_model')} m
        JOIN {_t('sync_project')} p ON p.id = m.project_id
        WHERE m.train_id=%s
    """
    args = [int(train_id)]
    if approach_id is not None:
        sql += " AND p.approach_id=%s"
        args.append(int(approach_id))
    sql += " ORDER BY m.synced_at DESC LIMIT 1"
    return _client().fetchone(sql, tuple(args))


def replace_platform_train_models(project_id, rows):
    client = _client()
    pid = int(project_id)
    client.execute(f"DELETE FROM {_t('platform_train_model')} WHERE project_id=%s", (pid,))
    n = 0
    for row in rows or []:
        client.execute(
            f"""INSERT INTO {_t('platform_train_model')}
                (project_id, train_id, model_name, model_type, train_duration, creator,
                 train_progress, snapshot_note, remark, c_time_platform)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                pid,
                int(row.get('train_id') or 0),
                row.get('model_name'),
                row.get('model_type'),
                row.get('train_duration'),
                row.get('creator'),
                row.get('train_progress'),
                row.get('snapshot_note'),
                row.get('remark'),
                row.get('c_time'),
            ),
        )
        n += 1
    return n


# ── 历史回跑编排 ───────────────────────────────────────────────────

def create_replay_run(spec_json):
    client = _client()
    client.execute(
        f"""INSERT INTO {_t('replay_run')} (status, stage, spec_json)
            VALUES ('pending', 'init', %s)""",
        (_json_dump(spec_json),),
    )
    return client.last_insert_id()


def get_replay_run(run_id):
    row = _client().fetchone(f"SELECT * FROM {_t('replay_run')} WHERE id=%s", (int(run_id),))
    if row:
        row['spec_json'] = _json_load(row.get('spec_json'))
        row['result_json'] = _json_load(row.get('result_json'))
    return row


def update_replay_run(run_id, **fields):
    allowed = {
        'status', 'stage', 'stage1_task_id', 'predict_job_id', 'stage2_task_id',
        'curation_batch_id', 'result_json', 'error', 'spec_json',
    }
    sets, args = [], []
    for key, val in fields.items():
        if key not in allowed:
            continue
        sets.append(f"`{key}`=%s")
        if key in ('result_json', 'spec_json') and val is not None and not isinstance(val, str):
            args.append(_json_dump(val))
        else:
            args.append(val)
    if not sets:
        return 0
    args.append(int(run_id))
    return _client().execute(
        f"UPDATE {_t('replay_run')} SET {', '.join(sets)} WHERE id=%s",
        tuple(args),
    )


def list_replay_runs(limit=50, offset=0):
    rows = _client().fetchall(
        f"SELECT * FROM {_t('replay_run')} ORDER BY id DESC LIMIT %s OFFSET %s",
        (int(limit), int(offset)),
    )
    for r in rows:
        r['spec_json'] = _json_load(r.get('spec_json'))
        r['result_json'] = _json_load(r.get('result_json'))
    return rows
