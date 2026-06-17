/**
 * 展示当前步骤从上游自动接入的参数字段。
 */
export default function ComposeUpstreamBanner({ bindHints = [] }) {
  const bound = bindHints.filter((h) => h.ok);
  const missing = bindHints.filter((h) => !h.ok);

  if (!bound.length && !missing.length) return null;

  return (
    <div className="compose-upstream-banner" data-testid="compose-upstream-banner">
      {bound.length > 0 && (
        <div className="compose-upstream-bound">
          <span className="compose-upstream-label">自动接入上游</span>
          <ul className="compose-upstream-list">
            {bound.map((h) => (
              <li key={h.param}>
                <code className="compose-upstream-param">{h.param}</code>
                <span className="compose-upstream-arrow">←</span>
                <span>{h.detail || h.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {missing.length > 0 && (
        <div className="compose-upstream-missing">
          {missing.map((h) => (
            <p key={h.param} className="compose-step-hint is-warn">{h.text}</p>
          ))}
        </div>
      )}
    </div>
  );
}
