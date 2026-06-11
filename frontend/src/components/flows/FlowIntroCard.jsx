/** 流程级说明（YAML 文件头 + description 字段） */
export default function FlowIntroCard({ readable, fallbackDescription = '', className = '' }) {
  const description = readable?.description || fallbackDescription;
  const hasHeader = readable?.summary || readable?.data_flow || description;

  if (!hasHeader) return null;

  return (
    <section className={`flows-intro-card${className ? ` ${className}` : ''}`}>
      {readable?.summary && (
        <p className="flows-intro-line">
          <span className="flows-intro-label">流程</span>
          {readable.summary}
        </p>
      )}
      {readable?.data_flow && (
        <p className="flows-intro-line flows-intro-line--sub">
          <span className="flows-intro-label">数据接力</span>
          {readable.data_flow}
        </p>
      )}
      {description && (
        <div className="flows-intro-desc">
          {String(description).split('\n').map((line) => line.trim()).filter(Boolean).map((line) => (
            <p key={line.slice(0, 40)}>{line}</p>
          ))}
        </div>
      )}
    </section>
  );
}
