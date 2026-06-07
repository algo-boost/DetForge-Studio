import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../../../api/client';
import { showErrorModal, showResultModal } from '../../../lib/feedbackModal';
import { MATCH_LABEL, MATCH_PILL_CLASS, TRAINING_LABEL, todayBatchId } from './manualQcUtils';

const PAGE = 100;

function MatchPill({ status }) {
  const cls = MATCH_PILL_CLASS[status] || 'mqc-pill';
  return <span className={cls}>{MATCH_LABEL[status] || status || '—'}</span>;
}

function TrainingPill({ status }) {
  const st = status || 'pending';
  return <span className={`mqc-pill mqc-pill-training mqc-pill-training-${st}`}>{TRAINING_LABEL[st] || st}</span>;
}

function batchFilterParams(batch) {
  if (!batch) return {};
  if (batch.batch_id) return { batch_id: batch.batch_id };
  const day = batch.batch_day || batch.batch_key;
  if (day) return { start: `${day} 00:00:00`, end: `${day} 23:59:59` };
  return { batch_id: batch.batch_key };
}

function buildListQs(filters, off = 0) {
  const q = new URLSearchParams();
  if (filters.batch_id) q.set('batch_id', filters.batch_id);
  if (filters.start) q.set('start', filters.start);
  if (filters.end) q.set('end', filters.end);
  if (filters.product_no) q.set('product_no', filters.product_no);
  if (filters.training_status) q.set('training_status', filters.training_status);
  filters.categories?.forEach((c) => q.append('category', c));
  filters.defect_types?.forEach((d) => q.append('defect_type', d));
  q.set('limit', String(PAGE));
  q.set('offset', String(off));
  return q.toString();
}

export default function ArchiveLibrary({ categories, reloadKey, onCompare, onOpenEdit }) {
  const [summary, setSummary] = useState(null);
  const [batches, setBatches] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [rows, setRows] = useState(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sn, setSn] = useState('');
  const [trainingFilter, setTrainingFilter] = useState('');
  const [cats, setCats] = useState([]);
  const [defects, setDefects] = useState([]);
  const [include, setInclude] = useState('both');
  const [outDir, setOutDir] = useState('');
  const [busy, setBusy] = useState(false);

  const listFilters = useMemo(() => {
    const base = batchFilterParams(selectedBatch);
    if (sn.trim()) base.product_no = sn.trim();
    if (trainingFilter) base.training_status = trainingFilter;
    if (cats.length) base.categories = cats;
    if (defects.length) base.defect_types = defects;
    return base;
  }, [selectedBatch, sn, trainingFilter, cats, defects]);

  const loadMeta = useCallback(async () => {
    try {
      const [s, b] = await Promise.all([
        api.forgeManualQcSummary(),
        api.forgeManualQcBatches('?limit=60'),
      ]);
      if (s.success) setSummary(s);
      if (b.success) setBatches(b.data || []);
    } catch (e) { /* ignore */ }
  }, []);

  const query = useCallback(async (off = 0) => {
    setBusy(true);
    try {
      const r = await api.forgeManualQcList(`?${buildListQs(listFilters, off)}`);
      if (r.success) {
        setRows(r.data || []);
        setTotal(r.total || 0);
        setOffset(off);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  }, [listFilters]);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  useEffect(() => {
    if (reloadKey) {
      loadMeta();
      query(0);
    }
  }, [reloadKey, loadMeta, query]);

  useEffect(() => {
    query(0);
  }, [query]);

  const selectBatch = (batch) => {
    setSelectedBatch(batch);
    setOffset(0);
  };

  const toggle = (setter, list) => (c) => setter(list.includes(c) ? list.filter((x) => x !== c) : [...list, c]);

  const exportParams = () => ({
    ...listFilters,
    include,
    out_dir: outDir.trim() || undefined,
  });

  const exportDir = async () => {
    setBusy(true);
    try {
      const r = await api.forgeManualQcExport(exportParams());
      if (r.success) {
        showResultModal(
          `已导出 ${r.copied} 张图 / ${r.records} 条${r.coco_count ? ` · COCO ${r.coco_count} 份` : ''}`,
          { title: '导出完成', detail: r.out_dir ? `目录：${r.out_dir}` : '' },
        );
      }
    } catch (e) { showErrorModal(e.message, { title: '导出失败' }); }
    finally { setBusy(false); }
  };

  const exportZip = async () => {
    setBusy(true);
    try {
      await api.forgeManualQcExportZip(exportParams());
      showResultModal('ZIP 文件已开始下载', { title: '导出完成' });
    } catch (e) { showErrorModal(e.message, { title: '导出失败' }); }
    finally { setBusy(false); }
  };

  const syncArchiveRoot = async () => {
    if (!summary?.archive_root_resolved) {
      showErrorModal('请先在「设置」中配置归档根目录', { title: '无法同步' });
      return;
    }
    if (!window.confirm('将当前筛选范围内的全部已定案记录同步到归档根目录？')) return;
    setBusy(true);
    try {
      const r = await api.forgeManualQcArchiveSync(listFilters);
      if (r.success) {
        showResultModal(
          `已同步 ${r.copied} 张图到归档目录${r.coco_count ? `（COCO ${r.coco_count} 份）` : ''}`,
          { title: '同步完成', detail: r.out_dir ? `目录：${r.out_dir}` : '' },
        );
      }
    } catch (e) { showErrorModal(e.message, { title: '同步失败' }); }
    finally { setBusy(false); }
  };

  const handoff = async () => {
    setBusy(true);
    try {
      const r = await api.forgeManualQcHandoff({
        ...listFilters,
        training_status: 'pending',
      });
      if (r.success) {
        const dir = r.handoff_dir || r.out_dir || '';
        const lines = [
          `样本 ${r.record_count} 条`,
          r.images_copied != null ? `复制图片 ${r.images_copied} 张` : '',
          `运行码 ${r.run_code}`,
          dir ? `目录（服务器路径）：\n${dir}` : '',
          r.coco_path ? `COCO：${r.coco_path}` : '',
          '内含 images/、_annotations.coco.json、manifest.csv、README.md',
        ].filter(Boolean).join('\n\n');
        showResultModal(lines, { title: '训练交接包已生成' });
        loadMeta();
        query(offset);
      }
    } catch (e) { showErrorModal(e.message, { title: '生成交接包失败' }); }
    finally { setBusy(false); }
  };

  const openRecord = (r) => {
    if (onOpenEdit) onOpenEdit(r.id);
  };

  const del = async (id, e) => {
    e?.stopPropagation();
    if (!window.confirm(`确认删除归档 #${id}？`)) return;
    try {
      const r = await api.forgeManualQcDelete(id);
      if (r.success) { toast('已删除'); query(offset); loadMeta(); }
    } catch (e) { showErrorModal(e.message, { title: '删除失败' }); }
  };

  const todayId = summary?.daily_batch_id || todayBatchId();
  const inboxRoot = summary?.handoff_inbox_root || '';
  const exportRoot = summary?.export_default_root || 'exports/manual_qc_export/';
  const archiveRoot = summary?.archive_root_resolved || summary?.archive_root || '';
  const globalPending = summary?.pending ?? 0;
  const handoffDisabledReason = globalPending <= 0
    ? '无「待交接」且已匹配平台图的已定案记录'
    : '';

  return (
    <div className="mqc-library">
      <aside className="mqc-library-side">
        <div className="mqc-library-side-head">
          <strong>按日 / 批次</strong>
          <span className="muted">{batches.length}</span>
        </div>
        <p className="mqc-library-side-hint muted">新归档默认归入当日批次 <code>{todayId}</code></p>
        <button
          type="button"
          className={`mqc-batch-item${!selectedBatch ? ' is-active' : ''}`}
          onClick={() => selectBatch(null)}
        >
          <span className="mqc-batch-title">全部记录</span>
          <span className="mqc-batch-meta">{summary?.total ?? '—'} 条</span>
        </button>
        <div className="mqc-batch-list">
          {batches.map((b) => (
            <button
              key={b.batch_key}
              type="button"
              className={`mqc-batch-item${selectedBatch?.batch_key === b.batch_key ? ' is-active' : ''}`}
              onClick={() => selectBatch(b)}
            >
              <span className="mqc-batch-title">{b.batch_key}</span>
              <span className="mqc-batch-meta">
                {b.total} 条
                {(b.pending || 0) > 0 && <em> · 待交接 {b.pending}</em>}
              </span>
              <span className="mqc-batch-time muted">{String(b.last_at || '').slice(0, 16)}</span>
            </button>
          ))}
        </div>
      </aside>

      <div className="mqc-library-main">
        <section className="mqc-library-stats">
          <div className="mqc-library-stat">
            <span className="mqc-library-stat-val">{summary?.total ?? 0}</span>
            <span className="muted">总归档</span>
          </div>
          <div className="mqc-library-stat mqc-library-stat-warn">
            <span className="mqc-library-stat-val">{summary?.pending ?? 0}</span>
            <span className="muted">待交接训练</span>
          </div>
          <div className="mqc-library-stat mqc-library-stat-ok">
            <span className="mqc-library-stat-val">{summary?.handoff_ready ?? 0}</span>
            <span className="muted">已生成交接包</span>
          </div>
        </section>

        <section className="platform-surface-card mqc-surface-card mqc-library-panel">
          <div className="platform-surface-card-head mqc-surface-head">
            <div>
              <h4>筛选</h4>
              <p className="mqc-surface-desc">
                {selectedBatch ? `当前批次：${selectedBatch.batch_key}` : '查看全部归档记录'}
              </p>
            </div>
          </div>
          <div className="forge-form-grid mqc-library-filters">
            <label>SN 搜索
              <input value={sn} onChange={(e) => setSn(e.target.value)} placeholder="精确匹配 SN" />
            </label>
            <label>训练状态
              <select value={trainingFilter} onChange={(e) => setTrainingFilter(e.target.value)}>
                <option value="">全部</option>
                <option value="pending">待交接</option>
                <option value="handoff_ready">已交接</option>
                <option value="closed">已关闭</option>
              </select>
            </label>
            <label className="forge-span2">成像情况
              <div className="forge-chips">
                {categories.imaging_categories.map((c) => (
                  <button type="button" key={c} className={`forge-chip${cats.includes(c) ? ' is-on' : ''}`} onClick={() => toggle(setCats, cats)(c)}>{c}</button>
                ))}
              </div>
            </label>
          </div>
          <div className="mqc-action-bar">
            <button type="button" className="btn btn-sm btn-primary" onClick={() => query(0)} disabled={busy} data-testid="mqc-library-query">查询</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setSn(''); setTrainingFilter(''); setCats([]); setDefects([]); setSelectedBatch(null); setRows(null); }} disabled={busy}>重置筛选</button>
          </div>
        </section>

        {rows !== null && (
          <section className="platform-surface-card mqc-surface-card">
            <div className="platform-surface-card-head mqc-surface-head">
              <div>
                <h4>归档记录</h4>
                <p className="mqc-surface-desc">点击行进入与核对台相同的修订界面 · 共 {total} 条</p>
              </div>
            </div>
            <div className="mqc-table-wrap">
              <table className="models-table mqc-table">
                <thead>
                  <tr>
                    <th>#</th><th>批次</th><th>SN</th><th>成像</th><th>缺陷</th>
                    <th>匹配</th><th>训练</th><th>时间</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.id}
                      className="mqc-library-row-clickable"
                      onClick={() => openRecord(r)}
                      title="点击进入修订（对照看图 + 变更历史）"
                    >
                      <td>{r.id}</td>
                      <td><code className="forge-path">{r.batch_id || String(r.archived_at || '').slice(0, 10)}</code></td>
                      <td>{r.product_no}</td>
                      <td>{r.qc_category || '—'}</td>
                      <td>{r.defect_type || '—'}</td>
                      <td><MatchPill status={r.match_status} /></td>
                      <td>
                        <TrainingPill status={r.training_status} />
                        {r.handoff_dir && <div className="mqc-handoff-path muted" title={r.handoff_dir}>↗ 已打包</div>}
                      </td>
                      <td className="forge-path">{String(r.archived_at || '').slice(0, 16)}</td>
                      <td className="forge-actions" onClick={(e) => e.stopPropagation()}>
                        <button type="button" className="btn btn-sm btn-primary" onClick={() => openRecord(r)}>打开</button>
                        {(r.customer_img_path || r.matched_img_path) && (
                          <button type="button" className="btn btn-sm btn-ghost" onClick={() => onCompare({
                            customer: r.customer_img_path ? api.imageUrl('c', r.customer_img_path) : null,
                            platform: r.matched_img_path ? api.imageUrl('m', r.matched_img_path) : null,
                          })}
                          >快览</button>
                        )}
                        <button type="button" className="btn btn-sm btn-ghost" onClick={(e) => del(r.id, e)}>删除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {total > PAGE && (
              <div className="mqc-query-pager">
                <button type="button" className="btn btn-sm btn-ghost" disabled={busy || offset <= 0} onClick={() => query(Math.max(0, offset - PAGE))}>上一页</button>
                <button type="button" className="btn btn-sm btn-ghost" disabled={busy || offset + PAGE >= total} onClick={() => query(offset + PAGE)}>下一页</button>
              </div>
            )}
          </section>
        )}

        <section className="platform-surface-card mqc-surface-card mqc-library-export">
          <div className="platform-surface-card-head mqc-surface-head">
            <div>
              <h4>导出与训练交接</h4>
              <p className="mqc-surface-desc">对<strong>当前筛选范围</strong>内的记录操作；交接包写入训练收件箱</p>
            </div>
          </div>

          <div className="mqc-path-cards">
            <div className="mqc-path-card">
              <div className="mqc-path-card-label">归档根目录（持续同步）</div>
              {archiveRoot ? (
                <code className="forge-path">{archiveRoot}/&lt;年&gt;/&lt;月&gt;/&lt;日&gt;/&lt;成像类别&gt;/&lt;SN&gt;/</code>
              ) : (
                <span className="muted">未配置 — 请在「设置 → 归档根目录」填写</span>
              )}
              <p className="muted">
                含图片与 SN 目录级 _annotations.coco.json；
                {summary?.archive_auto_sync ? ' 确认归档时自动写入' : ' 可手动「同步到归档目录」'}
              </p>
            </div>
            <div className="mqc-path-card">
              <div className="mqc-path-card-label">一次性导出（默认）</div>
              <code className="forge-path">{exportRoot}/&lt;时间戳&gt;/&lt;年&gt;/&lt;月&gt;/&lt;日&gt;/…</code>
              <p className="muted">含 manifest.csv；SN 目录下图片 + COCO</p>
            </div>
            <div className="mqc-path-card">
              <div className="mqc-path-card-label">训练交接包（COCO + images）</div>
              <code className="forge-path">{inboxRoot || '…/datasets/training_inbox/'}/qc_&lt;时间&gt;_xxx/</code>
              <p className="muted">
                写入服务器目录（非浏览器下载）；仅含已匹配平台图且状态为「待交接」的记录；
                生成后状态变为「已交接」
              </p>
            </div>
          </div>

          <div className="forge-form-grid">
            <label>导出内容
              <select value={include} onChange={(e) => setInclude(e.target.value)}>
                <option value="both">平台图 + 客户图</option>
                <option value="platform">仅平台缺陷图</option>
                <option value="customer">仅客户图</option>
              </select>
            </label>
            <label>自定义导出目录
              <input value={outDir} onChange={(e) => setOutDir(e.target.value)} placeholder="留空使用 exports/manual_qc_export/" />
            </label>
          </div>

          <div className="mqc-action-bar">
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={syncArchiveRoot}
              disabled={busy || !archiveRoot}
              title={archiveRoot ? '写入配置的归档根目录' : '请先配置归档根目录'}
            >
              同步到归档目录
            </button>
            <button type="button" className="btn btn-sm btn-primary" onClick={exportDir} disabled={busy} data-testid="mqc-library-export-dir">导出到指定目录</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={exportZip} disabled={busy}>下载 ZIP</button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={handoff}
              disabled={busy || globalPending <= 0}
              title={handoffDisabledReason || '对当前筛选范围内的待交接记录打包'}
              data-testid="mqc-library-handoff"
            >
              生成交接包（待交接 {globalPending}）
            </button>
            <Link to="/curation" className="btn btn-sm btn-ghost">筛选归档总览 →</Link>
          </div>
        </section>
      </div>
    </div>
  );
}
