import { useEffect, useMemo, useState } from 'react';
import { PythonEditor } from './Editors';
import { buildPythonSections, updatePythonFunction } from '../lib/pythonSections';

export function PythonCodeWorkspace({
  pythonCode,
  onPythonCodeChange,
  sampleCode,
  filterRulesCode,
  showSample = false,
  showFilterRules = false,
}) {
  const [activeId, setActiveId] = useState('process_data');

  const sections = useMemo(
    () => buildPythonSections({
      pythonCode,
      sampleCode,
      filterRulesCode,
      showSample,
      showFilterRules,
    }),
    [pythonCode, sampleCode, filterRulesCode, showSample, showFilterRules],
  );

  useEffect(() => {
    if (!sections.some((s) => s.id === activeId)) {
      setActiveId('process_data');
    }
  }, [sections, activeId]);

  const active = sections.find((s) => s.id === activeId) || sections[0];

  const handleSectionChange = (value) => {
    if (!active?.editable || active.source !== 'python') return;
    onPythonCodeChange(updatePythonFunction(pythonCode, active.name, value));
  };

  if (!active) return null;

  return (
    <div className="python-code-workspace">
      <div className="python-code-main">
        <div className="split-code-header python-code-section-header">
          <span className="python-code-section-title">
            {active.label}
            {active.subtitle && <span className="python-code-section-sub">{active.subtitle}</span>}
          </span>
          {active.isMain && <span className="python-code-badge">主函数</span>}
          {!active.editable && <span className="python-code-badge is-readonly">只读</span>}
        </div>
        <div className="editor-wrap">
          <PythonEditor
            value={active.code}
            onChange={active.editable ? handleSectionChange : undefined}
            readOnly={!active.editable}
          />
        </div>
      </div>
      <nav className="python-code-sidebar" aria-label="Python 函数">
        <div className="python-code-sidebar-title">函数</div>
        <ul className="python-code-nav">
          {sections.map((section) => (
            <li key={section.id}>
              <button
                type="button"
                className={`python-code-nav-item${section.id === activeId ? ' is-active' : ''}${section.isMain ? ' is-main' : ''}`}
                onClick={() => setActiveId(section.id)}
                title={section.subtitle || section.label}
              >
                <span className="python-code-nav-name">{section.label}</span>
                {section.subtitle && (
                  <span className="python-code-nav-hint">{section.subtitle}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
