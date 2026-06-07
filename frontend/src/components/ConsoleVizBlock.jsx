/** 执行输出区内置图表（由 Python plot_* 函数生成） */

export default function ConsoleVizBlock({ spec, index }) {
  if (!spec?.values?.length) return null;
  const maxVal = Math.max(...spec.values.map((v) => Number(v) || 0), 1);
  const title = spec.title || `图表 ${index + 1}`;
  const chartType = spec.chart || 'bar';

  return (
    <div className="console-viz-block">
      <div className="console-viz-head">
        <strong>{title}</strong>
        {(spec.x_label || spec.y_label) && (
          <span className="muted console-viz-axis">
            {spec.x_label}{spec.y_label ? ` → ${spec.y_label}` : ''}
          </span>
        )}
      </div>
      <div className={`console-viz-chart console-viz-${chartType}`}>
        {spec.labels.map((label, i) => {
          const val = Number(spec.values[i]) || 0;
          const pct = Math.max(2, (val / maxVal) * 100);
          return (
            <div key={`${label}-${i}`} className="console-viz-row" title={`${label}: ${val}`}>
              <span className="console-viz-label">{label}</span>
              <span className="console-viz-bar-track">
                <span className="console-viz-bar-fill" style={{ width: `${pct}%` }} />
              </span>
              <span className="console-viz-val">{val}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
