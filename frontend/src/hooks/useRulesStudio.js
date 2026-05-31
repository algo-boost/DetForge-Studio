import { useCallback, useEffect, useMemo, useState } from 'react';
import FlowTree from '../lib/flowTree';
import { api } from '../api/client';

const DAILY_TRAWL_RULES = [
  { categories: ['脏污'], confidence_range: [0, 1], random_drop_ratio: 1.0 },
  { categories: ['焊丝'], confidence_range: [0.1, 1], random_drop_ratio: 1.0 },
  { categories: ['其他'], confidence_range: [0, 1], random_drop_ratio: 1.0 },
  { categories: ['异色'], confidence_range: [0.2, 1], random_drop_ratio: 1.0 },
  { categories: ['线头'], confidence_range: [0.1, 1], random_drop_ratio: 0.8 },
  { categories: ['胶水'], confidence_range: [0, 1], random_drop_ratio: 0.8 },
  {
    categories: [
      '胶水', '碰伤', '异物外漏', '凹坑', '鼓包', '划伤', '擦伤', '色差',
      '杂质', '褶皱（重度）', '破损', '压痕', '线头', '麻点',
    ],
    confidence_range: [0, 0.2],
    random_drop_ratio: 1.0,
  },
];

const RULE_TEMPLATES = {
  daily_trawl: {
    label: '日常捞图',
    removeEmpty: true,
    rules: DAILY_TRAWL_RULES,
  },
  high_conf: {
    label: '高置信缺陷',
    removeEmpty: true,
    rules: [{ categories: [], confidence_range: [0.85, 1], random_drop_ratio: 0.5 }],
  },
};

const SAVED_KEY = 'pc_saved_rule_templates';

function uid() {
  return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function newRule() {
  return { categories: [], confidence_range: [0, 1], random_drop_ratio: 1 };
}

function isMinThresholdRule(r) {
  return r?.confidence_mode === 'min_threshold' || r?.min_confidence != null;
}

function buildRulesFlow(rules, removeEmpty) {
  const body = [{
    id: uid(), type: 'builtin.filter_df_by_ext',
    params: { bind_loop_rule: 'loop_rule', categories: [], confidence_range: [0, 1], random_drop_ratio: 1 },
  }];
  if (removeEmpty) body.push({ id: uid(), type: 'builtin.remove_empty_ext_rows', params: {} });
  return {
    version: 2,
    nodes: [{
      id: uid(), type: 'control.loop',
      params: { loop_mode: 'rules', rules: JSON.parse(JSON.stringify(rules)) },
      body,
    }],
  };
}

export function useRulesStudio(onChange) {
  const [rules, setRules] = useState([]);
  const [removeEmpty, setRemoveEmpty] = useState(true);
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [compiledCode, setCompiledCode] = useState('');
  const [filterMode, setFilterMode] = useState('rules');

  const flow = useMemo(
    () => FlowTree.prepareFlow(buildRulesFlow(rules, removeEmpty)),
    [rules, removeEmpty],
  );

  useEffect(() => {
    api.getFlowNodes().then((res) => {
      if (res.success) setCategoryOptions(res.defect_categories || []);
    }).catch(() => {});
  }, []);

  const compile = useCallback(async () => {
    if (!rules.length) {
      setCompiledCode('');
      return '';
    }
    try {
      const res = await api.compileFlow({ flow, target: 'filter_rules' });
      const code = res.success ? (res.python_code || '') : '';
      setCompiledCode(code);
      return code;
    } catch {
      setCompiledCode('');
      return '';
    }
  }, [flow, rules.length]);

  useEffect(() => {
    const t = setTimeout(() => {
      compile().then(() => onChange?.());
    }, 300);
    return () => clearTimeout(t);
  }, [flow, compile, onChange]);

  const applySnapshot = useCallback((snap) => {
    setRules(JSON.parse(JSON.stringify(snap?.rules || [])));
    setRemoveEmpty(snap?.removeEmpty !== false);
  }, []);

  const loadBuiltinTemplate = useCallback((id) => {
    const tpl = RULE_TEMPLATES[id];
    if (!tpl) return;
    applySnapshot(tpl);
  }, [applySnapshot]);

  const loadSavedTemplate = useCallback((id) => {
    try {
      const list = JSON.parse(localStorage.getItem(SAVED_KEY) || '[]');
      const tpl = list.find((x) => x.id === id);
      if (tpl) applySnapshot(tpl);
    } catch { /* ignore */ }
  }, [applySnapshot]);

  const saveAsTemplate = useCallback((name) => {
    if (!name?.trim() || !rules.length) return;
    const list = JSON.parse(localStorage.getItem(SAVED_KEY) || '[]');
    const entry = {
      id: 't' + Date.now(),
      name: name.trim(),
      removeEmpty,
      rules: JSON.parse(JSON.stringify(rules)),
      savedAt: new Date().toISOString(),
    };
    const idx = list.findIndex((x) => x.name === entry.name);
    if (idx >= 0) list[idx] = entry;
    else list.unshift(entry);
    localStorage.setItem(SAVED_KEY, JSON.stringify(list.slice(0, 20)));
  }, [rules, removeEmpty]);

  const getSavedTemplates = useCallback(() => {
    try {
      return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]');
    } catch {
      return [];
    }
  }, []);

  const setFlow = useCallback((incoming) => {
    const f = FlowTree.prepareFlow(incoming || { version: 2, nodes: [] });
    const loop = f.nodes.find((n) => n.type === 'control.loop' && (n.params?.loop_mode || 'rules') === 'rules');
    setRules(JSON.parse(JSON.stringify(loop?.params?.rules || [])));
    setRemoveEmpty(!!f.nodes.some((n) => n.type === 'builtin.remove_empty_ext_rows'));
  }, []);

  const importPipelineRules = useCallback(async (pipelineId, nodeId, trawl) => {
    const qs = new URLSearchParams();
    if (nodeId) qs.set('node_id', nodeId);
    qs.set('random_drop_ratio', trawl ? '1' : '0');
    const res = await api.getPipelineRules(pipelineId, `?${qs}`);
    if (!res.success) throw new Error(res.error || '导入失败');
    applySnapshot({ rules: res.rules || [], removeEmpty: true });
    return res;
  }, [applySnapshot]);

  return {
    rules,
    setRules,
    removeEmpty,
    setRemoveEmpty,
    categoryOptions,
    compiledCode,
    filterMode,
    setFilterMode,
    flow,
    compile,
    applySnapshot,
    loadBuiltinTemplate,
    loadSavedTemplate,
    saveAsTemplate,
    getSavedTemplates,
    setFlow,
    importPipelineRules,
    newRule,
    isMinThresholdRule,
    RULE_TEMPLATES,
  };
}
