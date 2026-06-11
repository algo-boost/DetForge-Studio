function toolTags(tool) {
  const tags = tool.tags?.length ? tool.tags : [];
  const kind = tool.kind ? [tool.kind] : [];
  return [...new Set([...tags, ...kind])];
}

export default function ToolCard({ tool, selected, stats = {}, onSelect }) {
  const usage = stats[tool.id] ?? tool.usage_count;

  return (
    <button
      type="button"
      className={`panel toolbox-card${selected ? ' is-selected' : ''}`}
      onClick={() => onSelect(tool)}
    >
      <div className="toolbox-card-label">{tool.label || tool.id}</div>
      <div className="toolbox-card-id">{tool.id} · v{tool.version || '?'}</div>
      {tool.description && (
        <p className="toolbox-card-desc">{tool.description}</p>
      )}
      <div className="toolbox-card-tags">
        {toolTags(tool).map((tag) => (
          <span
            key={tag}
            className={`toolbox-tag${tag === tool.kind ? ' toolbox-tag--kind' : ''}`}
          >
            {tag}
          </span>
        ))}
        {usage > 0 && (
          <span className="toolbox-tag">调用 {usage} 次</span>
        )}
      </div>
    </button>
  );
}
