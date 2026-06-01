import { useEffect, useRef, useState } from 'react';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import ManualQcTabBar from '../components/forge/manual-qc/ManualQcTabBar';
import { MATCH_LABEL, MATCH_PILL_CLASS } from '../components/forge/manual-qc/manualQcUtils';
import { buildArchiveEntries, toSqlTime } from '../utils/format';

const SN_PAGE = 50;
const QUERY_PAGE = 100;

function MatchPill({ status }) {
  const cls = MATCH_PILL_CLASS[status] || 'mqc-pill';
  return <span className={cls}>{MATCH_LABEL[status] || status || '—'}</span>;
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 16V8m0 0l-3 3m3-3l3 3" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

function ZoomIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M6 10L10 6M10 6H7M10 6V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function CompareLightbox({ data, onClose }) {
  const [zoom, setZoom] = useState(1);
  if (!data) return null;
  return (
    <div className="mqc-lightbox" onClick={onClose} role="dialog" aria-modal="true" aria-label="图片对比">
      <div className="mqc-lightbox-bar" onClick={(e) => e.stopPropagation()}>
        <span className="mqc-lightbox-title">客户图 ↔ 平台图对比</span>
        <div className="mqc-lightbox-zoom">
          <button type="button" aria-label="缩小" onClick={() => setZoom((z) => Math.max(1, z - 0.25))}>−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="放大" onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>+</button>
          <button type="button" className="mqc-lightbox-reset" onClick={() => setZoom(1)}>复位</button>
        </div>
        <button type="button" className="btn btn-sm btn-ghost mqc-lightbox-close" onClick={onClose}>关闭</button>
      </div>
      <div className="mqc-lightbox-body" onClick={(e) => e.stopPropagation()}>
        {[['客户图', data.customer], ['平台图', data.platform]].map(([label, src]) => (
          <div key={label} className="mqc-lightbox-pane">
            <div className="mqc-lightbox-label">{label}</div>
            <div className="mqc-lightbox-scroll">
              {src ? <img src={src} alt={label} style={{ transform: `scale(${zoom})` }} /> : <div className="mqc-empty-state">暂无图片</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImageDropZone({ multiple = false, busy = false, onFiles, hint, compact }) {
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);
  const pick = (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith('image/') || /\.(jpe?g|png|bmp|webp|gif)$/i.test(f.name));
    if (files.length) onFiles(multiple ? files : [files[0]]);
  };
  return (
    <div
      className={`mqc-dropzone${over ? ' is-over' : ''}${busy ? ' is-busy' : ''}${compact ? ' is-compact' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click(); } }}
    >
      <input ref={inputRef} type="file" accept="image/*" multiple={multiple} hidden
        onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
      <div className="mqc-dropzone-icon"><UploadIcon /></div>
      <div className="mqc-dropzone-text">{busy ? '上传中…' : (hint || '拖拽客户图到此处，或点击选择文件')}</div>
      <div className="mqc-dropzone-hint">支持 JPG / PNG / WebP</div>
    </div>
  );
}

function SurfaceCard({ title, desc, actions, children, className = '' }) {
  return (
    <section className={`platform-surface-card mqc-surface-card ${className}`.trim()}>
      {(title || actions) && (
        <div className="platform-surface-card-head mqc-surface-head">
          <div>
            {title && <h4>{title}</h4>}
            {desc && <p className="mqc-surface-desc">{desc}</p>}
          </div>
          {actions && <div className="mqc-surface-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

function StepBlock({ step, title, hint, children, done }) {
  return (
    <div className={`mqc-step${done ? ' is-done' : ''}`}>
      <div className="mqc-step-head">
        <span className="mqc-step-num">{step}</span>
        <div>
          <div className="mqc-step-title">{title}</div>
          {hint && <div className="mqc-step-hint">{hint}</div>}
        </div>
      </div>
      <div className="mqc-step-body">{children}</div>
    </div>
  );
}

function SingleArchive({ categories, onArchived, onCompare }) {
  const snRef = useRef(null);
  const [sn, setSn] = useState('');
  const [customer, setCustomer] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [records, setRecords] = useState(null);
  const [snLimit, setSnLimit] = useState(SN_PAGE);
  const [hasMore, setHasMore] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [noMatch, setNoMatch] = useState(false);
  const [defectType, setDefectType] = useState('');
  const [qcCategory, setQcCategory] = useState('');
  const [note, setNote] = useState('');
  const [forceArchive, setForceArchive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setSn(''); setCustomer(''); setCustomerName(''); setRecords(null); setSnLimit(SN_PAGE); setHasMore(false);
    setSelectedId(null); setNoMatch(false); setDefectType(''); setQcCategory(''); setNote(''); setForceArchive(false);
    setTimeout(() => snRef.current?.focus(), 0);
  };

  const onFiles = async (files) => {
    setUploading(true);
    try {
      const r = await api.forgeManualQcUpload(files);
      if (r.success && r.data?.length) { setCustomer(r.data[0].path); setCustomerName(r.data[0].name); toast('客户图已导入'); }
    } catch (e) { toast(e.message, 'error'); }
    finally { setUploading(false); }
  };

  const lookup = async (limit = SN_PAGE) => {
    if (!sn.trim()) { toast('请输入 SN', 'error'); return; }
    setBusy(true); setSelectedId(null); setNoMatch(false);
    try {
      const r = await api.forgeManualQcLookup(sn.trim(), limit);
      if (r.success) {
        setRecords(r.records || []);
        setHasMore((r.records || []).length >= limit);
        if (!r.records?.length) toast('该 SN 没有平台缺陷图', 'info');
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const loadMore = () => { const next = snLimit + SN_PAGE; setSnLimit(next); lookup(next); };
  const selectCard = (id) => { setSelectedId(id === selectedId ? null : id); setNoMatch(false); };
  const markNoMatch = () => { setNoMatch(true); setSelectedId(null); };

  useEffect(() => {
    if (!records?.length) return;
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.key === 'n' || e.key === 'N') { e.preventDefault(); markNoMatch(); return; }
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        const idx = records.findIndex((r) => r.id === selectedId);
        const next = records[Math.min(records.length - 1, idx + 1)] || records[0];
        setSelectedId(next.id); setNoMatch(false);
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        const idx = records.findIndex((r) => r.id === selectedId);
        const prev = records[Math.max(0, idx - 1)] || records[records.length - 1];
        setSelectedId(prev.id); setNoMatch(false);
      }
      if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey && selectedId) {
        e.preventDefault();
        selectCard(selectedId);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [records, selectedId]);

  const archive = async () => {
    if (!sn.trim()) { toast('请输入 SN', 'error'); return; }
    if (!qcCategory) { toast('请选择成像情况', 'error'); return; }
    setBusy(true);
    try {
      const entry = {
        product_no: sn.trim(), customer_img_path: customer || undefined,
        defect_type: defectType.trim() || undefined, qc_category: qcCategory,
        note: note.trim() || undefined,
        matched_detail_id: (!noMatch && selectedId) ? selectedId : undefined, no_match: noMatch, force: forceArchive,
      };
      const r = await api.forgeManualQcArchive({ entry });
      if (r.success) {
        if (r.result.duplicate_of) toast(`已归档 #${r.result.id}（注意：疑似与 #${r.result.duplicate_of} 重复）`, 'info');
        else toast(`已归档 #${r.result.id}：${qcCategory}`);
        reset(); onArchived?.();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const selectedRec = records?.find((r) => r.id === selectedId);

  return (
    <div className="mqc-archive-workspace">
      <div className="mqc-archive-grid">
        <div className="mqc-archive-side">
          <StepBlock step="1" title="导入客户图" hint="上传待核对的客户侧图片" done={!!customer}>
            {customer ? (
              <div className="mqc-thumb-card">
                <button type="button" className="mqc-thumb-preview" title="点击放大对比"
                  onClick={() => onCompare({ customer: api.imageUrl(customerName || 'img', customer), platform: selectedRec ? api.imageUrl(`d${selectedRec.id}`, selectedRec.img_path) : null })}>
                  <img src={api.imageUrl(customerName || 'img', customer)} alt={customerName} />
                </button>
                <div className="mqc-thumb-meta">
                  <span className="mqc-thumb-name" title={customer}>{customerName || customer}</span>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setCustomer(''); setCustomerName(''); }}>移除</button>
                </div>
              </div>
            ) : <ImageDropZone busy={uploading} onFiles={onFiles} />}
          </StepBlock>

          <StepBlock step="2" title="输入 SN" hint="按产品序列号检索平台缺陷图" done={!!sn.trim() && records !== null}>
            <div className="mqc-sn-row">
              <input ref={snRef} value={sn} onChange={(e) => setSn(e.target.value)} placeholder="客户提供 SN"
                onKeyDown={(e) => { if (e.key === 'Enter') { setSnLimit(SN_PAGE); lookup(SN_PAGE); } }} />
              <button type="button" className="btn btn-sm btn-primary" onClick={() => { setSnLimit(SN_PAGE); lookup(SN_PAGE); }} disabled={busy}>
                {busy ? '查询中…' : '查图'}
              </button>
            </div>
          </StepBlock>
        </div>

        <StepBlock step="3" title="选择匹配图" hint="点选对应平台图，或标记拍不到 / 找不到" done={noMatch || !!selectedId}>
          {records === null && (
            <div className="mqc-empty-state">
              <p>输入 SN 后点击「查图」，将展示该 SN 的全部平台缺陷图。</p>
            </div>
          )}
          {records !== null && (
            <>
              <div className="mqc-gallery">
                {records.map((r) => (
                  <div key={r.id} className={`mqc-tile${selectedId === r.id ? ' is-selected' : ''}`} title={r.img_path}>
                    <button type="button" className="mqc-tile-zoom" title="放大对比"
                      onClick={() => onCompare({ customer: customer ? api.imageUrl(customerName || 'img', customer) : null, platform: api.imageUrl(`d${r.id}`, r.img_path) })}>
                      <ZoomIcon />
                    </button>
                    <button type="button" className="mqc-tile-img" onClick={() => selectCard(r.id)}>
                      <img src={api.imageUrl(`d${r.id}`, r.img_path)} alt={`#${r.id}`} />
                      <span className="mqc-tile-cap">#{r.id} · {r.product_type || '—'}</span>
                    </button>
                  </div>
                ))}
                {!records.length && <div className="mqc-empty-state mqc-empty-inline">该 SN 无平台图</div>}
              </div>
              <div className="mqc-gallery-actions">
                <button type="button" className={`btn btn-sm ${noMatch ? 'btn-primary' : 'btn-ghost'}`} onClick={markNoMatch}>
                  {noMatch ? '已标记：拍不到 / 找不到' : '标记为拍不到 / 找不到'}
                </button>
                {hasMore && <button type="button" className="btn btn-sm btn-ghost" onClick={loadMore} disabled={busy}>加载更多</button>}
                <span className="mqc-kbd-hint">方向键切换 · N 标记无图</span>
              </div>
            </>
          )}
        </StepBlock>
      </div>

      <div className="mqc-verdict-bar" onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); archive(); } }}>
        <StepBlock step="4" title="标注并归档" hint="Ctrl/⌘ + Enter 快速提交">
          <div className="forge-form-grid mqc-verdict-form">
            <label>缺陷类型
              {categories.defect_strict ? (
                <select value={defectType} onChange={(e) => setDefectType(e.target.value)}>
                  <option value="">选择类别…</option>
                  {categories.defect_types.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              ) : (
                <input list="forge-defect-types" value={defectType} onChange={(e) => setDefectType(e.target.value)} placeholder="选择或输入" />
              )}
            </label>
            <label>成像情况 *
              <select value={qcCategory} onChange={(e) => setQcCategory(e.target.value)}>
                <option value="">选择类别…</option>
                {categories.imaging_categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="forge-span2">备注<input value={note} onChange={(e) => setNote(e.target.value)} placeholder="可选" /></label>
            <label className="forge-inline forge-span2 mqc-checkbox-row">
              <input type="checkbox" checked={forceArchive} onChange={(e) => setForceArchive(e.target.checked)} />
              强制归档（允许重复 SN + 客户图）
            </label>
          </div>
          <div className="mqc-verdict-footer">
            <div className="mqc-verdict-status">
              {noMatch ? <MatchPill status="not_found" /> : selectedId ? <span className="mqc-status-text">已选中平台图 <strong>#{selectedId}</strong></span> : <span className="mqc-status-text muted">未选中（归档时按 SN 自动取最新一条）</span>}
            </div>
            <div className="mqc-verdict-actions">
              <button type="button" className="btn btn-sm btn-ghost" onClick={reset}>重置</button>
              <button type="button" className="btn btn-sm btn-primary" onClick={archive} disabled={busy}>{busy ? '归档中…' : '确认归档'}</button>
            </div>
          </div>
        </StepBlock>
      </div>
    </div>
  );
}

function BatchArchive({ categories, onArchived }) {
  const [rows, setRows] = useState([]);
  const [batchId, setBatchId] = useState('');
  const [summary, setSummary] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);

  const onFiles = async (files) => {
    setUploading(true);
    try {
      const r = await api.forgeManualQcUpload(files);
      if (r.success && r.data?.length) {
        setRows((p) => [...p, ...r.data.map((d) => ({ name: d.name, path: d.path, sn: '', defect_type: '', qc_category: '', note: '' }))]);
        toast(`已导入 ${r.data.length} 张客户图`);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setUploading(false); }
  };

  const update = (i, k, v) => setRows((p) => p.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  const remove = (i) => setRows((p) => p.filter((_, idx) => idx !== i));
  const addBlank = () => setRows((p) => [...p, { name: '', path: '', sn: '', defect_type: '', qc_category: '', note: '' }]);

  const archive = async () => {
    const entries = buildArchiveEntries(rows);
    if (!entries.length) { toast('请至少填写一行 SN', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcArchive({ entries, batch_id: batchId.trim() || undefined });
      if (r.success) { setSummary(r.summary); toast(`批量归档完成：匹配 ${r.summary.matched}/${r.summary.total}`); setRows([]); onArchived?.(); }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <SurfaceCard title="批量导入" desc="拖入多张客户图，逐条填写 SN 与类别，系统将按 SN 自动匹配最新平台图">
      <div className="forge-form-grid mqc-batch-meta">
        <label>批次 ID<input value={batchId} onChange={(e) => setBatchId(e.target.value)} placeholder="可选，便于检索 / 导出" /></label>
      </div>
      <ImageDropZone multiple compact busy={uploading} onFiles={onFiles} hint="拖拽多张客户图到此处批量导入" />
      {rows.length > 0 && (
        <div className="mqc-table-wrap">
          <table className="models-table mqc-table">
            <thead><tr><th>客户图</th><th>SN *</th><th>缺陷类型</th><th>成像情况</th><th>备注</th><th></th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.path ? <img className="mqc-mini" src={api.imageUrl(r.name || 'img', r.path)} alt={r.name} /> : <span className="muted">无图</span>}</td>
                  <td><input value={r.sn} onChange={(e) => update(i, 'sn', e.target.value)} placeholder="必填" /></td>
                  <td><input list="forge-defect-types" value={r.defect_type} onChange={(e) => update(i, 'defect_type', e.target.value)} /></td>
                  <td>
                    <select value={r.qc_category} onChange={(e) => update(i, 'qc_category', e.target.value)}>
                      <option value="">—</option>
                      {categories.imaging_categories.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td><input value={r.note} onChange={(e) => update(i, 'note', e.target.value)} /></td>
                  <td><button type="button" className="btn btn-sm btn-ghost" onClick={() => remove(i)}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mqc-action-bar">
        <button type="button" className="btn btn-sm btn-ghost" onClick={addBlank}>添加空行（仅 SN）</button>
        <button type="button" className="btn btn-sm btn-primary" onClick={archive} disabled={busy || !rows.length}>{busy ? '归档中…' : `批量归档 (${rows.length})`}</button>
      </div>
      {summary && (
        <div className="mqc-summary-bar">
          共 {summary.total} 条 · 匹配 {summary.matched} · 未找到 {summary.not_found} · 多条 {summary.multiple}
        </div>
      )}
    </SurfaceCard>
  );
}

function QueryExport({ categories, reloadKey }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [cats, setCats] = useState([]);
  const [defects, setDefects] = useState([]);
  const [include, setInclude] = useState('both');
  const [outDir, setOutDir] = useState('');
  const [rows, setRows] = useState(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [exportRes, setExportRes] = useState(null);

  const toggle = (setter, list) => (c) => setter(list.includes(c) ? list.filter((x) => x !== c) : [...list, c]);

  const baseParams = () => ({
    start: toSqlTime(start) || undefined, end: toSqlTime(end) || undefined,
    categories: cats.length ? cats : undefined, defect_types: defects.length ? defects : undefined,
  });

  const buildQs = (off = 0) => {
    const q = new URLSearchParams();
    if (start) q.set('start', toSqlTime(start));
    if (end) q.set('end', toSqlTime(end));
    cats.forEach((c) => q.append('category', c));
    defects.forEach((d) => q.append('defect_type', d));
    q.set('limit', String(QUERY_PAGE)); q.set('offset', String(off));
    return q.toString();
  };

  const query = async (off = 0) => {
    setBusy(true); setExportRes(null);
    try {
      const r = await api.forgeManualQcList(`?${buildQs(off)}`);
      if (r.success) { setRows(r.data || []); setTotal(r.total || 0); setOffset(off); }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const exportDir = async () => {
    setBusy(true);
    try { const r = await api.forgeManualQcExport({ ...baseParams(), include, out_dir: outDir.trim() || undefined }); if (r.success) { setExportRes(r); toast(`已导出 ${r.copied} 张到目录`); } }
    catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const exportZip = async () => {
    setBusy(true);
    try { await api.forgeManualQcExportZip({ ...baseParams(), include }); toast('ZIP 已开始下载'); }
    catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const exportAsync = async () => {
    setBusy(true);
    try { const r = await api.forgeManualQcExport({ ...baseParams(), include, out_dir: outDir.trim() || undefined, async: true }); if (r.success) toast(`已创建后台导出作业 #${r.job_id}，到「任务」页查看`); }
    catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  useEffect(() => { if (reloadKey && rows !== null) query(offset); /* eslint-disable-next-line */ }, [reloadKey]);

  return (
    <SurfaceCard title="筛选与导出" desc="按时段、成像类别与缺陷类型查询归档记录，并导出图片">
      <div className="forge-form-grid">
        <label>开始时间<input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>结束时间<input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <label className="forge-span2">成像情况（不选 = 全部）
          <div className="forge-chips">
            {categories.imaging_categories.map((c) => (
              <button type="button" key={c} className={`forge-chip${cats.includes(c) ? ' is-on' : ''}`} onClick={() => toggle(setCats, cats)(c)}>{c}</button>
            ))}
          </div>
        </label>
        <label className="forge-span2">缺陷类型（不选 = 全部）
          <div className="forge-chips">
            {categories.defect_types.map((d) => (
              <button type="button" key={d} className={`forge-chip${defects.includes(d) ? ' is-on' : ''}`} onClick={() => toggle(setDefects, defects)(d)}>{d}</button>
            ))}
          </div>
        </label>
        <label>导出内容
          <select value={include} onChange={(e) => setInclude(e.target.value)}>
            <option value="both">平台图 + 客户图</option>
            <option value="platform">仅平台缺陷图</option>
            <option value="customer">仅客户图</option>
          </select>
        </label>
        <label>导出目录<input value={outDir} onChange={(e) => setOutDir(e.target.value)} placeholder="留空 = exports/manual_qc_export/<时间戳>" /></label>
      </div>
      <div className="mqc-action-bar">
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => query(0)} disabled={busy} data-testid="mqc-query-export-query">查询</button>
        <button type="button" className="btn btn-sm btn-primary" onClick={exportDir} disabled={busy} data-testid="mqc-query-export-dir">导出到目录</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={exportZip} disabled={busy}>下载 ZIP</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={exportAsync} disabled={busy}>后台导出</button>
      </div>
      {exportRes && (
        <div className="forge-banner-ok">
          导出完成：{exportRes.copied} 张图 / {exportRes.records} 条记录（缺失 {exportRes.missing}）→ <code className="forge-path">{exportRes.out_dir}</code>
        </div>
      )}
      {rows !== null && (
        <div className="mqc-query-results">
          <div className="mqc-query-toolbar">
            <span className="muted">共 {total} 条 · 当前 {offset + 1}–{offset + rows.length}</span>
            <span className="mqc-query-pager">
              <button type="button" className="btn btn-sm btn-ghost" disabled={busy || offset <= 0} onClick={() => query(Math.max(0, offset - QUERY_PAGE))}>上一页</button>
              <button type="button" className="btn btn-sm btn-ghost" disabled={busy || offset + QUERY_PAGE >= total} onClick={() => query(offset + QUERY_PAGE)}>下一页</button>
            </span>
          </div>
          <div className="mqc-table-wrap">
            <table className="models-table mqc-table">
              <thead><tr><th>#</th><th>SN</th><th>成像</th><th>缺陷</th><th>状态</th><th>款型</th><th>时间</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td><td>{r.product_no}</td><td>{r.qc_category || '—'}</td>
                    <td>{r.defect_type || '—'}</td><td><MatchPill status={r.match_status} /></td>
                    <td>{r.product_type || '—'}</td><td className="forge-path">{r.archived_at || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SurfaceCard>
  );
}

function RecentTable({ categories, recent, reload, onCompare }) {
  const [editId, setEditId] = useState(null);
  const [draft, setDraft] = useState({});

  const startEdit = (r) => { setEditId(r.id); setDraft({ qc_category: r.qc_category || '', defect_type: r.defect_type || '', note: r.note || '' }); };
  const save = async (id) => {
    try { const r = await api.forgeManualQcUpdate(id, draft); if (r.success) { toast('已更新'); setEditId(null); reload(); } }
    catch (e) { toast(e.message, 'error'); }
  };
  const del = async (id) => {
    try { const r = await api.forgeManualQcDelete(id); if (r.success) { toast('已删除'); reload(); } }
    catch (e) { toast(e.message, 'error'); }
  };

  return (
    <SurfaceCard
      title="最近归档"
      desc={recent.length ? `最近 ${recent.length} 条记录，支持编辑与对比` : '暂无归档记录'}
      actions={<button type="button" className="btn btn-sm btn-ghost" onClick={reload}>刷新</button>}
    >
      {!recent.length ? (
        <div className="mqc-empty-state"><p>完成首次归档后，记录将显示在此处。</p></div>
      ) : (
        <div className="mqc-table-wrap">
          <table className="models-table mqc-table">
            <thead><tr><th>#</th><th>SN</th><th>成像</th><th>缺陷</th><th>状态</th><th>款型</th><th>匹配图</th><th>备注</th><th>操作</th></tr></thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td><td>{r.product_no}</td>
                  {editId === r.id ? (
                    <>
                      <td><select value={draft.qc_category} onChange={(e) => setDraft({ ...draft, qc_category: e.target.value })}>
                        <option value="">—</option>{categories.imaging_categories.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select></td>
                      <td><input list="forge-defect-types" value={draft.defect_type} onChange={(e) => setDraft({ ...draft, defect_type: e.target.value })} /></td>
                      <td><MatchPill status={r.match_status} /></td>
                      <td>{r.product_type || '—'}</td>
                      <td><code className="forge-path">{r.matched_img_path || '—'}</code></td>
                      <td><input value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} /></td>
                      <td className="forge-actions">
                        <button type="button" className="btn btn-sm btn-primary" onClick={() => save(r.id)}>保存</button>
                        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditId(null)}>取消</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td>{r.qc_category || '—'}</td><td>{r.defect_type || '—'}</td>
                      <td><MatchPill status={r.match_status} /></td><td>{r.product_type || '—'}</td>
                      <td>
                        {r.matched_img_path
                          ? <button type="button" className="btn btn-sm btn-ghost" onClick={() => onCompare({ customer: r.customer_img_path ? api.imageUrl('c', r.customer_img_path) : null, platform: api.imageUrl('m', r.matched_img_path) })}>对比</button>
                          : <span className="muted">—</span>}
                      </td>
                      <td className="forge-path">{r.note || '—'}</td>
                      <td className="forge-actions">
                        <button type="button" className="btn btn-sm btn-ghost" onClick={() => startEdit(r)}>编辑</button>
                        <button type="button" className="btn btn-sm btn-ghost" onClick={() => del(r.id)}>删除</button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SurfaceCard>
  );
}

function CategoryConfig({ categories, onSaved }) {
  const [imaging, setImaging] = useState('');
  const [defects, setDefects] = useState('');
  const [strict, setStrict] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setImaging((categories.imaging_categories || []).join('\n'));
    setDefects((categories.defect_types || []).join('\n'));
    setStrict(!!categories.defect_strict);
  }, [categories]);

  const save = async () => {
    setBusy(true);
    try {
      const r = await api.forgeManualQcSaveCategories({
        imaging_categories: imaging.split('\n').map((s) => s.trim()).filter(Boolean),
        defect_types: defects.split('\n').map((s) => s.trim()).filter(Boolean),
        defect_strict: strict,
      });
      if (r.success) { toast('类别已保存'); onSaved?.(r); }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const cleanup = async () => {
    try {
      const dry = await api.forgeManualQcCleanupUploads(true);
      if (!dry.orphans?.length) { toast('没有未引用的客户图'); return; }
      if (!window.confirm(`发现 ${dry.orphans.length} 个未被引用的客户图，确认删除？`)) return;
      const r = await api.forgeManualQcCleanupUploads(false);
      if (r.success) toast(`已清理 ${r.deleted} 个文件`);
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <SurfaceCard title="类别配置" desc="维护成像情况与缺陷类型列表，以及缺陷输入模式">
      <div className="forge-form-grid">
        <label>成像情况（每行一个）<textarea rows={5} value={imaging} onChange={(e) => setImaging(e.target.value)} /></label>
        <label>缺陷类型（每行一个）<textarea rows={5} value={defects} onChange={(e) => setDefects(e.target.value)} /></label>
        <label className="forge-span2 mqc-checkbox-row">
          <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} />
          缺陷类型严格模式（仅允许从配置列表选择，禁止自由输入）
        </label>
      </div>
      <div className="mqc-action-bar">
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={busy}>{busy ? '保存中…' : '保存类别'}</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={cleanup}>清理未引用客户图</button>
      </div>
    </SurfaceCard>
  );
}

export default function ManualQcPage() {
  const [categories, setCategories] = useState({ imaging_categories: [], defect_types: [], defect_strict: false });
  const [recent, setRecent] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [lightbox, setLightbox] = useState(null);
  const [activeTab, setActiveTab] = useState('archive');

  const loadCategories = async () => {
    try { const r = await api.forgeManualQcCategories(); if (r.success) setCategories({ imaging_categories: r.imaging_categories || [], defect_types: r.defect_types || [], defect_strict: !!r.defect_strict }); }
    catch (e) { /* ignore */ }
  };
  const loadRecent = async () => {
    try { const r = await api.forgeManualQcList('?limit=50'); if (r.success) setRecent(r.data || []); }
    catch (e) { /* ignore */ }
  };

  useEffect(() => { loadCategories(); loadRecent(); }, []);
  const onArchived = () => { loadRecent(); setReloadKey((k) => k + 1); };

  const tabCounts = { records: recent.length };

  return (
    <div className="panel active mqc-page">
      <SceneHubNav variant="query" />
      <header className="mqc-header">
        <div>
          <div className="topbar-title">人工质检</div>
          <p className="mqc-header-desc">导入客户图 → 检索 SN → 匹配平台图 → 标注归档 → 按时段导出</p>
        </div>
        <div className="mqc-header-stats">
          <div className="mqc-stat">
            <span className="mqc-stat-value">{recent.length}</span>
            <span className="mqc-stat-label">最近记录</span>
          </div>
          <div className="mqc-stat">
            <span className="mqc-stat-value">{categories.imaging_categories.length}</span>
            <span className="mqc-stat-label">成像类别</span>
          </div>
          <div className="mqc-stat">
            <span className="mqc-stat-value">{categories.defect_types.length}</span>
            <span className="mqc-stat-label">缺陷类型</span>
          </div>
        </div>
      </header>

      <ManualQcTabBar activeTab={activeTab} onTabChange={setActiveTab} counts={tabCounts} />

      <div className="mqc-workspace">
        {activeTab === 'archive' && (
          <SurfaceCard title="核对归档" desc="单条客户图与平台缺陷图的人工匹配工作流">
            <SingleArchive categories={categories} onArchived={onArchived} onCompare={setLightbox} />
          </SurfaceCard>
        )}
        {activeTab === 'batch' && <BatchArchive categories={categories} onArchived={onArchived} />}
        {activeTab === 'query' && <QueryExport categories={categories} reloadKey={reloadKey} />}
        {activeTab === 'records' && <RecentTable categories={categories} recent={recent} reload={loadRecent} onCompare={setLightbox} />}
        {activeTab === 'settings' && <CategoryConfig categories={categories} onSaved={loadCategories} />}
        <datalist id="forge-defect-types">{categories.defect_types.map((d) => <option key={d} value={d} />)}</datalist>
      </div>

      <CompareLightbox data={lightbox} onClose={() => setLightbox(null)} />
    </div>
  );
}
