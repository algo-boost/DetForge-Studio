"""Flow 节点注册表：内置节点 + 与块模板的映射。"""

CONTAINER_TYPES = frozenset({'control.if', 'control.loop'})

BUILTIN_NODES = [
    {
        'type': 'builtin.filter_df_by_ext',
        'category': '数据筛选',
        'name': '按缺陷框筛选',
        'description': '对 ext 内指定类别+置信度区间的框按比例随机剔除',
        'icon': 'filter',
        'params_schema': [
            {
                'key': 'bind_loop_rule', 'label': '绑定循环规则', 'type': 'select', 'default': 'manual',
                'options': [
                    {'value': 'manual', 'label': '手动配置'},
                    {'value': 'loop_rule', 'label': '使用当前循环规则（需在循环容器内）'},
                ],
            },
            {
                'key': 'categories', 'label': '缺陷类型', 'type': 'multiselect', 'default': [],
                'options': [
                    '划伤', '压痕', '吊紧', '异物外漏', '折痕', '抛线', '拼接间隙', '水渍', '烫伤',
                    '破损', '碰伤', '红标签', '线头', '脏污', '褶皱(T型)', '褶皱（重度）', '重跳针',
                    '胶水', '色差', '凹坑', '擦伤', '杂质', '麻点', '焊丝', '异色', '其他',
                ],
            },
            {
                'key': 'confidence_range', 'label': '置信度区间', 'type': 'range',
                'default': [0, 1], 'min': 0, 'max': 1, 'step': 0.05,
            },
            {
                'key': 'random_drop_ratio', 'label': '随机剔除比例', 'type': 'number',
                'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05,
            },
        ],
    },
    {
        'type': 'builtin.remove_empty_ext_rows',
        'category': '数据筛选',
        'name': '移除空框行',
        'description': '删除 ext 中没有任何检测框的图片行',
        'icon': 'filter',
        'params_schema': [],
    },
    {
        'type': 'control.loop',
        'category': '控制流',
        'name': '循环容器',
        'description': '按规则/次数/条件循环，循环体内可嵌入任意处理模块（支持嵌套）',
        'icon': 'loop',
        'is_container': True,
        'branches': ['body'],
        'params_schema': [
            {
                'key': 'loop_mode', 'label': '循环模式', 'type': 'select', 'default': 'rules',
                'options': [
                    {'value': 'rules', 'label': '规则列表（每条规则执行一次循环体）'},
                    {'value': 'count', 'label': '固定次数'},
                    {'value': 'while_rows', 'label': '当行数满足条件时重复（带上限）'},
                ],
            },
            {'key': 'count', 'label': '循环次数', 'type': 'number', 'default': 3, 'min': 1, 'step': 1},
            {
                'key': 'op', 'label': '行数比较', 'type': 'select', 'default': 'gt',
                'options': [
                    {'value': 'gt', 'label': '大于'}, {'value': 'gte', 'label': '大于等于'},
                    {'value': 'lt', 'label': '小于'}, {'value': 'lte', 'label': '小于等于'},
                ],
            },
            {'key': 'value', 'label': '行数阈值', 'type': 'number', 'default': 0, 'min': 0, 'step': 1},
            {'key': 'max_iterations', 'label': '最大迭代次数', 'type': 'number', 'default': 50, 'min': 1, 'step': 1},
            {'key': 'rules', 'label': '规则列表', 'type': 'rules_table', 'default': []},
        ],
    },
    {
        'type': 'control.if',
        'category': '控制流',
        'name': '条件分支',
        'description': '满足条件执行 THEN 分支，否则执行 ELSE 分支；分支内可嵌套任意模块',
        'icon': 'branch',
        'is_container': True,
        'branches': ['then', 'else'],
        'params_schema': [
            {
                'key': 'condition_type', 'label': '条件类型', 'type': 'select', 'default': 'row_count',
                'options': [
                    {'value': 'row_count', 'label': 'DataFrame 行数'},
                    {'value': 'not_empty', 'label': '结果非空（行数 > 0）'},
                    {'value': 'always', 'label': '始终成立（调试用）'},
                ],
            },
            {
                'key': 'op', 'label': '比较', 'type': 'select', 'default': 'gt',
                'options': [
                    {'value': 'gt', 'label': '大于'}, {'value': 'gte', 'label': '大于等于'},
                    {'value': 'lt', 'label': '小于'}, {'value': 'lte', 'label': '小于等于'},
                    {'value': 'eq', 'label': '等于'}, {'value': 'neq', 'label': '不等于'},
                ],
            },
            {'key': 'value', 'label': '行数阈值', 'type': 'number', 'default': 0, 'min': 0, 'step': 1},
        ],
    },
    {
        'type': 'builtin.view',
        'category': '观察',
        'name': '查看 DataFrame',
        'description': '弹窗预览当前数据（不改变数据）',
        'icon': 'eye',
        'params_schema': [
            {'key': 'label', 'label': '标签', 'type': 'text', 'default': ''},
        ],
    },
    {
        'type': 'builtin.count_category_boxes',
        'category': '观察',
        'name': '统计类别框数',
        'description': '统计并弹窗展示各类别检测框数量',
        'icon': 'eye',
        'params_schema': [],
    },
]


def is_container_type(node_type):
    return node_type in CONTAINER_TYPES


def get_builtin_nodes():
    return [dict(n) for n in BUILTIN_NODES]


def template_to_node_type(template_id):
    return f'template.{template_id}'


def build_node_registry(templates, category_options=None):
    """合并内置节点与策略块模板为统一注册表。"""
    from studio.query.defect_categories import inject_category_options

    nodes = get_builtin_nodes()
    for tpl in templates.values():
        nodes.append({
            'type': template_to_node_type(tpl['id']),
            'template_id': tpl['id'],
            'category': '块模板',
            'name': tpl.get('name', tpl['id']),
            'description': tpl.get('description', ''),
            'icon': tpl.get('icon', 'code'),
            'params_schema': tpl.get('params_schema', []),
        })
    if category_options:
        nodes = inject_category_options(nodes, category_options)
    return nodes
