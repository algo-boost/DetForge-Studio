/** 本地总控 Approach（vision_backend / defect_approach_id） */
export function resolveLocalApproachId(config) {
  const id = config?.defect_approach_id;
  return id != null && id !== '' ? Number(id) : 18;
}

/** Magic-Fox 线上项目 Approach（sync_projects.approach_id） */
export function resolveMagicFoxApproachId(project) {
  const id = project?.approach_id;
  return id != null && id !== '' ? Number(id) : null;
}

export function registryMatchesApproaches(model, localApproachId, magicFoxApproachId) {
  if (!model?.approach_id) return true;
  const aid = Number(model.approach_id);
  if (localApproachId != null && aid === Number(localApproachId)) return true;
  if (magicFoxApproachId != null && aid === Number(magicFoxApproachId)) return true;
  return false;
}
