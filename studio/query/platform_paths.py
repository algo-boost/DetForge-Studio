"""从 vision_backend 推断 Magic-Fox 平台根目录与 local_file 前缀。"""
import re

LOCAL_FILE_MARKER = '/resources/backend/local_file/'


def _norm_root(root):
    if not root:
        return ''
    return str(root).replace('\\', '/').rstrip('/')


def _drive_letter(value):
    if not value:
        return ''
    m = re.match(r'^([A-Za-z]):', str(value).strip().replace('\\', '/'))
    return m.group(1).upper() if m else ''


def fetch_platform_roots(client, drive=None):
    """
    从 product_detection_detail_result.local_pic_url 统计平台根目录。
    drive: 可选盘符过滤，如 'D' 只返回 D: 盘记录。
    """
    if client is None or client.connection is None:
        return []

    drive_filter = ''
    if drive:
        d = _drive_letter(f'{drive}:')
        if d:
            # pandas read_sql 会把 SQL 里的 % 当作占位符，LIKE 子句需写 %%
            drive_filter = f"AND (local_pic_url LIKE '{d}:%%' OR local_pic_url LIKE '{d}:/%%')"

    marker = LOCAL_FILE_MARKER.replace("'", "''")
    sql = f"""
        SELECT
          SUBSTRING_INDEX(REPLACE(local_pic_url,'\\\\','/'), '{marker}', 1) AS platform_root,
          COUNT(*) AS sample_count
        FROM product_detection_detail_result
        WHERE local_pic_url IS NOT NULL AND local_pic_url != ''
          AND local_pic_url LIKE '%%{marker}%%'
          {drive_filter}
        GROUP BY platform_root
        ORDER BY sample_count DESC
    """
    df = client.query(sql)
    if df is None or df.empty:
        return []

    out = []
    for _, row in df.iterrows():
        root = _norm_root(row.get('platform_root'))
        if not root:
            continue
        out.append({
            'platform_root': root,
            'local_file_base': f'{root}{LOCAL_FILE_MARKER}',
            'sample_count': int(row.get('sample_count') or 0),
        })
    return out


def resolve_platform_paths(client, config=None):
    """
    解析当前应使用的平台路径。
    盘符优先级：config.platform_root_drive → img_base_path 盘符 → 全库众数。
    """
    config = config or {}
    drive = config.get('platform_root_drive') or _drive_letter(config.get('img_base_path', ''))

    candidates = fetch_platform_roots(client, drive=drive or None)
    if not candidates and drive:
        candidates = fetch_platform_roots(client)

    chosen = candidates[0] if candidates else {}
    root = chosen.get('platform_root', '')
    local_file_base = chosen.get('local_file_base', '')
    resolved_drive = _drive_letter(root) or drive or ''

    return {
        'platform_root': root,
        'local_file_base': local_file_base,
        'platform_root_drive': resolved_drive,
        'candidates': candidates,
        'source': 'product_detection_detail_result.local_pic_url',
    }


def build_deploy_full_path(local_file_base, object_key):
    base = (local_file_base or '').replace('\\', '/').rstrip('/')
    key = (object_key or '').replace('\\', '/').lstrip('/')
    if not base or not key:
        return ''
    return f'{base}/{key}'


def sync_img_base_path(config, paths):
    """
    将推断出的 local_file_base 写入 config.img_base_path（拼接模式）。
    返回 (updated_config, changed, message)。
    """
    config = dict(config or {})
    paths = paths or {}
    local_file_base = (paths.get('local_file_base') or '').strip()
    if not local_file_base:
        return config, False, '未能从数据库推断出平台路径'

    mode = config.get('img_path_mode', 'concat')
    if mode != 'concat':
        return config, False, '当前为完整路径模式，未修改 img_base_path'

    new_path = local_file_base.replace('/', '\\') + ('\\' if not local_file_base.endswith('/') else '')
    if not new_path.endswith(('\\', '/')):
        new_path += '\\'

    old = (config.get('img_base_path') or '').strip()
    if old.replace('/', '\\').rstrip('\\/').lower() == new_path.rstrip('\\/').lower():
        return config, False, 'img_base_path 已与数据库一致'

    config['img_base_path'] = new_path
    drive = paths.get('platform_root_drive') or _drive_letter(local_file_base)
    if drive:
        config['platform_root_drive'] = drive
    root = paths.get('platform_root', '')
    msg = f'已同步 img_base_path → {new_path}'
    if root:
        msg += f'（平台根 {root}）'
    return config, True, msg
