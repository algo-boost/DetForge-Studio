"""从 model_pipeline / model_pipeline_node 解析筛选规则。"""
import json
import uuid

DETECTION_NODE_TYPES = frozenset({
    'object_detection',
    'detection',
    'classfication',
    'deep_learning_classification',
    'unsupervised_classification',
})

# 产线 confidence = 最低保留阈值（低于此值的框剔除）
CONFIDENCE_MODE_MIN_THRESHOLD = 'min_threshold'


def _parse_json_list(val):
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        s = val.strip()
        if not s or s == '[]':
            return []
        try:
            obj = json.loads(s)
            if isinstance(obj, list):
                return [str(x).strip() for x in obj if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return []


def _clamp_confidence(val, default=0.0):
    try:
        return max(0.0, min(1.0, float(val)))
    except (TypeError, ValueError):
        return default


def _parse_positions(val):
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return []
    if s.startswith('['):
        return _parse_json_list(s)
    return [s]


def pipeline_threshold_to_rule(categories, pipeline_conf, random_drop_ratio=0.0, positions=None):
    """
    将产线/pipeline 的 confidence 翻译为规则表条目。
    产线 UI 中 50% 表示最低保留阈值 0.5（0.5 以下剔除），非捞图区间。
    positions: algo_config 中的面别（如「正面」），仅对匹配 position 列的行生效。
    """
    min_conf = _clamp_confidence(pipeline_conf)
    pos_list = [str(p).strip() for p in (positions or []) if str(p).strip()]
    rule = {
        'categories': list(categories),
        'confidence_mode': CONFIDENCE_MODE_MIN_THRESHOLD,
        'min_confidence': min_conf,
        'confidence_range': [min_conf, 1.0],
        'random_drop_ratio': max(0.0, min(1.0, float(random_drop_ratio))),
        '_source': 'pipeline',
    }
    if pos_list:
        rule['positions'] = pos_list
    return rule


def _extract_basic_config(param):
    if not isinstance(param, dict):
        return {}
    if isinstance(param.get('config'), dict):
        basic = param['config'].get('basic_config') or {}
        if basic:
            return basic
    if isinstance(param.get('runtime_config'), dict):
        return param['runtime_config']
    return param


def parse_node_param(node_type, param_raw, node_name='', random_drop_ratio=0.0):
    """解析单个 pipeline 节点 param → (rules, warnings)。"""
    warnings = []
    if not param_raw:
        return [], warnings

    try:
        param = json.loads(param_raw) if isinstance(param_raw, str) else dict(param_raw or {})
    except (json.JSONDecodeError, TypeError):
        return [], [f'{node_name or "节点"}: param 不是有效 JSON']

    node_type = (node_type or '').lower()
    basic = _extract_basic_config(param)
    if node_type not in DETECTION_NODE_TYPES and not (
        basic.get('ng_tags') or basic.get('algo_config') or basic.get('confidence') is not None
    ):
        return [], warnings

    rules = []
    ng_tags = _parse_json_list(basic.get('ng_tags'))
    effective = _parse_json_list(basic.get('effectiveLabel'))
    base_conf = basic.get('confidence')

    algo_config = basic.get('algo_config') or []
    if isinstance(algo_config, str):
        try:
            algo_config = json.loads(algo_config)
        except json.JSONDecodeError:
            algo_config = []

    covered_labels = set()

    if isinstance(algo_config, list):
        for grp in algo_config:
            if not isinstance(grp, dict):
                continue
            labels = _parse_json_list(grp.get('labels'))
            if not labels:
                continue
            conf = grp.get('confidence', base_conf if base_conf is not None else 0)
            pos = grp.get('position') or grp.get('positions')
            pos_list = _parse_positions(pos)
            rules.append(pipeline_threshold_to_rule(labels, conf, random_drop_ratio, positions=pos_list))
            covered_labels.update(labels)

    if ng_tags:
        remaining = [t for t in ng_tags if t not in covered_labels]
        if remaining:
            conf = base_conf if base_conf is not None else 0
            rules.append(pipeline_threshold_to_rule(remaining, conf, random_drop_ratio))
            if covered_labels:
                warnings.append(
                    f'{node_name or "节点"}: {len(remaining)} 个标签使用默认最低阈值 '
                    f'{_clamp_confidence(conf):.2f}'
                )
    elif not rules and effective:
        conf = base_conf if base_conf is not None else 0
        rules.append(pipeline_threshold_to_rule(effective, conf, random_drop_ratio))
    elif not rules and base_conf is not None:
        rules.append(pipeline_threshold_to_rule([], _clamp_confidence(base_conf), random_drop_ratio))
        warnings.append(f'{node_name or "节点"}: 仅有全局 confidence，未指定类别')

    return rules, warnings


def dedupe_rules(rules):
    seen = set()
    out = []
    for r in rules or []:
        key = (
            tuple(r.get('categories') or []),
            r.get('confidence_mode'),
            float(r.get('min_confidence', (r.get('confidence_range') or [0, 1])[0])),
            tuple(r.get('confidence_range') or [0, 1]),
            float(r.get('random_drop_ratio', 0)),
            tuple(r.get('positions') or []),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _uid():
    return 'n' + uuid.uuid4().hex[:8]


def build_rules_flow(rules, remove_empty=True, rules_semantics='prune_boxes'):
    body = [{
        'id': _uid(),
        'type': 'builtin.filter_df_by_ext',
        'params': {
            'bind_loop_rule': 'loop_rule',
            'categories': [],
            'confidence_range': [0, 1],
            'random_drop_ratio': 1.0,
        },
    }]
    if remove_empty:
        body.append({'id': _uid(), 'type': 'builtin.remove_empty_ext_rows', 'params': {}})
    return {
        'version': 2,
        'nodes': [{
            'id': _uid(),
            'type': 'control.loop',
            'params': {
                'loop_mode': 'rules',
                'rules': list(rules or []),
                'rules_semantics': rules_semantics or 'prune_boxes',
            },
            'body': body,
        }],
    }


def fetch_pipeline_nodes(client, pipeline_id):
    """列出 pipeline 下可解析规则的检测节点。"""
    rows = []
    if client is None or not client.ensure_alive():
        return rows
    pid = str(pipeline_id or '').replace("'", "''")
    try:
        df = client.query(f"""
            SELECT node_id, name, type, param
            FROM model_pipeline_node
            WHERE pipeline_id = '{pid}'
            ORDER BY id
        """)
    except Exception:
        return rows
    if df is None or df.empty:
        return rows
    for _, row in df.iterrows():
        ntype = str(row.get('type') or '')
        name = str(row.get('name') or row.get('node_id') or '')
        rules, _ = parse_node_param(ntype, row.get('param'), node_name=name, random_drop_ratio=0.0)
        if not rules:
            continue
        rows.append({
            'node_id': str(row.get('node_id') or ''),
            'name': name,
            'type': ntype,
            'rule_count': len(rules),
        })
    return rows


def fetch_pipelines(client, limit=30):
    rows = []
    meta = {'source': 'model_pipeline'}
    limit = max(1, min(int(limit or 30), 100))

    if client is None or not client.ensure_alive():
        meta['error'] = '数据库未连接'
        return {'pipelines': rows, 'meta': meta}

    try:
        df = client.query(f"""
            SELECT pipeline_id, pipeline_name, subject_id, c_time
            FROM model_pipeline
            ORDER BY id DESC
            LIMIT {limit}
        """)
    except Exception as e:
        meta['error'] = str(e)
        return {'pipelines': rows, 'meta': meta}

    if df is None or df.empty:
        return {'pipelines': rows, 'meta': meta}

    for _, row in df.iterrows():
        rows.append({
            'pipeline_id': str(row.get('pipeline_id') or '').strip(),
            'pipeline_name': str(row.get('pipeline_name') or '').strip(),
            'subject_id': str(row.get('subject_id') or '').strip(),
            'c_time': str(row.get('c_time') or ''),
        })
    return {'pipelines': rows, 'meta': meta}


def fetch_pipeline_filter_rules(
    client,
    pipeline_id,
    node_id=None,
    random_drop_ratio=0.0,
    remove_empty=True,
    known_categories=None,
):
    """解析 pipeline 下检测节点，合并为规则列表与 flow。"""
    meta = {
        'pipeline_id': pipeline_id,
        'nodes_parsed': 0,
        'nodes_skipped': 0,
        'confidence_semantics': CONFIDENCE_MODE_MIN_THRESHOLD,
    }
    warnings = []

    if client is None or not client.ensure_alive():
        return {
            'rules': [],
            'flow': build_rules_flow([], remove_empty=remove_empty),
            'meta': {**meta, 'error': '数据库未连接'},
            'warnings': warnings,
        }

    pid = str(pipeline_id or '').replace("'", "''")
    sql = f"""
        SELECT node_id, name, type, param
        FROM model_pipeline_node
        WHERE pipeline_id = '{pid}'
        ORDER BY id
    """
    if node_id:
        nid = str(node_id).replace("'", "''")
        sql = f"""
            SELECT node_id, name, type, param
            FROM model_pipeline_node
            WHERE pipeline_id = '{pid}' AND node_id = '{nid}'
            LIMIT 1
        """

    try:
        df = client.query(sql)
        df_pipe = client.query(f"""
            SELECT pipeline_name FROM model_pipeline
            WHERE pipeline_id = '{pid}' LIMIT 1
        """)
        if df_pipe is not None and not df_pipe.empty:
            meta['pipeline_name'] = str(df_pipe.iloc[0].get('pipeline_name') or '')
    except Exception as e:
        return {
            'rules': [],
            'flow': build_rules_flow([], remove_empty=remove_empty),
            'meta': {**meta, 'error': str(e)},
            'warnings': warnings,
        }

    all_rules = []
    parsed_nodes = []

    if df is None or df.empty:
        warnings.append('未找到 pipeline 节点')
        flow = build_rules_flow([], remove_empty=remove_empty)
        return {'rules': [], 'flow': flow, 'meta': meta, 'warnings': warnings, 'nodes': parsed_nodes}

    known = set(known_categories or [])

    for _, row in df.iterrows():
        ntype = str(row.get('type') or '')
        name = str(row.get('name') or row.get('node_id') or '')
        rules, node_warnings = parse_node_param(
            ntype, row.get('param'), node_name=name, random_drop_ratio=random_drop_ratio,
        )
        warnings.extend(node_warnings)
        if not rules:
            meta['nodes_skipped'] = meta.get('nodes_skipped', 0) + 1
            continue
        meta['nodes_parsed'] = meta.get('nodes_parsed', 0) + 1
        parsed_nodes.append({
            'node_id': str(row.get('node_id') or ''),
            'name': name,
            'type': ntype,
            'rule_count': len(rules),
        })
        for r in rules:
            if known:
                unknown = [c for c in (r.get('categories') or []) if c not in known]
                if unknown:
                    warnings.append(f'{name}: 类别未在 defect_categories 中: {", ".join(unknown[:5])}')
        all_rules.extend(rules)

    rules = dedupe_rules(all_rules)
    semantics = 'keep_matching_rows' if float(random_drop_ratio or 0) >= 1.0 else 'prune_boxes'
    flow = build_rules_flow(rules, remove_empty=remove_empty, rules_semantics=semantics)
    return {
        'rules': rules,
        'flow': flow,
        'meta': meta,
        'warnings': warnings,
        'nodes': parsed_nodes,
    }
