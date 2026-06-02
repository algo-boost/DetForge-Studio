import { useMemo, useState } from 'react';
import { parseConsoleOutput, formatViewStats, formatViewLabel } from '../lib/consoleOutput';
import { DataFrameViewModal } from './DataFrameViewModal';

export function ConsolePanel({ visible, content, onClear }) {
  const [viewIndex, setViewIndex] = useState(null);
  const { viewMatches, cleanOutput } = useMemo(
    () => parseConsoleOutput(content?.consoleOutput || ''),
    [content?.consoleOutput],
  );

  const handleClear = () => {
    setViewIndex(null);
    onClear?.();
  };

  if (!visible) return null;

  const type = content?.type || '';
  const text = content?.text || '';

  return (
    <>
      <div className="console-panel" style={{ display: 'block' }}>
        <div className="console-header">
          <div className="console-title">
            <span className={`console-dot ${type === 'error' ? 'err' : type === 'run' ? 'run' : 'ok'}`} />
            执行输出
          </div>
          <button type="button" className="btn-icon" onClick={handleClear} title="清空">✕</button>
        </div>
        <div className={`console-body ${type || ''}`}>
          {text && <div className="console-text">{text}</div>}
          {viewMatches.length > 0 && (
            <div className="console-views">
              {viewMatches.map((viewData, index) => (
                <div key={index} className="console-view-item">
                  <button type="button" className="ep-btn" onClick={() => setViewIndex(index)}>
                    查看 {formatViewLabel(viewData, index, viewMatches.length)}
                  </button>
                  <span className="console-view-meta">{formatViewStats(viewData)}</span>
                </div>
              ))}
            </div>
          )}
          {cleanOutput && <pre className="console-pre">{cleanOutput}</pre>}
        </div>
      </div>
      <DataFrameViewModal
        open={viewIndex != null}
        viewData={viewIndex != null ? viewMatches[viewIndex] : null}
        title={viewIndex != null ? formatViewLabel(viewMatches[viewIndex], viewIndex, viewMatches.length) : undefined}
        onClose={() => setViewIndex(null)}
      />
    </>
  );
}

export const PYTHON_HELP = [
  ['view(df, description=None)', '弹窗查看 DataFrame，默认显示全部行；view(df, 50) 或 max_rows=50 限制行数'],
  ['info(df)', '打印 DataFrame 基本信息到控制台'],
  ['describe_df(df, description=None)', '弹窗查看统计描述；可传 description 覆盖默认标题'],
  ['parse_ext(ext)', '解析 ext 字段为 predictions 列表'],
  ['is_ext_empty(ext)', '判断 ext 检测框是否为空'],
  ['strip_boxes_below_confidence(df, categories, min_confidence)', '产线语义：低于阈值剔除'],
  ['select_df_rows_by_rules_union(df, rules)', '捞图：命中规则保留整图，ext 框不删'],
  ['filter_df_by_ext(df, categories, confidence_range, random_drop_ratio)', '按区间随机剔除框（会改 ext）'],
  ['remove_empty_ext_rows(df)', '移除 ext 中无任何框的行'],
  ['count_category_boxes(df)', '统计各类别框数量'],
  ['apply_random_sample_rows(df)', '随机采样（须在策略流中启用 random_sample；参数 SAMPLE_SIZE / RANDOM_SEED）'],
];
