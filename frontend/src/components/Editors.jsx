import CodeMirror from '@uiw/react-codemirror';
import { sql } from '@codemirror/lang-sql';
import { python } from '@codemirror/lang-python';
import { EditorView } from '@codemirror/view';

const CM_SETUP = {
  lineNumbers: true,
  foldGutter: false,
  highlightActiveLine: true,
  bracketMatching: true,
};

const cmTheme = EditorView.theme({
  '&': {
    flex: '1 1 auto',
    minHeight: 0,
    fontSize: '12px',
    fontFamily: 'var(--mono)',
  },
  '.cm-scroller': {
    flex: '1 1 auto',
    minHeight: 0,
    overflow: 'auto',
    fontFamily: 'inherit',
    lineHeight: '1.55',
  },
  '.cm-content': { fontFamily: 'inherit' },
  '.cm-gutters': { fontSize: '11px' },
});

const cmBase = [EditorView.lineWrapping, cmTheme];

export function SqlEditor({ value, onChange, readOnly = false }) {
  return (
    <CodeMirror
      className="editor-cm-root"
      value={value}
      height="100%"
      readOnly={readOnly}
      extensions={[
        sql(),
        ...cmBase,
        ...(readOnly ? [EditorView.editable.of(false)] : []),
      ]}
      onChange={readOnly ? undefined : onChange}
      basicSetup={CM_SETUP}
    />
  );
}

export function PythonEditor({ value, onChange, readOnly = false }) {
  return (
    <CodeMirror
      className="editor-cm-root"
      value={value}
      height="100%"
      readOnly={readOnly}
      extensions={[
        python(),
        ...cmBase,
        ...(readOnly ? [EditorView.editable.of(false)] : []),
      ]}
      onChange={readOnly ? undefined : onChange}
      basicSetup={CM_SETUP}
    />
  );
}
