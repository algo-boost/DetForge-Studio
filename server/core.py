"""Shared backend services and helpers."""
from flask import current_app, jsonify, send_file, send_from_directory
import pandas as pd
import pymysql
import os
import re
import time
import threading
import traceback
import io
import sys
from contextlib import contextmanager
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import shutil
import json
import uuid
import zipfile
from urllib.parse import quote_plus
from studio.export.csv2coco import csv2coco, build_coco_info, sync_coco_image_file_names
from studio.query.row_fields import enrich_df_product_fields, normalize_result_row_fields
from studio.query.python_builtins import build_python_namespace
from studio.flow.flow_registry import build_node_registry
from studio.flow.flow_compiler import (
    compile_flow, compile_filter_rules, combine_python_code, combine_execution_python,
    resolve_strategy_python, compile_sample_code, build_random_sample_function,
    references_random_sample,
    extract_rules_compile_flow, normalize_strategy, has_inline_sampling,
    has_filter_rules_definition, references_filter_rules,
    FILTER_RULES_FUNC, PROCESS_FUNC,
)
from studio.flow.flow_schema import prepare_strategy, validate_flow, FLOW_IR_VERSION
from studio.query.defect_categories import (
    apply_categories_to_templates,
    fetch_defect_categories,
    merge_id2name,
)
from studio.query.platform_paths import resolve_platform_paths, sync_img_base_path
from studio.query.deployed_models import fetch_deployed_models, fetch_training_models
from studio.query.pipeline_rules import fetch_pipelines, fetch_pipeline_filter_rules, fetch_pipeline_nodes

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# 默认配置
DEFAULT_CONFIG = {
    'db_host': 'localhost',
    'db_user': 'root',
    'db_password': '',
    'db_database': 'vision_backend',
    'forge_database': 'detforge',  # 写库（同实例独立库；存模型/作业/预测结果/质检）
    'img_base_path': 'E:/magic_fox_ai_20250826/resources/backend/local_file/',
    'img_path_mode': 'concat',  # 'full_path' 或 'concat'
    'img_path_field': 'origin_object_key',  # 用于拼接的字段名
    'img_full_path_field': 'local_pic_url',  # 完整路径字段名
    'default_sql': "SELECT * FROM `product_detection_detail_result` WHERE ext like '%脏污%' AND c_time BETWEEN '${START_TIME}' AND '${END_TIME}'",
    'archive_base_path': '',
    'handoff_root': '',
    'defect_approach_id': 18,
    'platform_root_drive': 'D',
    # 预测：外部 Python 子进程（DetUnify-Studio）；留空 predict_python_executable 则进程内 import
    'detunify_studio_root': '',
    'predict_python_executable': '',
    'predict_script': '',
    'coco_visualizer_root': '',
    'viz_open_mode': 'prompt',  # off | prompt | auto
    'device_max_concurrency': 1,
    # Magic-Fox 数据集同步（认证均在设置页配置，写入 config.json）
    'dataset_sync_root': 'datasets',
    'magic_fox_api_base': 'https://www.ai.magic-fox.com/api/v1',
    'magic_fox_auth_mode': 'password',  # password | token
    'magic_fox_username': '',
    'magic_fox_password': '',
    'magic_fox_access_token': '',
    'dataset_sync_roots': [],
    # Magic-Fox 平台预测（model_validation）上传与批处理
    'platform_predict_batch_size': 10,
    'platform_upload_chunk': 3,
    'platform_upload_connect_timeout': 30,
    'platform_upload_read_timeout': 1800,
    'platform_upload_write_timeout': 1800,
    'id2name': {
        '0': '其他', '1': '划伤', '2': '压痕', 
        '3': '吊紧', '4': '异物外漏', '5': '折痕', '6': '抛线',
        '7': '拼接间隙', '8': '水渍', '9': '烫伤', '10': '破损', 
        '11': '碰伤', '12': '红标签', '13': '线头', '14': '脏污', 
        '15': '褶皱(T型)', '16': '褶皱（重度）', '17': '重跳针'
    }
}

DEFAULT_SAMPLE_SIZE = 300
RANDOM_SAMPLE_SEED = 42

_defect_category_cache = {'ts': 0.0, 'bundle': None}
DEFECT_CATEGORY_CACHE_TTL = 300


def _fetch_approaches(client):
    """查询 approach 列表，供设置页下拉选择。"""
    if client is None or client.connection is None:
        return []
    try:
        df = client.query('SELECT id, approach_name, approach_type FROM approach ORDER BY id')
        if df is None or df.empty:
            return []
        return [
            {
                'id': int(row.get('id') or 0),
                'approach_name': str(row.get('approach_name') or '').strip(),
                'approach_type': str(row.get('approach_type') or '').strip(),
            }
            for _, row in df.iterrows()
        ]
    except Exception:
        return []


def get_defect_categories_bundle(force_refresh=False, approach_id_override=None):
    """加载缺陷类别（带短时缓存）。"""
    global _defect_category_cache
    now = time.time()
    if (
        not force_refresh
        and approach_id_override is None
        and _defect_category_cache['bundle']
        and now - _defect_category_cache['ts'] < DEFECT_CATEGORY_CACHE_TTL
    ):
        return _defect_category_cache['bundle']

    config = load_config()
    aid = int(
        approach_id_override
        if approach_id_override is not None
        else config.get('defect_approach_id', DEFAULT_CONFIG.get('defect_approach_id', 18))
    )
    fallback = list((config.get('id2name') or DEFAULT_CONFIG['id2name']).values())
    client = get_db_client()
    bundle = fetch_defect_categories(
        client,
        approach_id=aid,
        fallback=fallback,
    )
    bundle['id2name'] = merge_id2name(config.get('id2name', DEFAULT_CONFIG['id2name']), bundle['categories'])
    bundle['approach_id'] = aid
    if approach_id_override is None:
        _defect_category_cache = {'ts': now, 'bundle': bundle}
    return bundle


def get_effective_id2name():
    return get_defect_categories_bundle().get('id2name') or load_config().get('id2name', DEFAULT_CONFIG['id2name'])


def get_platform_paths_bundle(force_refresh=False):
    """从数据库 local_pic_url 推断平台根目录（可指定盘符）。"""
    config = load_config()
    client = get_db_client()
    return resolve_platform_paths(client, config)


def apply_random_sample(df, sample_size=None, seed=RANDOM_SAMPLE_SEED):
    """在最终 DataFrame 上随机采样；行数不足时返回全部。"""
    if sample_size is None:
        return df
    sample_size = int(sample_size)
    if sample_size <= 0 or len(df) <= sample_size:
        return df.reset_index(drop=True)
    return df.sample(n=sample_size, random_state=seed).reset_index(drop=True)


def parse_sample_size(value, default=DEFAULT_SAMPLE_SIZE):
    if value is None or value == '':
        return default
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def sample_size_from_env(env_ctx):
    """仅当 env 中显式提供 SAMPLE_SIZE 时才返回采样数，否则不二次采样。"""
    if not env_ctx or 'SAMPLE_SIZE' not in env_ctx:
        return None
    raw = env_ctx.get('SAMPLE_SIZE')
    if raw is None or str(raw).strip() == '':
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def parse_random_seed(value, default=RANDOM_SAMPLE_SEED):
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# 配置管理函数
def read_config_file_raw():
    """读取 config.json 原始 JSON（不解密）。"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f'⚠️ 读取 config.json 失败: {e}')
        return {}


def _merge_file_config(file_config: dict) -> dict:
    merged_config = DEFAULT_CONFIG.copy()
    merged_config.update(file_config or {})
    if not isinstance(merged_config.get('id2name'), dict):
        merged_config['id2name'] = DEFAULT_CONFIG['id2name'].copy()
    else:
        id2name = DEFAULT_CONFIG['id2name'].copy()
        id2name.update(merged_config['id2name'])
        merged_config['id2name'] = id2name
    return merged_config


def secret_field_set_on_disk(key: str) -> bool:
    """磁盘上是否已有该敏感字段（含 enc:v1 密文）。"""
    from studio.config_crypto import is_encrypted
    val = read_config_file_raw().get(key)
    if not isinstance(val, str) or not str(val).strip():
        return False
    return is_encrypted(val) or bool(str(val).strip())


def preserve_secrets_for_save(config: dict, incoming: dict | None = None) -> dict:
    """保存前：表单留空时保留内存/磁盘已有口令，避免误写成空或 DEFAULT。"""
    from studio.config_crypto import is_encrypted, SENSITIVE_KEYS
    incoming = incoming or {}
    out = dict(config)
    raw = read_config_file_raw()
    for key in SENSITIVE_KEYS:
        if str(incoming.get(key) or '').strip():
            continue
        if str(out.get(key) or '').strip():
            continue
        disk = raw.get(key)
        if isinstance(disk, str) and (is_encrypted(disk) or str(disk).strip()):
            out[key] = disk
    return out


def load_config():
    """加载配置文件（敏感字段自动解密；解密失败仍保留文件中的非敏感项）。"""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        file_config = read_config_file_raw()
        if not file_config:
            return DEFAULT_CONFIG.copy()
        merged_config = _merge_file_config(file_config)
        from studio.config_crypto import decrypt_config_secrets
        return decrypt_config_secrets(merged_config)
    except json.JSONDecodeError as e:
        print(f'⚠️ config.json 格式错误: {e}，使用默认配置')
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f'⚠️ 加载配置文件失败: {e}')
        try:
            return _merge_file_config(read_config_file_raw())
        except Exception:
            return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置文件（敏感字段加密写入磁盘）。"""
    try:
        from studio.config_crypto import encrypt_config_secrets, encryption_available
        to_write = dict(config or {})
        to_write.pop('_config_decrypt_errors', None)
        to_write = encrypt_config_secrets(to_write)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_write, f, ensure_ascii=False, indent=4)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass
        if not encryption_available():
            print('⚠️ 未安装 cryptography，config.json 敏感字段以明文保存（pip install cryptography）')
        return True
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")
        return False

# 加载配置
APP_CONFIG = load_config()

# 数据库配置（优先使用配置文件，其次环境变量，最后默认值）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', APP_CONFIG.get('db_host', DEFAULT_CONFIG['db_host'])),
    'user': os.getenv('DB_USER', APP_CONFIG.get('db_user', DEFAULT_CONFIG['db_user'])),
    'password': os.getenv('DB_PASSWORD', APP_CONFIG.get('db_password', DEFAULT_CONFIG['db_password'])),
    'database': os.getenv('DB_DATABASE', APP_CONFIG.get('db_database', DEFAULT_CONFIG['db_database']))
}

# 图片基础路径配置
IMG_BASE_PATH = os.getenv('IMG_BASE_PATH', APP_CONFIG.get('img_base_path', DEFAULT_CONFIG['img_base_path']))


class MySQLClient:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self._engine = None
        # pymysql 连接非线程安全；worker 多线程 + 心跳线程共享同一全局 client，
        # 用可重入锁串行化所有 DB 操作，避免游标交叉导致的数据错乱。
        self._lock = threading.RLock()
        self.last_query_error = None
        self.connect()

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4'
            )
            print(f"✅ 成功连接到MySQL数据库: {self.database}")
        except Exception as e:
            print(f"❌ 连接数据库失败: {e}")
            self.connection = None

    def ensure_alive(self):
        """Ping 连接；断开则重连（不使用已弃用的 reconnect 参数）。"""
        if self.connection is None:
            self.connect()
            return self.connection is not None
        try:
            self.connection.ping(reconnect=False)
            return True
        except Exception:
            self.connection = None
            self.connect()
            return self.connection is not None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from sqlalchemy import create_engine
            url = (
                f"mysql+pymysql://{quote_plus(self.user)}:{quote_plus(self.password)}"
                f"@{self.host}/{self.database}?charset=utf8mb4"
            )
            self._engine = create_engine(
                url, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=3600,
            )
        except Exception as e:
            print(f"⚠️ SQLAlchemy engine 创建失败，回退 pymysql: {e}")
            self._engine = None
        return self._engine

    @contextmanager
    def _borrow_conn(self):
        """从连接池借连接（优先 SQLAlchemy pool，回退单连接）。"""
        engine = self._get_engine()
        if engine is not None:
            conn = engine.raw_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            if not self.ensure_alive():
                raise RuntimeError('数据库未连接')
            yield self.connection
            self.connection.commit()

    def query(self, sql):
        with self._lock:
            if not self.ensure_alive():
                print("❌ 重新连接数据库失败")
                return None
            try:
                engine = self._get_engine()
                if engine is not None:
                    from sqlalchemy import text
                    # text() 避免 LIKE '%...%' 被 pandas/SQLAlchemy 当作 pyformat 占位符
                    df = pd.read_sql(text(sql), engine)
                else:
                    df = pd.read_sql(sql, self.connection)
                self.last_query_error = None
                return df
            except Exception as e:
                print(f"❌ 查询失败: {e}")
                self.last_query_error = str(e)
                self.connection = None
                self._engine = None
                return None

    # ── 写库 / 取数（pymysql 直连，支持跨库限定名 detforge.xxx）────────
    def execute(self, sql, args=None):
        """执行写操作（INSERT/UPDATE/DELETE/DDL），返回受影响行数。"""
        with self._lock:
            with self._borrow_conn() as conn:
                with conn.cursor() as cur:
                    return cur.execute(sql, args or ())

    def execute_returning_id(self, sql, args=None):
        """执行 INSERT 并返回自增主键 lastrowid。"""
        with self._lock:
            with self._borrow_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, args or ())
                    return cur.lastrowid

    def executemany(self, sql, args_list):
        """批量写；args_list 为空时直接返回 0。"""
        args_list = list(args_list or [])
        if not args_list:
            return 0
        with self._lock:
            with self._borrow_conn() as conn:
                with conn.cursor() as cur:
                    return cur.executemany(sql, args_list)

    def fetchall(self, sql, args=None):
        """以字典列表返回查询结果（用于写库表读取）。"""
        with self._lock:
            with self._borrow_conn() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cur:
                    cur.execute(sql, args or ())
                    return list(cur.fetchall())

    def fetchone(self, sql, args=None):
        rows = self.fetchall(sql, args)
        return rows[0] if rows else None

    def execute_script(self, script):
        """执行以分号分隔的多语句 DDL 脚本（建库/建表）。"""
        with self._lock:
            with self._borrow_conn() as conn:
                statements = [s.strip() for s in script.split(';') if s.strip()]
                with conn.cursor() as cur:
                    for stmt in statements:
                        cur.execute(stmt)
                return len(statements)

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            print("🔌 数据库连接已关闭")


# 全局数据库客户端
db_client = None


def resolve_db_password(cfg=None):
    """解析数据库口令（环境变量 > 已解密配置 > 磁盘密文）。"""
    env_pw = os.getenv('DB_PASSWORD')
    if env_pw is not None and str(env_pw).strip():
        return str(env_pw).strip()
    cfg = cfg or load_config()
    from studio.config_crypto import is_encrypted, resolve_secret_value
    pw = str(cfg.get('db_password') or '').strip()
    if pw:
        return pw
    disk = read_config_file_raw().get('db_password')
    if isinstance(disk, str) and disk.strip():
        if is_encrypted(disk):
            try:
                return resolve_secret_value(disk)
            except Exception:
                return ''
        return disk.strip()
    return ''


def get_db_client():
    global db_client, DB_CONFIG, APP_CONFIG
    APP_CONFIG = load_config()
    new_db = {
        'host': os.getenv('DB_HOST', APP_CONFIG.get('db_host', DEFAULT_CONFIG['db_host'])),
        'user': os.getenv('DB_USER', APP_CONFIG.get('db_user', DEFAULT_CONFIG['db_user'])),
        'password': resolve_db_password(APP_CONFIG),
        'database': os.getenv('DB_DATABASE', APP_CONFIG.get('db_database', DEFAULT_CONFIG['db_database'])),
    }
    DB_CONFIG = new_db

    stale = (
        db_client is None
        or db_client.host != new_db['host']
        or db_client.user != new_db['user']
        or db_client.password != new_db['password']
        or db_client.database != new_db['database']
    )
    if stale:
        if db_client is not None:
            db_client.close()
        db_client = MySQLClient(**new_db)
    else:
        db_client.ensure_alive()
    return db_client


def update_config_and_reconnect(new_config):
    """更新配置并重新连接数据库"""
    global db_client, DB_CONFIG, IMG_BASE_PATH, APP_CONFIG
    
    # 保存配置
    if save_config(new_config):
        APP_CONFIG = new_config
        DB_CONFIG = {
            'host': new_config.get('db_host', DEFAULT_CONFIG['db_host']),
            'user': new_config.get('db_user', DEFAULT_CONFIG['db_user']),
            'password': new_config.get('db_password', DEFAULT_CONFIG['db_password']),
            'database': new_config.get('db_database', DEFAULT_CONFIG['db_database'])
        }
        IMG_BASE_PATH = new_config.get('img_base_path', DEFAULT_CONFIG['img_base_path'])
        
        # 关闭旧连接
        if db_client:
            try:
                db_client.close()
            except:
                pass
            db_client = None
        
        # 创建新连接
        get_db_client()
        return True
    return False


def apply_img_paths(df):
    """根据配置为 DataFrame 添加 img_path 列"""
    global IMG_BASE_PATH
    # predict_result 表：img_path 已是服务器绝对路径，勿用 origin_object_key 覆盖
    if 'job_id' in df.columns and 'img_path' in df.columns:
        df['img_path'] = df['img_path'].apply(
            lambda v: str(v).strip() if pd.notna(v) and v else ''
        )
        return df

    config = load_config()
    IMG_BASE_PATH = config.get('img_base_path', DEFAULT_CONFIG['img_base_path'])
    img_path_mode = config.get('img_path_mode', DEFAULT_CONFIG['img_path_mode'])
    img_path_field = config.get('img_path_field', DEFAULT_CONFIG['img_path_field'])
    img_full_path_field = config.get('img_full_path_field', DEFAULT_CONFIG['img_full_path_field'])

    if img_path_mode == 'full_path':
        if img_full_path_field in df.columns:
            df['img_path'] = df[img_full_path_field].apply(
                lambda v: str(v) if pd.notna(v) and v else ''
            )
        elif 'local_pic_url' in df.columns:
            df['img_path'] = df['local_pic_url'].apply(
                lambda v: str(v) if pd.notna(v) and v else ''
            )
        elif 'img_path' not in df.columns:
            df['img_path'] = ''
    else:
        base_path = IMG_BASE_PATH
        base_ok = bool(base_path and os.path.isdir(str(base_path).rstrip('/\\')))
        field = img_path_field if img_path_field in df.columns else 'origin_object_key'
        if not base_ok and 'local_pic_url' in df.columns:
            df['img_path'] = df['local_pic_url'].apply(
                lambda v: str(v).replace('\\', '/') if pd.notna(v) and v else ''
            )
        elif field in df.columns:
            if base_path and not base_path.endswith(('/', '\\')):
                base_path += '/'
            df['img_path'] = df[field].apply(
                lambda v: base_path + str(v) if pd.notna(v) and v else ''
            )
        elif 'img_path' not in df.columns:
            df['img_path'] = ''
    return df


def execute_python_filter(
    df,
    code,
    capture_output=False,
    env_context=None,
    strategy=None,
    python_presets=None,
):
    """执行用户 Python 筛选代码，返回 (df, console_output, execution_time)"""
    from studio.query.env_context import normalize_env_dict, substitute_template
    from studio.query.python_preset_registry import build_execution_namespace

    code = (code or '').strip()
    if not code:
        return df, '', 0.0

    ctx = normalize_env_dict(env_context)
    if ctx:
        code = substitute_template(code, ctx)

    func_match = re.search(rf'def\s+{re.escape(PROCESS_FUNC)}\s*\(', code)
    if not func_match:
        raise ValueError(f'代码中未找到函数定义，请定义 def {PROCESS_FUNC}(df): ...')

    local_ns = build_execution_namespace(
        ctx,
        strategy=strategy,
        python_presets=python_presets,
        code=code,
    )
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    start = time.time()

    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        exec(code, local_ns)
        if PROCESS_FUNC not in local_ns:
            raise ValueError(f'请定义 def {PROCESS_FUNC}(df): ...')
        result = local_ns[PROCESS_FUNC](df.copy())

    elapsed = time.time() - start
    if not isinstance(result, pd.DataFrame):
        raise ValueError(f'函数 {PROCESS_FUNC} 必须返回 pandas DataFrame')

    result = result.reset_index(drop=True)
    console_output = stdout_buf.getvalue()
    err_output = stderr_buf.getvalue()
    if err_output:
        console_output = (console_output + '\n' + err_output).strip() if console_output else err_output

    if capture_output:
        return result, console_output, elapsed
    return result


def execute_filter_rules_only(df, rules_code, env_context=None, strategy=None):
    """仅执行 apply_filter_rules，用于预览筛选行数。"""
    from studio.query.python_preset_registry import build_execution_namespace

    rules_code = (rules_code or '').strip()
    if not rules_code:
        return df
    local_ns = build_execution_namespace(
        env_context,
        strategy=strategy,
        python_presets=['filter'],
        code=rules_code,
    )
    exec(rules_code, local_ns)
    if FILTER_RULES_FUNC not in local_ns:
        raise ValueError(f'规则代码中未找到 def {FILTER_RULES_FUNC}(df)')
    result = local_ns[FILTER_RULES_FUNC](df.copy())
    if not isinstance(result, pd.DataFrame):
        raise ValueError(f'{FILTER_RULES_FUNC} 必须返回 pandas DataFrame')
    return result.reset_index(drop=True)


def _compile_rules_from_flow(flow, templates):
    if not (flow or {}).get('nodes'):
        return ''
    rules_flow = extract_rules_compile_flow(flow)
    compiled = compile_filter_rules(rules_flow, templates)
    if compiled['valid'] and (compiled.get('python_code') or '').strip():
        return compiled['python_code'].strip()
    return ''


def _resolve_sample_code(data, templates, process_code=''):
    """仅当策略流含 random_sample 或 process_data 调用采样函数时附带 sample 辅助代码。"""
    from studio.flow.flow_compiler import _flow_has_random_sample, references_random_sample

    flow = data.get('flow') or {}
    if not _flow_has_random_sample(flow) and not references_random_sample(process_code):
        return ''
    sample_code = (data.get('sample_code') or '').strip()
    if not sample_code:
        sample_code = compile_sample_code(flow, templates)
    if not sample_code:
        sample_code = build_random_sample_function()
    return sample_code


def _resolve_query_python(data, templates):
    """从请求体解析用于执行的合并 Python 代码（规则 + 采样函数 + process_data）。"""
    process_code = (data.get('python_code') or '').strip()
    filter_rules_code = (data.get('filter_rules_code') or '').strip()
    flow = data.get('flow') or {}
    filter_mode = (data.get('filter_mode') or '').strip()

    if not filter_rules_code and filter_mode in ('flow', 'split', 'rules'):
        filter_rules_code = _compile_rules_from_flow(flow, templates)

    sample_code = _resolve_sample_code(data, templates, process_code)

    # 已含完整 apply_filter_rules 定义（含客户端预合并代码）
    if process_code and has_filter_rules_definition(process_code):
        return process_code

    # process_data 调用了 apply_filter_rules，需合并规则代码
    if process_code and references_filter_rules(process_code):
        if filter_rules_code:
            return combine_execution_python(filter_rules_code, sample_code, process_code)
        raise ValueError(
            f'代码调用了 {FILTER_RULES_FUNC}()，但未找到规则定义。'
            '请在「规则」模式配置筛选条件，或将 def apply_filter_rules(df) 写入代码。'
        )

    if process_code:
        return combine_execution_python('', sample_code, process_code)

    if filter_rules_code or sample_code:
        return combine_execution_python(filter_rules_code, sample_code, '')

    if filter_mode in ('flow', 'split', 'rules'):
        compiled = _compile_rules_from_flow(flow, templates)
        if compiled:
            return combine_execution_python(compiled, sample_code, '')
        raise ValueError('筛选规则为空，请添加至少一条规则或切换到「代码」模式')

    return ''


def _resolve_filter_rules_code(data, templates):
    """解析仅用于 apply_filter_rules 的代码。"""
    rules_code = (data.get('filter_rules_code') or '').strip()
    if rules_code:
        return rules_code
    flow = data.get('flow') or {}
    if flow.get('nodes'):
        rules_flow = extract_rules_compile_flow(flow)
        compiled = compile_filter_rules(rules_flow, templates)
        if compiled['valid']:
            return compiled['python_code']
    return ''


def build_query_task(df, query_meta=None):
    """保存查询结果到 exports 目录，返回 (result_data, task_id)"""
    df = df.reset_index(drop=True)
    df = apply_img_paths(df)
    df = enrich_df_product_fields(df)

    task_id = str(uuid.uuid4())
    task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
    os.makedirs(task_dir, exist_ok=True)

    if query_meta:
        meta_path = os.path.join(task_dir, 'query_meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(query_meta, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(task_dir, 'result.csv')
    df.to_csv(csv_path, index=False, encoding='utf-8')

    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    coco_data = None
    pred_ann_by_image = {}
    try:
        id2name_config = get_effective_id2name()
        csv2coco(csv_path, coco_path, id2name_config, query_meta=query_meta)
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        if (query_meta or {}).get('data_source') == 'predict_result':
            from studio.export.pred_coco_layout import load_pred_annotations_by_image_id
            pred_ann_by_image = load_pred_annotations_by_image_id(task_dir)
    except Exception as e:
        print(f"⚠️ COCO 转换警告: {e}")

    local_img_by_idx = {}
    try:
        for idx, row in df.iterrows():
            img_path = row.get('img_path', '')
            if pd.isna(img_path) or not img_path or not os.path.exists(img_path):
                if img_path and not pd.isna(img_path):
                    print(f"⚠️ 图片文件不存在: {img_path}")
                continue
            base = os.path.basename(str(img_path))
            dest_img_path = os.path.join(task_dir, f'{int(idx)}_{base}')
            shutil.copy2(img_path, dest_img_path)
            local_img_by_idx[int(idx)] = dest_img_path
    except Exception as e:
        print(f"⚠️ 复制图片警告: {e}")

    if os.path.isfile(coco_path):
        paths_by_id = dict(local_img_by_idx)
        for idx, row in df.iterrows():
            iid = int(idx)
            if iid in paths_by_id:
                continue
            raw = row.get('img_path', '')
            if raw is None or (hasattr(raw, '__float__') and pd.isna(raw)):
                continue
            p = str(raw).strip()
            if p and os.path.isfile(p):
                paths_by_id[iid] = os.path.abspath(p)
        if paths_by_id:
            try:
                if sync_coco_image_file_names(coco_path, paths_by_id, image_dir=task_dir):
                    with open(coco_path, 'r', encoding='utf-8') as f:
                        coco_data = json.load(f)
            except Exception as e:
                print(f"⚠️ COCO 图片路径同步警告: {e}")

    if (query_meta or {}).get('data_source') == 'predict_result' and 'id' not in df.columns:
        print('⚠️ 预测结果查询缺少 id 列，带框预览可能不可用，建议在 SQL 中包含 id')

    result_data = []
    image_meta_by_id = {}
    if coco_data:
        for img in coco_data.get('images', []):
            image_meta_by_id[int(img.get('id', -1))] = img

    for idx, row in df.iterrows():
        img_path = row.get('img_path', '')
        if pd.isna(img_path):
            img_path = ''
        img_path = str(img_path).strip() if img_path else ''
        local_path = local_img_by_idx.get(int(idx))
        if local_path and os.path.isfile(local_path):
            img_path = local_path
        img_name = os.path.basename(img_path) if img_path else ''

        annotations = []
        if pred_ann_by_image:
            annotations = pred_ann_by_image.get(int(idx), [])
        elif coco_data:
            image_id = int(idx)
            for ann in coco_data.get('annotations', []):
                if ann.get('image_id') == image_id:
                    annotations.append({
                        'bbox': ann.get('bbox', []),
                        'category': ann.get('category', ''),
                        'category_id': ann.get('category_id', 0),
                        'score': ann.get('score', 0)
                    })

        norm = normalize_result_row_fields(row)
        meta = image_meta_by_id.get(int(idx), {})

        entry = {
            'id': int(idx),
            'img_name': img_name,
            'img_path': img_path,
            'c_time': str(row.get('c_time', '')),
            'check_status': str(row.get('check_status', '')),
            'detection_result_status': str(row.get('detection_result_status', '')),
            'manual_check_status': str(row.get('manual_check_status', '')),
            'annotations': annotations,
            'product_no': norm['product_no'] or str(meta.get('product_no') or meta.get('SN') or '').strip(),
            'product_id': norm['product_id'] or str(meta.get('product_id') or '').strip(),
            'product_type': norm['product_type'] or str(meta.get('product_type') or '').strip(),
            'position': norm['position'] or str(meta.get('position') or '').strip(),
        }
        # 预测结果表：保留 DB 主键供带框预览
        raw_id = row.get('id')
        if raw_id is not None and not pd.isna(raw_id):
            if (query_meta or {}).get('data_source') == 'predict_result' or row.get('job_id') is not None:
                entry['predict_result_id'] = int(raw_id)
        if (query_meta or {}).get('data_source') == 'predict_result':
            if row.get('box_count') is not None and not pd.isna(row.get('box_count')):
                entry['box_count'] = int(row.get('box_count'))
            if row.get('max_score') is not None and not pd.isna(row.get('max_score')):
                entry['max_score'] = float(row.get('max_score'))
        if norm['defect_type']:
            entry['defect_type'] = norm['defect_type']
        if entry['product_no']:
            entry['SN'] = entry['product_no']
        # 去掉空字符串 optional 字段
        entry = {k: v for k, v in entry.items() if v != '' or k in (
            'id', 'img_name', 'img_path', 'c_time', 'check_status',
            'detection_result_status', 'manual_check_status', 'annotations',
        )}
        result_data.append(entry)

    return result_data, task_id


