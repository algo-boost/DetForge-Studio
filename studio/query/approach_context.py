"""本地总控 Approach 与 Magic-Fox 线上 Approach 的解析。"""


def resolve_local_approach_id(config=None, override=None):
    """
    本地 vision_backend 总控 Approach。
    用于 modeldeploy、缺陷类别、本地 modeltrainconfig 查询。
    """
    if override is not None:
        return int(override)
    config = dict(config or {})
    from server.core import DEFAULT_CONFIG
    return int(
        config.get('defect_approach_id')
        or DEFAULT_CONFIG.get('defect_approach_id')
        or 18
    )


def resolve_magic_fox_approach_id(project=None, override=None):
    """
    Magic-Fox 线上项目 Approach（sync_projects.approach_id）。
    用于数据集同步、平台训练模型 API。
    """
    if override is not None:
        return int(override)
    if project and project.get('approach_id') is not None:
        return int(project['approach_id'])
    return None
