import { DEFAULT_SAMPLE, DEFAULT_SEED, buildSampleFunction } from './constants';

const BRANCH_KEYS = ['then', 'else', 'body'];
export const SAMPLE_FUNC = 'apply_random_sample_rows';

function* walkFlowNodes(nodes) {
  for (const node of nodes || []) {
    yield node;
    for (const key of BRANCH_KEYS) {
      yield* walkFlowNodes(node[key] || []);
    }
  }
}

function isRandomSampleNode(node) {
  const t = node?.type || '';
  const tid = node?.template_id || '';
  return t === 'template.random_sample' || tid === 'random_sample';
}

export function hasInlineSamplingInPython(processCode, sampleCode = '') {
  if ((sampleCode || '').trim()) return true;
  const text = (processCode || '').trim();
  if (!text) return false;
  if (new RegExp(`\\b${SAMPLE_FUNC}\\s*\\(`).test(text)) return true;
  if (/_tpl_random_sample/.test(text)) return true;
  if (/\.sample\s*\(/.test(text)) return true;
  return false;
}

export function hasInlineSamplingInFlow(flow) {
  if (!flow?.nodes?.length) return false;
  for (const node of walkFlowNodes(flow.nodes)) {
    if (isRandomSampleNode(node)) return true;
  }
  return false;
}

export function hasInlineSampling(processCode, flow, sampleCode = '') {
  return hasInlineSamplingInPython(processCode, sampleCode) || hasInlineSamplingInFlow(flow);
}

export function extractSampleFromSampleCode(code) {
  const text = (code || '').trim();
  if (!text) return null;
  const defRe = new RegExp(
    `def\\s+${SAMPLE_FUNC}\\s*\\([^)]*max_rows\\s*=\\s*(\\d+)[^)]*random_seed\\s*=\\s*(\\d+)`,
  );
  const m = defRe.exec(text);
  if (m) {
    return { sampleSize: parseInt(m[1], 10), randomSeed: parseInt(m[2], 10) };
  }
  return null;
}

export function extractSampleFromPython(processCode, sampleCode = '') {
  const fromSample = extractSampleFromSampleCode(sampleCode);
  if (fromSample) return fromSample;

  const text = (processCode || '').trim();
  if (!text) return null;

  const callRe = new RegExp(
    `${SAMPLE_FUNC}\\s*\\(\\s*df\\s*,\\s*max_rows\\s*=\\s*(\\d+)\\s*,\\s*random_seed\\s*=\\s*(\\d+)\\s*\\)`,
  );
  const callM = callRe.exec(text);
  if (callM) {
    return { sampleSize: parseInt(callM[1], 10), randomSeed: parseInt(callM[2], 10) };
  }

  const tplRe = /_tpl_random_sample_\w+\s*\([^,]+,\s*\{[^}]*(?:max_rows|'max_rows'|"max_rows")\s*:\s*(\d+)[^}]*(?:random_seed|'random_seed'|"random_seed")\s*:\s*(\d+)/;
  const tplM = tplRe.exec(text);
  if (tplM) {
    return { sampleSize: parseInt(tplM[1], 10), randomSeed: parseInt(tplM[2], 10) };
  }

  return null;
}

export function extractSampleFromFlow(flow) {
  if (!flow?.nodes?.length) return null;
  let sampleSize = null;
  let randomSeed = null;
  for (const node of walkFlowNodes(flow.nodes)) {
    if (!isRandomSampleNode(node)) continue;
    const p = node.params || {};
    if (p.max_rows != null) sampleSize = Number(p.max_rows);
    if (p.random_seed != null) randomSeed = Number(p.random_seed);
  }
  if (sampleSize == null && randomSeed == null) return null;
  return {
    sampleSize: sampleSize ?? DEFAULT_SAMPLE,
    randomSeed: randomSeed ?? DEFAULT_SEED,
  };
}

export function resolveSampleSettings({ pythonCode, sampleCode, flow, sampleSize, randomSeed }) {
  const fromSample = extractSampleFromSampleCode(sampleCode);
  if (fromSample) return fromSample;
  const fromPy = extractSampleFromPython(pythonCode, sampleCode);
  if (fromPy) return fromPy;
  const fromFlow = extractSampleFromFlow(flow);
  if (fromFlow) return fromFlow;
  return {
    sampleSize: sampleSize ?? DEFAULT_SAMPLE,
    randomSeed: randomSeed ?? DEFAULT_SEED,
  };
}

function patchFlowNode(node, sampleSize, randomSeed) {
  if (!node) return;
  if (isRandomSampleNode(node)) {
    node.params = { ...(node.params || {}), max_rows: sampleSize, random_seed: randomSeed };
  }
  const thenHasSample = (node.then || []).some(isRandomSampleNode);
  if (
    node.type === 'control.if'
    && thenHasSample
    && (node.params?.condition_type || 'row_count') === 'row_count'
    && (node.params?.op || 'gt') === 'gt'
  ) {
    node.params = { ...node.params, value: sampleSize };
  }
  for (const key of BRANCH_KEYS) {
    for (const child of node[key] || []) patchFlowNode(child, sampleSize, randomSeed);
  }
}

export function patchFlowSample(flow, { sampleSize, randomSeed }) {
  if (!flow?.nodes?.length) return flow;
  const patched = JSON.parse(JSON.stringify(flow));
  for (const node of patched.nodes) patchFlowNode(node, sampleSize, randomSeed);
  return patched;
}

/** 仅更新采样函数定义，不修改 process_data。 */
export function patchSampleFunction(sampleCode, { sampleSize, randomSeed }) {
  const text = (sampleCode || '').trim();
  if (!text) return buildSampleFunction(sampleSize, randomSeed);
  const defRe = new RegExp(
    `(def\\s+${SAMPLE_FUNC}\\s*\\([^)]*max_rows\\s*=\\s*)\\d+([^)]*random_seed\\s*=\\s*)\\d+`,
  );
  if (defRe.test(text)) {
    return text.replace(defRe, `$1${sampleSize}$2${randomSeed}`);
  }
  return buildSampleFunction(sampleSize, randomSeed);
}

/** 从合并代码中拆出采样函数（兼容旧策略）。 */
export function extractSampleFunctionBlock(code) {
  const text = (code || '').trim();
  const re = new RegExp(
    `(def\\s+${SAMPLE_FUNC}\\s*\\([^)]*\\)\\s*:[\\s\\S]*?)(?=\\ndef\\s+|\\nclass\\s+|$)`,
  );
  const m = re.exec(text);
  return m ? m[1].trim() : '';
}

/** process_data 内采样调用统一为无参形式，参数由采样函数定义承担。 */
export function normalizeProcessSampleCall(processCode) {
  return (processCode || '').replace(
    new RegExp(`${SAMPLE_FUNC}\\s*\\(\\s*df\\s*,\\s*max_rows\\s*=\\s*\\d+\\s*,\\s*random_seed\\s*=\\s*\\d+\\s*\\)`, 'g'),
    `${SAMPLE_FUNC}(df)`,
  );
}

/** 请求发出前同步生成采样函数，避免 async state 滞后。 */
export function resolveSampleCodeForExecution(sampleCode, { sampleSize, randomSeed }, inline = true) {
  if (!inline) return '';
  return patchSampleFunction(
    sampleCode || buildSampleFunction(sampleSize, randomSeed),
    { sampleSize, randomSeed },
  );
}

export function splitStrategyPython({ pythonCode, sampleCode }) {
  let proc = normalizeProcessSampleCall(pythonCode || '');
  let sample = (sampleCode || '').trim();
  if (!sample) {
    sample = extractSampleFunctionBlock(proc);
    if (sample) {
      proc = proc.replace(sample, '').trim();
    }
  }
  return { processCode: proc, sampleCode: sample };
}
