const VIEW_RE = /__VIEW_DF_START__\n([\s\S]*?)\n__VIEW_DF_END__/g;
const VIZ_RE = /__VIZ_START__\n([\s\S]*?)\n__VIZ_END__/g;

export function parseConsoleOutput(consoleOutput) {
  const empty = { viewMatches: [], vizMatches: [], cleanOutput: '' };
  if (!consoleOutput || !consoleOutput.trim()) {
    return empty;
  }
  let cleanOutput = consoleOutput;
  const viewMatches = [];
  const vizMatches = [];

  const viewRe = new RegExp(VIEW_RE.source, VIEW_RE.flags);
  let match;
  while ((match = viewRe.exec(consoleOutput)) !== null) {
    try {
      viewMatches.push(JSON.parse(match[1]));
      cleanOutput = cleanOutput.replace(match[0], '');
    } catch {
      /* ignore malformed payload */
    }
  }

  const vizRe = new RegExp(VIZ_RE.source, VIZ_RE.flags);
  while ((match = vizRe.exec(consoleOutput)) !== null) {
    try {
      vizMatches.push(JSON.parse(match[1]));
      cleanOutput = cleanOutput.replace(match[0], '');
    } catch {
      /* ignore malformed payload */
    }
  }

  return { viewMatches, vizMatches, cleanOutput: cleanOutput.trim() };
}

export function formatViewStats(viewData) {
  const stats = viewData?.stats || {};
  let text = `${stats.total_rows ?? 0} 行 × ${stats.total_cols ?? 0} 列`;
  if (stats.memory_usage) text += ` · ${stats.memory_usage}`;
  const tips = [];
  if (viewData?.truncated_rows) tips.push(`仅显示前 ${stats.displayed_rows} 行`);
  if (viewData?.truncated_cols) tips.push(`仅显示前 ${stats.displayed_cols} 列`);
  if (tips.length) text += ` · ${tips.join('，')}`;
  return text;
}

export function formatViewLabel(viewData, index, total) {
  const desc = viewData?.description?.trim();
  if (desc) return desc;
  if (total > 1) return `DataFrame #${index + 1}`;
  return 'DataFrame';
}

export function formatConsoleSummary({ executionTime, inputRows, outputRows, traceback } = {}) {
  const lines = [];
  if (executionTime != null) lines.push(`执行时间  ${(executionTime * 1000).toFixed(1)} ms`);
  if (inputRows != null) {
    let line = `数据规模  ${inputRows} 行`;
    if (outputRows != null) line += `  →  ${outputRows} 行`;
    lines.push(line);
  }
  if (traceback) lines.push('', traceback);
  return lines.join('\n');
}
