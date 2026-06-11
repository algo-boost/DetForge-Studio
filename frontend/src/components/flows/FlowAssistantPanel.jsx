import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../../api/client';
import FlowGraphPanel from './FlowGraphPanel';

function nextId() {
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

const STEPS = [
  { id: 'chat', label: '1 描述需求' },
  { id: 'yaml', label: '2 YAML 草稿' },
  { id: 'preview', label: '3 预览流程图' },
];

/**
 * 编排助手：对话 + YAML 草稿 + 校验 + 流程图预览。
 */
export default function FlowAssistantPanel({ flowId = null, compact = false }) {
  const [context, setContext] = useState(null);
  const [tab, setTab] = useState('chat');
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: '用自然语言描述编排需求，我会调用 Claude Code 生成 Kestra Flow YAML。落库请走 Git + Catalog 同步。',
    },
  ]);
  const [input, setInput] = useState('');
  const [yamlDraft, setYamlDraft] = useState('');
  const [validation, setValidation] = useState(null);
  const [previewGraph, setPreviewGraph] = useState(null);
  const [busy, setBusy] = useState(false);
  const [savedFlowId, setSavedFlowId] = useState(null);
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);

  const loadContext = useCallback(async () => {
    try {
      const q = flowId ? `?flow_id=${encodeURIComponent(flowId)}` : '';
      const r = await api.flowAgentContext(q);
      if (r.success) {
        setContext(r.data || null);
        setYamlDraft((prev) => prev || r.data?.current_yaml || '');
      }
    } catch {
      /* ignore */
    }
  }, [flowId]);

  useEffect(() => { loadContext(); }, [loadContext]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const pushMessage = (role, content, extra = {}) => {
    setMessages((prev) => [...prev, { id: nextId(), role, content, ...extra }]);
  };

  const statusLabel = () => {
    if (!context) return '检测中…';
    if (context.llm_configured) {
      const ver = context.claude_probe?.version;
      return ver ? `${context.provider_label} · ${ver}` : `${context.provider_label} 已就绪`;
    }
    if (context.claude_code_available && context.claude_probe && !context.claude_probe.ok) {
      return `CLI 已安装 · ${context.claude_probe.error || '探测失败'}`;
    }
    if (context.claude_code_available) {
      return `${context.provider_label} · CLI 已安装`;
    }
    return `未配置 ${context.provider_label || 'LLM'}`;
  };

  const statusClass = () => {
    if (context?.llm_configured) return 'flows-assistant-badge--ok';
    if (context?.claude_code_available) return 'flows-assistant-badge--warn';
    return '';
  };

  const applyResult = (data) => {
    const isError = data.mode === 'error' || (!data.success && data.error);
    if (isError) {
      toast(data.llm_error || data.reply || '调用失败', 'error');
      return;
    }
    if (data.yaml) {
      setYamlDraft(data.yaml);
      setValidation(data.validation || null);
      setTab('yaml');
      if (data.graph) setPreviewGraph(data.graph);
    }
  };

  const onSend = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    pushMessage('user', text);
    const streamMsgId = nextId();
    setMessages((prev) => [...prev, { id: streamMsgId, role: 'assistant', content: '', streaming: true }]);
    setBusy(true);
    setTab('chat');

    const history = messages
      .filter((m) => m.id !== 'welcome' && (m.role === 'user' || m.role === 'assistant'))
      .slice(-8)
      .map((m) => ({ role: m.role, content: m.content }));

    const updateStreamMsg = (patch) => {
      setMessages((prev) => prev.map((m) => (m.id === streamMsgId ? { ...m, ...patch } : m)));
    };

    const controller = new AbortController();
    abortRef.current = controller;
    let acc = '';
    let finalData = null;
    try {
      await api.flowAgentComposeStream(
        { message: text, flow_id: flowId, history },
        {
          signal: controller.signal,
          onEvent: (ev) => {
            if (ev.type === 'delta') {
              acc += ev.text || '';
              updateStreamMsg({ content: acc });
            } else if (ev.type === 'final') {
              finalData = ev.data || {};
            } else if (ev.type === 'error') {
              finalData = { mode: 'error', success: false, error: ev.error, reply: `调用失败：${ev.error}` };
            }
          },
        },
      );

      if (finalData) {
        updateStreamMsg({
          content: finalData.reply || acc || '已完成',
          streaming: false,
          mode: finalData.mode,
          isError: finalData.mode === 'error',
        });
        applyResult(finalData);
      } else {
        updateStreamMsg({ content: acc || '（无响应）', streaming: false });
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setMessages((prev) => prev.map((m) => (
          m.id === streamMsgId ? { ...m, streaming: false, content: m.content || '（已停止）' } : m
        )));
      } else {
        updateStreamMsg({ content: String(e.message || e), streaming: false, isError: true });
        toast(String(e.message || e), 'error');
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  const onStop = () => {
    abortRef.current?.abort();
  };

  const onValidate = async () => {
    if (!yamlDraft.trim()) return;
    setBusy(true);
    try {
      const r = await api.flowAgentValidate({ yaml: yamlDraft });
      const data = r.data || {};
      setValidation(data);
      if (data.valid) toast('校验通过', 'success');
      else toast((data.errors || []).join('；') || '校验失败', 'error');
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onPreview = async () => {
    if (!yamlDraft.trim()) return;
    setBusy(true);
    try {
      const r = await api.flowAgentPreviewGraph({ yaml: yamlDraft });
      const data = r.data || {};
      if (r.success && data.graph) {
        setPreviewGraph(data.graph);
        setValidation(data.validation || null);
        setTab('preview');
        toast('已生成预览', 'success');
      } else {
        toast(data.error || r.error || '预览失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onSave = async (overwrite = false) => {
    if (!yamlDraft.trim()) return;
    setBusy(true);
    try {
      const r = await api.flowAgentSave({ yaml: yamlDraft, overwrite });
      const data = r.data || {};
      if (r.success && data.flow_id) {
        setSavedFlowId(data.flow_id);
        toast(data.overwritten ? `已更新 Flow ${data.flow_id}` : `已保存 Flow ${data.flow_id}`, 'success');
        return;
      }
      if (data.exists) {
        // eslint-disable-next-line no-alert
        if (window.confirm(`已存在 Flow「${data.flow_id}」，是否覆盖？`)) {
          await onSave(true);
          return;
        }
        return;
      }
      toast(data.error || r.error || '保存失败', 'error');
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const copyPrompt = async () => {
    const text = context?.system_prompt || '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast('已复制 system prompt', 'success');
    } catch {
      toast('复制失败', 'error');
    }
  };

  const loadExample = async (exampleId) => {
    const ex = (context?.examples || []).find((e) => e.id === exampleId);
    if (!ex?.path) return;
    setBusy(true);
    try {
      const r = await api.flowPipelineYaml(exampleId);
      const yamlText = r?.data?.yaml;
      if (yamlText) {
        setYamlDraft(yamlText);
        setTab('yaml');
        toast(`已加载范例 ${exampleId}`, 'success');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`flows-assistant${compact ? ' flows-assistant--compact' : ''}`}>
      <div className="flows-assistant-toolbar">
        <div className="flows-assistant-steps">
          {STEPS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`flows-assistant-step${tab === s.id ? ' is-active' : ''}`}
              onClick={() => setTab(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flows-assistant-meta">
          <span className={`flows-assistant-badge ${statusClass()}`}>{statusLabel()}</span>
          {flowId && (
            <span className="flows-assistant-flow-tag">
              上下文 <code>{flowId}</code>
            </span>
          )}
        </div>
      </div>

      {tab === 'chat' && (
        <div className="flows-assistant-panel flows-assistant-panel--chat">
          <div className="flows-assistant-messages" role="log" aria-live="polite">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flows-assistant-msg flows-assistant-msg--${m.role}${m.isError ? ' flows-assistant-msg--error' : ''}`}
              >
                <div className="flows-assistant-msg-role">{m.role === 'user' ? '你' : '助手'}</div>
                <div className="flows-assistant-msg-body">
                  {m.content || (m.streaming ? '' : '')}
                  {m.streaming && !m.content && (
                    <span className="flows-assistant-thinking">正在调用 Claude Code…</span>
                  )}
                  {m.streaming && m.content && <span className="flows-assistant-cursor">▍</span>}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          {(context?.examples || []).length > 0 && (
            <div className="flows-assistant-examples">
              <span className="flows-assistant-examples-label">快速范例：</span>
              {(context.examples || []).map((ex) => (
                <button
                  key={ex.id}
                  type="button"
                  className="btn btn-sm flows-assistant-example-btn"
                  disabled={busy}
                  onClick={() => loadExample(ex.id)}
                >
                  {ex.label || ex.id}
                </button>
              ))}
            </div>
          )}
          <div className="flows-assistant-compose">
            <textarea
              className="form-control flows-assistant-input"
              rows={compact ? 2 : 3}
              placeholder="例如：每天 2 点按 yesterday 窗口捞 NG，人工改 COCO 后归档…（⌘/Ctrl+Enter 发送）"
              value={input}
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onSend();
              }}
            />
            {busy ? (
              <button
                type="button"
                className="btn flows-assistant-send flows-assistant-stop"
                onClick={onStop}
              >
                停止
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary flows-assistant-send"
                disabled={!input.trim()}
                onClick={onSend}
              >
                发送
              </button>
            )}
          </div>
        </div>
      )}

      {tab === 'yaml' && (
        <div className="flows-assistant-panel flows-assistant-panel--yaml">
          <div className="flows-assistant-draft-head">
            <p className="flows-assistant-panel-desc">编辑 YAML 后校验 tool_id，确认无误再预览流程图。</p>
            <div className="flows-assistant-draft-actions">
              <button type="button" className="btn btn-sm" disabled={busy} onClick={copyPrompt}>
                复制 Prompt
              </button>
              <button type="button" className="btn btn-sm" disabled={busy || !yamlDraft.trim()} onClick={onValidate}>
                校验
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={busy || !yamlDraft.trim()}
                onClick={onPreview}
              >
                预览流程图
              </button>
              <button
                type="button"
                className="btn btn-sm btn-primary"
                disabled={busy || !validation?.valid}
                title={validation?.valid ? '保存到 Catalog，使其可在 /flows 运行' : '先校验通过再保存'}
                onClick={() => onSave(false)}
              >
                保存为可运行 Flow
              </button>
            </div>
          </div>
          {savedFlowId && (
            <div className="flows-assistant-saved">
              已保存 <code>{savedFlowId}</code>，可前往
              {' '}
              <Link to={`/flows/tasks/${encodeURIComponent(savedFlowId)}`}>任务详情</Link>
              {' '}运行。
            </div>
          )}
          <textarea
            className="form-control flows-assistant-yaml"
            spellCheck={false}
            value={yamlDraft}
            onChange={(e) => {
              setYamlDraft(e.target.value);
              setValidation(null);
              setSavedFlowId(null);
            }}
            placeholder="粘贴或编辑 Kestra Flow YAML…"
          />
          {validation && (
            <div className={`flows-assistant-validation${validation.valid ? ' is-valid' : ' is-invalid'}`}>
              {validation.valid ? (
                <span>校验通过 · {validation.engine || 'kestra'} · id={validation.id || '—'}</span>
              ) : (
                <ul>
                  {(validation.errors || []).map((err) => (
                    <li key={err}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'preview' && (
        <div className="flows-assistant-panel flows-assistant-panel--preview">
          {!previewGraph?.nodes?.length ? (
            <div className="flows-assistant-empty">
              <p>尚无预览。请先在「YAML 草稿」页填写内容并点「预览流程图」。</p>
              <button type="button" className="btn btn-sm" onClick={() => setTab('yaml')}>
                去编辑 YAML
              </button>
            </div>
          ) : (
            <FlowGraphPanel graph={previewGraph} mode="design" compact />
          )}
        </div>
      )}
    </div>
  );
}
