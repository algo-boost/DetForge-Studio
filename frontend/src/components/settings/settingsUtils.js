export const SETTINGS_TABS = [
  { id: 'connection', label: '数据库', desc: 'MySQL 连接' },
  { id: 'project', label: '检测项目', desc: '本地总控 Approach 与类别' },
  { id: 'labels', label: '类别映射', desc: 'id2name / COCO' },
  { id: 'paths', label: '图片路径', desc: '解析与归档' },
  { id: 'viz', label: '样本图库', desc: 'COCOVisualizer' },
  { id: 'predict', label: '预测环境', desc: 'DetUnify 子进程' },
  { id: 'platform', label: 'Magic-Fox', desc: '训练平台认证' },
  { id: 'security', label: '安全', desc: 'Token 与写库' },
  { id: 'query', label: '查询', desc: '默认 SQL' },
  { id: 'system', label: '系统', desc: '运行状态' },
];

export function id2nameToText(obj) {
  return Object.entries(obj || {})
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n');
}

export function textToId2name(text) {
  const out = {};
  String(text || '').split('\n').forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const m = trimmed.match(/^(\d+)\s*[:：]\s*(.+)$/);
    if (m) out[m[1]] = m[2].trim();
  });
  return out;
}

export function rootsToText(arr) {
  return (arr || []).filter(Boolean).join('\n');
}

export function textToRoots(text) {
  return String(text || '').split('\n').map((s) => s.trim()).filter(Boolean);
}
