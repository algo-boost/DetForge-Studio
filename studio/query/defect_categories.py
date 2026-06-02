"""从 vision_backend 加载目标检测（DET）缺陷类别。"""
import json

DEFAULT_FALLBACK_CATEGORIES = [
    '划伤', '压痕', '吊紧', '异物外漏', '折痕', '抛线', '拼接间隙', '水渍', '烫伤',
    '破损', '碰伤', '红标签', '线头', '脏污', '褶皱(T型)', '褶皱（重度）', '重跳针',
    '胶水', '色差', '凹坑', '擦伤', '杂质', '麻点', '焊丝', '异色', '其他',
]

# 训练配置里可能混有分类任务；仅用于「模型列表」宽松判断，不用于缺陷类别加载
DETECTION_TRAIN_TYPES = frozenset({'BASIC_PRECISION', 'HIGH_PRECISION'})

CATEGORY_PARAM_KEYS = frozenset({'categories'})

# 非缺陷语义标签（成像面别 / 合格判定等），即使出现在 label 表也排除
_NON_DEFECT_LABEL_HINTS = frozenset({
    '正面', '反面', '侧面', '背面', '顶面', '底面',
    'ok', 'ng', 'OK', 'NG', '合格', '不合格', '良品', '不良品',
    '未分类', '其它', '其他类',
})


def is_detection_deploy_model_type(model_type):
    """缺陷类别专用：仅目标检测部署/训练类型（排除 BASIC_PRECISION 等分类训练）。"""
    if not model_type:
        return False
    t = str(model_type).strip().upper()
    if t.startswith('DET'):
        return True
    return t in ('DETECTION', 'OBJECT_DETECTION')


def is_detection_model_type(model_type):
    """模型列表展示用（含部分历史训练类型标记）。"""
    if is_detection_deploy_model_type(model_type):
        return True
    t = str(model_type).strip().upper()
    if t in DETECTION_TRAIN_TYPES:
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


def _defect_vocab(fallback):
    return set(fallback or DEFAULT_FALLBACK_CATEGORIES)


# 部署 model_labels 与缺陷词表重合不足时，视为错漏装/总成等其它 DET 任务，不用其类别
_MIN_DEFECT_OVERLAP_COUNT = 2
_MIN_DEFECT_OVERLAP_RATIO = 0.2


def _labels_match_defect_vocab(labels, fallback):
    """判断类别列表是否属于表面缺陷检测（与 config/默认缺陷表有足够重合）。"""
    cleaned = _strip_non_defect_hints(labels)
    if not cleaned:
        return False
    vocab = _defect_vocab(fallback)
    known = [n for n in cleaned if n in vocab]
    if len(known) >= _MIN_DEFECT_OVERLAP_COUNT:
        return True
    if len(cleaned) >= 5 and len(known) / len(cleaned) >= _MIN_DEFECT_OVERLAP_RATIO:
        return True
    return False


def _labels_for_defect_detection_source(labels, fallback):
    """DET 部署/训练：词表匹配则采用全部类别；否则丢弃（常见为错漏装类名）。"""
    cleaned = _strip_non_defect_hints(labels)
    if not cleaned:
        return []
    if _labels_match_defect_vocab(cleaned, fallback):
        return cleaned
    return []


def _strip_non_defect_hints(labels):
    """去掉明显的成像/合格判定标签，保留其余名称。"""
    out = []
    for raw in labels or []:
        name = str(raw or '').strip()
        if name and name not in _NON_DEFECT_LABEL_HINTS:
            out.append(name)
    return out


def _sanitize_defect_labels(labels, fallback):
    """label 表等：仅保留与缺陷词表有交集的项。"""
    cleaned = _strip_non_defect_hints(labels)
    if not cleaned:
        return []
    vocab = _defect_vocab(fallback)
    known = [n for n in cleaned if n in vocab]
    return known if known else []


def _labels_from_deploy_extra(extra_result):
    if not extra_result:
        return []
    try:
        data = json.loads(extra_result) if isinstance(extra_result, str) else extra_result
        if not is_detection_deploy_model_type(data.get('model_type')):
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
    仅加载目标检测缺陷类别：
    1) modeldeploy 且 model_type 为 DET*；
    2) modeltrainconfig 且 model_type 为 DET*（不用 BASIC_PRECISION 分类训练）；
    3) label 表仅在与缺陷词表有交集时采用；
    4) 否则回退 config id2name / 默认缺陷表。
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
            # 同一 approach 可能先后部署错漏装 DET 与表面缺陷 DET；仅取 id 最大的一条会误用错漏装类别
            df = client.query(f"""
                SELECT deploy_name, extra_result, object_key,
                       JSON_UNQUOTE(JSON_EXTRACT(extra_result, '$.model_type')) AS model_type
                FROM modeldeploy
                WHERE approach_id = {aid}
                  AND extra_result IS NOT NULL AND extra_result != ''
                  AND JSON_UNQUOTE(JSON_EXTRACT(extra_result, '$.model_type')) LIKE 'DET%'
                ORDER BY id DESC
                LIMIT 30
            """)
            if df is not None and not df.empty:
                skipped = []
                for _, row in df.iterrows():
                    raw_deploy = _labels_from_deploy_extra(row.get('extra_result'))
                    if not raw_deploy:
                        continue
                    candidate = _labels_for_defect_detection_source(raw_deploy, fallback)
                    if candidate:
                        deploy_labels = candidate
                        meta['deploy_label_count'] = len(deploy_labels)
                        meta['deploy_name'] = row.get('deploy_name')
                        meta['model_type'] = row.get('model_type')
                        meta['object_key'] = row.get('object_key')
                        if skipped:
                            meta['deploy_skipped_newer'] = skipped[:3]
                        break
                    skipped.append({
                        'deploy_name': row.get('deploy_name'),
                        'labels': raw_deploy[:8],
                    })
                if not deploy_labels and skipped:
                    meta['deploy_skipped_wrong_task'] = skipped[0].get('labels')
                    meta['deploy_name'] = skipped[0].get('deploy_name')
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
                    raw_labels = [str(x).strip() for x in df['label_name'].tolist() if str(x).strip()]
                    label_table = _sanitize_defect_labels(raw_labels, fallback)
                    if raw_labels and not label_table:
                        meta['label_table_skipped'] = raw_labels[:20]
            except Exception as e:
                meta['label_error'] = str(e)

        try:
            df = client.query(f"""
                SELECT model_labels, model_name, model_type, model_store_key
                FROM modeltrainconfig
                WHERE approach_id = {aid}
                  AND UPPER(model_type) LIKE 'DET%'
                  AND model_labels IS NOT NULL AND model_labels != ''
                ORDER BY id DESC
                LIMIT 3
            """)
            if df is not None and not df.empty:
                raw_train = []
                for _, row in df.iterrows():
                    if not is_detection_deploy_model_type(row.get('model_type')):
                        continue
                    raw_train.extend(_parse_model_labels(row.get('model_labels')))
                train_labels = _labels_for_defect_detection_source(raw_train, fallback)
                if raw_train and not train_labels:
                    meta['train_skipped_wrong_task'] = raw_train[:24]
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
