"""从 vision_backend 加载目标检测（DET）缺陷类别。"""
import json
import re
from collections import Counter

DEFAULT_FALLBACK_CATEGORIES = [
    '划伤', '压痕', '吊紧', '异物外漏', '折痕', '抛线', '拼接间隙', '水渍', '烫伤',
    '破损', '碰伤', '红标签', '线头', '脏污', '褶皱(T型)', '褶皱（重度）', '重跳针',
    '胶水', '色差', '凹坑', '擦伤', '杂质', '麻点', '焊丝', '异色', '其他',
]

# 训练配置里属于目标检测的任务类型
DETECTION_TRAIN_TYPES = frozenset({'BASIC_PRECISION', 'HIGH_PRECISION'})

CATEGORY_PARAM_KEYS = frozenset({'categories'})


def is_detection_model_type(model_type):
    """判断是否为检测模型（排除分类 / OCR / 分割等）。"""
    if not model_type:
        return False
    t = str(model_type).strip().upper()
    if t.startswith('DET'):
        return True
    if t in DETECTION_TRAIN_TYPES:
        return True
    if t in ('DETECTION',):
        return True
    return False


def _parse_model_labels(raw):
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        obj = raw
    if isinstance(obj, dict):
        return sorted(k for k in obj.keys() if k)
    return []


def _model_type_from_extra(extra_result):
    if not extra_result:
        return ''
    try:
        data = json.loads(extra_result) if isinstance(extra_result, str) else extra_result
        return str(data.get('model_type') or '').strip()
    except Exception:
        return ''


def _labels_from_deploy_extra(extra_result):
    if not extra_result:
        return []
    try:
        data = json.loads(extra_result) if isinstance(extra_result, str) else extra_result
        if not is_detection_model_type(data.get('model_type')):
            return []
        tc = data.get('train_config') or {}
        if isinstance(tc, str):
            tc = json.loads(tc)
        return _parse_model_labels(tc.get('model_labels'))
    except Exception:
        return []


def _merge_unique(*lists, fallback=None):
    seen = set()
    out = []
    for lst in lists:
        for c in lst or []:
            name = (c or '').strip()
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    if out:
        return out
    fb = fallback or DEFAULT_FALLBACK_CATEGORIES
    return list(fb)


def fetch_defect_categories(client, approach_id=18, fallback=None, ext_sample_limit=0):
    """
    仅加载目标检测模型类别（modeldeploy DET* / modeltrainconfig 检测任务 / DETECTION 项目 label 表）。
    """
    fallback = fallback or DEFAULT_FALLBACK_CATEGORIES
    deploy_labels = []
    label_table = []
    train_labels = []
    meta = {'approach_id': approach_id, 'scope': 'detection_only'}

    if client is not None and client.connection is not None:
        aid = int(approach_id)

        try:
            df = client.query(f"""
                SELECT approach_type FROM approach WHERE id = {aid} LIMIT 1
            """)
            if df is not None and not df.empty:
                meta['approach_type'] = df.iloc[0].get('approach_type')
        except Exception as e:
            meta['approach_error'] = str(e)

        try:
            df = client.query(f"""
                SELECT deploy_name, extra_result, object_key,
                       JSON_UNQUOTE(JSON_EXTRACT(extra_result, '$.model_type')) AS model_type
                FROM modeldeploy
                WHERE approach_id = {aid}
                  AND extra_result IS NOT NULL AND extra_result != ''
                  AND JSON_UNQUOTE(JSON_EXTRACT(extra_result, '$.model_type')) LIKE 'DET%'
                ORDER BY id DESC
                LIMIT 1
            """)
            if df is not None and not df.empty:
                row = df.iloc[0]
                deploy_labels = _labels_from_deploy_extra(row.get('extra_result'))
                meta['deploy_name'] = row.get('deploy_name')
                meta['model_type'] = row.get('model_type')
                meta['object_key'] = row.get('object_key')
        except Exception as e:
            meta['deploy_error'] = str(e)

        if meta.get('approach_type') == 'DETECTION':
            try:
                df = client.query(f"""
                    SELECT label_name FROM label
                    WHERE approach_id = {aid}
                    ORDER BY sort_order, id
                """)
                if df is not None and not df.empty:
                    label_table = [str(x).strip() for x in df['label_name'].tolist() if str(x).strip()]
            except Exception as e:
                meta['label_error'] = str(e)

        det_train_types = "', '".join(sorted(DETECTION_TRAIN_TYPES))
        try:
            df = client.query(f"""
                SELECT model_labels, model_name, model_type, model_store_key
                FROM modeltrainconfig
                WHERE approach_id = {aid}
                  AND model_type IN ('{det_train_types}')
                  AND model_labels IS NOT NULL AND model_labels != ''
                ORDER BY id DESC
                LIMIT 3
            """)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    train_labels.extend(_parse_model_labels(row.get('model_labels')))
                meta['train_config_models'] = df['model_name'].tolist()
                meta['train_model_types'] = df['model_type'].tolist()
        except Exception as e:
            meta['train_error'] = str(e)

    if deploy_labels:
        source = 'modeldeploy'
        categories = _merge_unique(deploy_labels, fallback=fallback)
    elif train_labels:
        source = 'modeltrainconfig'
        categories = _merge_unique(train_labels, fallback=fallback)
    elif label_table:
        source = 'label'
        categories = _merge_unique(label_table, fallback=fallback)
    else:
        source = 'fallback'
        categories = _merge_unique(fallback)

    id2name = categories_to_id2name(categories, {})

    return {
        'categories': categories,
        'source': source,
        'id2name': id2name,
        'meta': meta,
    }


def categories_to_id2name(categories, existing_id2name=None):
    """类别名列表 → id2name；保留已有映射，新类别追加 id。"""
    existing = dict(existing_id2name or {})
    name_to_id = {}
    for k, v in existing.items():
        try:
            name_to_id[str(v)] = int(k)
        except (TypeError, ValueError):
            continue
    next_id = max(name_to_id.values(), default=-1) + 1
    result = {str(k): v for k, v in existing.items()}
    for name in categories or []:
        if name in name_to_id:
            continue
        result[str(next_id)] = name
        name_to_id[name] = next_id
        next_id += 1
    return result


def merge_id2name(base_id2name, categories):
    base = dict(base_id2name or {})
    return categories_to_id2name(categories, base)


def inject_category_options(nodes, categories):
    if not categories:
        return nodes
    out = []
    cats = list(categories)
    for node in nodes:
        n = dict(node)
        schema = []
        for field in n.get('params_schema') or []:
            f = dict(field)
            if f.get('type') == 'multiselect' and f.get('key') in CATEGORY_PARAM_KEYS:
                f['options'] = cats
            schema.append(f)
        n['params_schema'] = schema
        out.append(n)
    return out


def apply_categories_to_templates(templates, categories):
    if not categories:
        return templates
    cats = list(categories)
    out = {}
    for tid, tpl in (templates or {}).items():
        t = dict(tpl)
        schema = []
        for field in t.get('params_schema') or []:
            f = dict(field)
            if f.get('type') == 'multiselect' and f.get('key') in CATEGORY_PARAM_KEYS:
                f['options'] = cats
            schema.append(f)
        t['params_schema'] = schema
        out[tid] = t
    return out
