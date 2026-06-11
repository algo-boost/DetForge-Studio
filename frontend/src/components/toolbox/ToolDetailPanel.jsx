export default function ToolDetailPanel({ tool, mode = 'browse' }) {
  if (!tool) {
    return (
      <div className="panel toolbox-empty">选择工具查看说明与参数</div>
    );
  }

  if (mode === 'browse') {
    return (
      <div className="panel toolbox-detail">
        <h3 className="toolbox-detail-title">{tool.label}</h3>
        <div className="toolbox-card-id">{tool.id} · {tool.kind} · v{tool.version || '?'}</div>
        <p style={{ marginTop: 12, lineHeight: 1.5 }}>{tool.description || '暂无说明'}</p>

        {tool.inputs?.length > 0 && (
          <section className="toolbox-detail-section">
            <h4>输入</h4>
            <div className="toolbox-card-tags">
              {tool.inputs.map((i) => (
                <span key={i} className="toolbox-tag">{i}</span>
              ))}
            </div>
          </section>
        )}

        {tool.outputs?.length > 0 && (
          <section className="toolbox-detail-section">
            <h4>输出</h4>
            <div className="toolbox-card-tags">
              {tool.outputs.map((o) => (
                <span key={o} className="toolbox-tag">{o}</span>
              ))}
            </div>
          </section>
        )}

        <section className="toolbox-detail-section">
          <h4>参数 schema</h4>
          <pre className="toolbox-schema-pre">
            {JSON.stringify(tool.params_schema || {}, null, 2)}
          </pre>
        </section>

        {tool.skill_source && (
          <p style={{ fontSize: 12, marginTop: 12 }}>
            Skill 来源：
            <code>{tool.skill_source}</code>
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="panel toolbox-detail">
      <h3 className="toolbox-detail-title">{tool.label}</h3>
      <section className="toolbox-detail-section">
        <h4>Manifest</h4>
        <pre className="toolbox-schema-pre">
          {JSON.stringify({
            id: tool.id,
            kind: tool.kind,
            version: tool.version,
            manifest_path: tool.manifest_path,
            skill_source: tool.skill_source,
            tags: tool.tags,
          }, null, 2)}
        </pre>
      </section>
      <section className="toolbox-detail-section">
        <h4>完整 params_schema</h4>
        <pre className="toolbox-schema-pre">
          {JSON.stringify(tool.params_schema || {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}
