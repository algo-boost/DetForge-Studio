import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import { ConsolePanel } from '../components/ConsolePanel';
import { ResultsPanel } from '../components/ResultsPanel';
import { formatConsoleSummary } from '../lib/consoleOutput';
import { buildQueryResultsPath, saveLastQueryTaskId } from '../lib/queryResultsNav';

function buildConsoleContent({
  consoleOutput,
  executionTime,
  inputRows,
  outputRows,
  summary,
  heading = '✓ 筛选完成',
}) {
  if (consoleOutput || executionTime != null) {
    const line = formatConsoleSummary({
      executionTime,
      inputRows,
      outputRows,
    });
    return {
      text: [heading, line].filter(Boolean).join('\n\n'),
      type: 'success',
      consoleOutput: consoleOutput || '',
    };
  }
  if (summary) {
    return { text: summary, type: 'success', consoleOutput: '' };
  }
  return null;
}

export default function QueryResultsPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const taskId = searchParams.get('task') || '';

  const [loading, setLoading] = useState(!!taskId);
  const [rawResults, setRawResults] = useState([]);
  const [executionDetail, setExecutionDetail] = useState(null);
  const [console, setConsole] = useState(location.state?.console || null);
  const [dataSource, setDataSource] = useState('detail');
  const [strategyId, setStrategyId] = useState('');
  const [strategyName, setStrategyName] = useState('');
  const [viewerOpenNewWindow, setViewerOpenNewWindow] = useState(false);
  const [emptyHint, setEmptyHint] = useState(() => (
    location.state?.empty ? (location.state?.summary || '无结果') : ''
  ));

  const loadTask = useCallback(async (tid) => {
    if (!tid) return;
    setLoading(true);
    try {
      const res = await api.queryTask(tid);
      if (!res.success) throw new Error(res.error || '加载失败');
      const data = res.data || [];
      setRawResults(data);
      saveLastQueryTaskId(tid);
      setExecutionDetail({
        summary: res.summary || `${data.length} 条`,
        detail: '',
      });
      if (res.data_source) setDataSource(res.data_source);
      const meta = res.query_meta || {};
      setStrategyId(meta.strategy_id || '');
      setStrategyName(meta.strategy_name || '');
      setEmptyHint(data.length ? '' : (res.summary || '查询结果为空'));
      const fromApi = buildConsoleContent({
        consoleOutput: res.console_output,
        executionTime: res.execution_time,
        inputRows: res.input_rows,
        outputRows: res.output_rows,
        summary: res.summary,
      });
      if (fromApi) setConsole((prev) => prev || fromApi);
    } catch (e) {
      toast(e.message, 'error');
      setRawResults([]);
      setExecutionDetail({ summary: e.message, detail: '' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api.getConfig().then((r) => {
      setViewerOpenNewWindow(!!r.config?.viz_open_new_window);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (location.state?.console != null || location.state?.empty) {
      navigate(buildQueryResultsPath(taskId), { replace: true, state: null });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!taskId) {
      setLoading(false);
      return;
    }
    loadTask(taskId);
  }, [taskId, loadTask]);

  useEffect(() => {
    if (!taskId && emptyHint && !executionDetail) {
      setExecutionDetail({ summary: emptyHint, detail: '' });
    }
  }, [taskId, emptyHint, executionDetail]);

  const pageTitle = useMemo(() => {
    if (loading) return '加载结果…';
    if (rawResults.length) return `${rawResults.length} 条结果`;
    if (executionDetail?.summary) return executionDetail.summary;
    return '查询结果';
  }, [loading, rawResults.length, executionDetail?.summary]);

  const hasContent = !!console || rawResults.length > 0 || !!emptyHint;

  return (
    <div className="panel active query-results-page" id="panel-query-results">
      <SceneHubNav variant="query" />
      <div className="topbar query-results-topbar">
        <div className="topbar-left-group">
          <div>
            <div className="topbar-title">查询结果</div>
            <div className="topbar-sub">{pageTitle}</div>
          </div>
          {taskId && <span className="muted query-results-task-id">任务 {taskId}</span>}
        </div>
        <div className="topbar-actions">
          <Link to="/" className="btn btn-sm btn-ghost">返回查询</Link>
          {taskId && (
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => loadTask(taskId)}>
              刷新
            </button>
          )}
        </div>
      </div>

      <div className="query-results-body">
        {loading && (
          <div className="query-results-loading muted">正在加载结果…</div>
        )}

        {!loading && !hasContent && (
          <div className="query-results-empty">
            <p className="muted">暂无查询结果。请在查询页执行策略后查看，或从查询历史打开。</p>
            <Link to="/" className="btn btn-sm btn-primary">前往查询</Link>
            <Link to="/history" className="btn btn-sm btn-ghost">查询历史</Link>
          </div>
        )}

        <ConsolePanel
          visible={!!console}
          content={console}
          onClear={() => setConsole(null)}
        />

        {!loading && emptyHint && !rawResults.length && (
          <div className="query-results-empty-inline muted">{emptyHint}</div>
        )}

        <ResultsPanel
          pageLayout
          visible={rawResults.length > 0}
          rawData={rawResults}
          taskId={taskId}
          executionDetail={executionDetail}
          onArchive={() => toast('归档完成')}
          dataSource={dataSource}
          strategyId={strategyId}
          strategyName={strategyName}
          viewerOpenNewWindow={viewerOpenNewWindow}
        />
      </div>
    </div>
  );
}
