/** 运行级 env_spec 规范化（与后端 run_env_resolver 对齐） */

export function defaultInputsForTemplate(template) {
  const out = {};
  for (const row of template?.param_schema || []) {
    const key = String(row.key || '').trim();
    if (!key) continue;
    if (row.default != null && row.default !== '') out[key] = row.default;
  }
  return out;
}

export function normalizeEnvSpec(raw, templatesById = {}) {
  const spec = { ...(raw || {}) };
  const kind = String(spec.kind || 'template').toLowerCase();
  if (kind === 'manual') return { kind: 'manual' };
  if (kind === 'script') {
    return {
      kind: 'script',
      script: spec.script || spec.script_override || '',
      inputs: { ...(spec.inputs || {}) },
    };
  }
  const templateId = spec.template_id || 'time_preset';
  const tpl = templatesById[templateId];
  const defaults = tpl ? defaultInputsForTemplate(tpl) : { preset: 'yesterday' };
  const out = {
    kind: 'template',
    template_id: templateId,
    inputs: { ...defaults, ...(spec.inputs || {}) },
  };
  if (spec.script_override) out.script_override = spec.script_override;
  return out;
}

/** legacy time_window + env → env_spec */
export function normalizeRunParamsDefaults(raw, templatesById = {}) {
  const data = { ...(raw || {}) };
  if (data.env_spec) {
    return {
      env_spec: normalizeEnvSpec(data.env_spec, templatesById),
      env: { ...(data.env || {}) },
    };
  }
  const tw = data.time_window || {};
  if (tw.start_time && tw.end_time) {
    return {
      env_spec: normalizeEnvSpec({
        kind: 'template',
        template_id: 'time_absolute',
        inputs: { start_time: tw.start_time, end_time: tw.end_time },
      }, templatesById),
      env: { ...(data.env || {}) },
    };
  }
  return {
    env_spec: normalizeEnvSpec({
      kind: 'template',
      template_id: 'time_preset',
      inputs: { preset: tw.preset || 'yesterday' },
    }, templatesById),
    env: { ...(data.env || {}) },
  };
}

export function defaultRunParamsDefaults() {
  return normalizeRunParamsDefaults({});
}
