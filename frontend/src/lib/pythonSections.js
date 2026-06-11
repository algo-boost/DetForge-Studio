const DEF_RE = /^def\s+(\w+)\s*\(/;

/** 解析 Python 源码中的 def 函数块，保留文件头 preamble（如 global 赋值） */
export function parsePythonModule(code) {
  const text = code || '';
  if (!text.trim()) {
    return { preamble: '', functions: [] };
  }

  const lines = text.split('\n');
  let preambleLines = [];
  const functions = [];
  let currentName = null;
  let currentLines = [];
  let seenDef = false;

  for (const line of lines) {
    const m = line.match(DEF_RE);
    if (m) {
      if (currentName) {
        functions.push({ name: currentName, code: currentLines.join('\n') });
      } else if (!seenDef && preambleLines.length) {
        /* preamble already collected */
      }
      seenDef = true;
      currentName = m[1];
      currentLines = [line];
      continue;
    }
    if (currentName) {
      currentLines.push(line);
    } else {
      preambleLines.push(line);
    }
  }

  if (currentName) {
    functions.push({ name: currentName, code: currentLines.join('\n') });
  }

  return {
    preamble: preambleLines.join('\n').replace(/\n+$/, ''),
    functions,
  };
}

export function joinPythonModule({ preamble, functions }) {
  const parts = [];
  if (preamble?.trim()) parts.push(preamble.trimEnd());
  for (const fn of functions || []) {
    if (fn.code?.trim()) parts.push(fn.code.trimEnd());
  }
  if (!parts.length) return '';
  return `${parts.join('\n\n')}\n`;
}

export function updatePythonFunction(fullCode, funcName, newFuncCode) {
  const mod = parsePythonModule(fullCode);
  const idx = mod.functions.findIndex((f) => f.name === funcName);
  if (idx < 0) return fullCode;
  mod.functions[idx] = { name: funcName, code: newFuncCode };
  return joinPythonModule(mod);
}

/**
 * 构建代码 Tab 侧边栏段落：process_data 置顶，其余函数按源码顺序。
 */
export function buildPythonSections({
  pythonCode,
  sampleCode,
  filterRulesCode,
  showSample = false,
  showFilterRules = false,
}) {
  const mod = parsePythonModule(pythonCode);
  const sections = [];

  const processFn = mod.functions.find((f) => f.name === 'process_data');
  const otherFns = mod.functions.filter((f) => f.name !== 'process_data');

  if (processFn) {
    sections.push({
      id: 'process_data',
      name: 'process_data',
      label: 'process_data',
      subtitle: '主函数',
      code: processFn.code,
      editable: true,
      isMain: true,
      source: 'python',
    });
  } else {
    sections.push({
      id: 'process_data',
      name: 'process_data',
      label: 'process_data',
      subtitle: '主函数',
      code: pythonCode?.trim() ? pythonCode : 'def process_data(df):\n    return df',
      editable: true,
      isMain: true,
      source: 'python',
    });
  }

  for (const fn of otherFns) {
    sections.push({
      id: fn.name,
      name: fn.name,
      label: fn.name,
      code: fn.code,
      editable: true,
      source: 'python',
    });
  }

  if (showFilterRules && filterRulesCode?.trim()) {
    sections.push({
      id: 'apply_filter_rules',
      name: 'apply_filter_rules',
      label: 'apply_filter_rules',
      subtitle: '规则 Tab 自动生成',
      code: filterRulesCode.trim(),
      editable: false,
      source: 'filter_rules',
    });
  }

  if (showSample && sampleCode?.trim()) {
    sections.push({
      id: 'apply_random_sample_rows',
      name: 'apply_random_sample_rows',
      label: 'apply_random_sample_rows',
      subtitle: '随顶部采样控件更新',
      code: sampleCode.trim(),
      editable: false,
      source: 'sample',
    });
  }

  return sections;
}

export function sectionCodeToPythonCode(sections, preamble = '') {
  const fns = sections
    .filter((s) => s.source === 'python')
    .map((s) => ({ name: s.name, code: s.code }));
  return joinPythonModule({ preamble, functions: fns });
}
