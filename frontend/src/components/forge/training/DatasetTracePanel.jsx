import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, toast } from '../../../api/client';

const TRACE_LABEL = {
  matched: 'object_key',
  filename: '文件名',
  fuzzy: '模糊匹配',
  sn_only: 'SN',
  path_only: '路径SN',
  unmatched: '未匹配',
};

const TRACE_CLASS = {
  matched: 'platform-trace-pill-ok',
  filename: 'platform-trace-pill-ok',
  fuzzy: 'platform-trace-pill-info',
  sn_only: 'platform-trace-pill-info',
  path_only: 'platform-trace-pill-warn',
  unmatched: 'platform-trace-pill-err',
};

const PAGE_SIZE = 50;

function TracePill({ status }) {
  const cls = TRACE_CLASS[status] || 'platform-trace-pill-muted';
  return <span className={`platform-trace-pill ${cls}`}>{TRACE_LABEL[status] || status || '—'}</span>;
}

function fmtTime(val) {
  if (!val) return '—';
  return String(val).replace('T', ' ').slice(0, 19);
}

export default function DatasetTracePanel({ datasets, projectId }) {
  const writable = useMemo(
    () => (datasets || []).filter((d) => d.write_db),
    [datasets],
  );
  const [datasetId, setDatasetId] = useState('');
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [retracing, setRetracing] = useState(false);
  const [filters, setFilters] = useState({
    q: '', product_no: '', product_type: '', trace_status: '', start: '', end: '',
  });

  useEffect(() => {
    if (writable.length && !writable.some((d) => String(d.id) === String(datasetId))) {
      setDatasetId(String(writable[0].id));
    }
  }, [writable, datasetId]);

  const load = useCallback(async (off = 0, overrideFilters = null) => {
    if (!datasetId) return;
    setLoading(true);
    const f = overrideFilters || filters;
    try {
      const p = new URLSearchParams();
      p.set('limit', String(PAGE_SIZE));
      p.set('offset', String(off));
      Object.entries(f).forEach(([k, v]) => {
        if (String(v || '').trim()) p.set(k, String(v).trim());
      });
      const res = await api.forgeSyncDatasetItems(datasetId, `?${p.toString()}`);
      if (res.success) {
        setItems(res.data || []);
        setTotal(res.total || 0);
        setSummary(res.trace_summary || null);
        setOffset(off);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setLoading(false); }
  }, [datasetId, filters]);

  useEffect(() => { load(0); }, [load]);

  const retrace = async () => {
    if (!datasetId) return;
    setRetracing(true);
    try {
      const res = await api.forgeSyncDatasetRetrace(datasetId);
      if (res.success) {
        toast(`溯源完成：更新 ${res.updated || 0} 条`);
        load(0);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setRetracing(false); }
  };

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (!writable.length) {
    return (
      <div className="platform-surface-card platform-trace-empty">
        <h3 className="platform-section-title">样本溯源</h3>
        <p className="platform-section-desc">
          需在数据集中勾选「标注写入数据库」并完成至少一次同步，才能将图片与 vision_backend 平台库（SN / 款型 / 检测时间）联合溯源。
        </p>
      </div>
    );
  }

  return (
    <div className="platform-trace-section">
      <div className="platform-surface-card platform-section-toolbar-card">
        <div>
          <h3 className="platform-section-title">样本溯源</h3>
          <p className="platform-section-desc">
            查询 vision_backend.product_detection_detail_result：优先 object_key / 文件名精确匹配，未命中时按<strong>文件名模糊相似度</strong>（≥72%）匹配，再按 SN。
          </p>
        </div>
        <div className="platform-section-toolbar-actions">
          <button type="button" className="btn sm" disabled={retracing || loading} onClick={retrace}>
            {retracing ? '溯源中…' : '重新溯源'}
          </button>
          <button type="button" className="btn sm btn-ghost" disabled={loading} onClick={() => load(offset)}>刷新</button>
        </div>
      </div>

      {summary && (
        <div className="platform-trace-stats">
          <div className="platform-trace-stat">
            <span className="platform-trace-stat-value">{summary.total || 0}</span>
            <span className="platform-trace-stat-label">样本总数</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-ok">
            <span className="platform-trace-stat-value">{summary.matched || 0}</span>
            <span className="platform-trace-stat-label">object_key</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-ok">
            <span className="platform-trace-stat-value">{summary.filename || 0}</span>
            <span className="platform-trace-stat-label">文件名</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-info">
            <span className="platform-trace-stat-value">{summary.fuzzy || 0}</span>
            <span className="platform-trace-stat-label">模糊</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-info">
            <span className="platform-trace-stat-value">{summary.sn_only || 0}</span>
            <span className="platform-trace-stat-label">SN</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-warn">
            <span className="platform-trace-stat-value">{summary.path_only || 0}</span>
            <span className="platform-trace-stat-label">路径解析</span>
          </div>
          <div className="platform-trace-stat platform-trace-stat-err">
            <span className="platform-trace-stat-value">{summary.unmatched || 0}</span>
            <span className="platform-trace-stat-label">未匹配</span>
          </div>
        </div>
      )}

      <div className="platform-surface-card platform-trace-filters">
        <label className="platform-trace-filter">
          数据集
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {writable.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>
        <label className="platform-trace-filter">
          关键词
          <input
            value={filters.q}
            placeholder="文件名 / SN / 款型 / object_key"
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
          />
        </label>
        <label className="platform-trace-filter">
          SN
          <input
            value={filters.product_no}
            placeholder="product_no"
            onChange={(e) => setFilters({ ...filters, product_no: e.target.value })}
          />
        </label>
        <label className="platform-trace-filter">
          款型
          <input
            value={filters.product_type}
            placeholder="product_type"
            onChange={(e) => setFilters({ ...filters, product_type: e.target.value })}
          />
        </label>
        <label className="platform-trace-filter">
          溯源状态
          <select
            value={filters.trace_status}
            onChange={(e) => setFilters({ ...filters, trace_status: e.target.value })}
          >
            <option value="">全部</option>
            <option value="matched">object_key</option>
            <option value="filename">文件名</option>
            <option value="fuzzy">模糊匹配</option>
            <option value="sn_only">SN</option>
            <option value="path_only">路径SN</option>
            <option value="unmatched">未匹配</option>
          </select>
        </label>
        <label className="platform-trace-filter">
          开始时间
          <input type="datetime-local" value={filters.start} onChange={(e) => setFilters({ ...filters, start: e.target.value })} />
        </label>
        <label className="platform-trace-filter">
          结束时间
          <input type="datetime-local" value={filters.end} onChange={(e) => setFilters({ ...filters, end: e.target.value })} />
        </label>
        <div className="platform-trace-filter-actions">
          <button type="button" className="btn sm primary" disabled={loading} onClick={() => load(0)}>查询</button>
            <button
            type="button"
            className="btn sm btn-ghost"
            onClick={() => {
              const empty = { q: '', product_no: '', product_type: '', trace_status: '', start: '', end: '' };
              setFilters(empty);
              load(0, empty);
            }}
          >
            重置
          </button>
        </div>
      </div>

      <div className="platform-surface-card platform-trace-table-card">
        <table className="forge-table platform-trace-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>SN</th>
              <th>款型</th>
              <th>部位</th>
              <th>平台时间</th>
              <th>平台记录</th>
              <th>溯源</th>
              <th>框数</th>
            </tr>
          </thead>
          <tbody>
            {loading && !items.length && (
              <tr><td colSpan={8} className="platform-empty-cell">加载中…</td></tr>
            )}
            {!loading && !items.length && (
              <tr><td colSpan={8} className="platform-empty-cell">无匹配样本，请调整筛选或先执行同步</td></tr>
            )}
            {items.map((row) => (
              <tr key={row.id}>
                <td>
                  <div className="platform-trace-file">{row.file_name}</div>
                  {row.local_path && (
                    <div className="platform-trace-path" title={row.local_path}>{row.local_path}</div>
                  )}
                </td>
                <td><code>{row.product_no || '—'}</code></td>
                <td>{row.product_type || '—'}</td>
                <td>{row.position || '—'}</td>
                <td className="platform-dataset-time">{fmtTime(row.platform_c_time)}</td>
                <td>
                  {row.source_detail_id ? (
                    <code className="platform-trace-id">#{row.source_detail_id}</code>
                  ) : '—'}
                </td>
                <td><TracePill status={row.trace_status} /></td>
                <td>{row.box_count ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {total > PAGE_SIZE && (
          <div className="platform-trace-pagination">
            <span>{total} 条 · 第 {page}/{pages} 页</span>
            <div>
              <button type="button" className="btn sm btn-ghost" disabled={offset <= 0 || loading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>上一页</button>
              <button type="button" className="btn sm btn-ghost" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => load(offset + PAGE_SIZE)}>下一页</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
