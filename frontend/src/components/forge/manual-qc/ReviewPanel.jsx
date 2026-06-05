import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, openSampleGalleryWhenReady, toast } from '../../../api/client';
import {
  DEFAULT_RESULT_FILTER,
  itemMatchesFilter,
} from '../../../lib/resultFilters';
import ManualQcCompareWorkbench from './ManualQcCompareWorkbench';
import { normalizePlatformRecord } from './manualQcUtils';

const SN_PAGE = 100;
const LS_IMMERSIVE = 'mqc-review-immersive';

function readImmersive() {
  try {
    const v = localStorage.getItem(LS_IMMERSIVE);
    if (v === '1') return true;
    if (v === '0') return false;
  } catch { /* ignore */ }
  return false;
}

export default function ReviewPanel({ categories, onArchived, focusId, onImmersiveChange }) {
  const [queue, setQueue] = useState([]);
  const [confirmed, setConfirmed] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [records, setRecords] = useState(null);
  const [filter, setFilter] = useState({ ...DEFAULT_RESULT_FILTER });
  const [onlyWithBoxes, setOnlyWithBoxes] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [noMatch, setNoMatch] = useState(false);
  const [defectType, setDefectType] = useState('');
  const [qcCategory, setQcCategory] = useState('');
  const [note, setNote] = useState('');
  const [forceArchive, setForceArchive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lookupBusy, setLookupBusy] = useState(false);
  const [selectedConfirm, setSelectedConfirm] = useState(new Set());
  const [immersive, setImmersive] = useState(readImmersive);
  const [queueCollapsed, setQueueCollapsed] = useState(false);
  const [vizOpening, setVizOpening] = useState(false);

  const loadQueues = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([
        api.forgeManualQcQueue('?status=intake&limit=200'),
        api.forgeManualQcQueue('?status=confirmed&limit=200'),
      ]);
      if (a.success) setQueue(a.data || []);
      if (b.success) setConfirmed(b.data || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadQueues(); }, [loadQueues]);

  useEffect(() => {
    if (focusId) setActiveId(Number(focusId));
  }, [focusId]);

  const activeCase = useMemo(() => {
    const all = [...queue, ...confirmed];
    return all.find((r) => r.id === activeId) || null;
  }, [queue, confirmed, activeId]);

  useEffect(() => {
    onImmersiveChange?.(immersive && !!activeCase);
    try { localStorage.setItem(LS_IMMERSIVE, immersive ? '1' : '0'); } catch { /* ignore */ }
  }, [immersive, activeCase, onImmersiveChange]);

  useEffect(() => {
    if (immersive) setQueueCollapsed(true);
    else if (!activeCase) setQueueCollapsed(false);
  }, [immersive, activeCase]);

  useEffect(() => {
    if (focusId) return;
    if (activeId != null) return;
    const first = queue[0] || confirmed[0];
    if (first) setActiveId(first.id);
  }, [queue, confirmed, focusId, activeId]);

  const loadCandidates = useCallback(async (sn) => {
    if (!sn?.trim()) { setRecords([]); return; }
    setLookupBusy(true);
    setNoMatch(false);
    setActiveIndex(0);
    try {
      const r = await api.forgeManualQcLookup(sn.trim(), SN_PAGE);
      if (r.success) setRecords(r.records || []);
    } catch (e) {
      toast(e.message, 'error');
      setRecords(null);
    } finally { setLookupBusy(false); }
  }, []);

  useEffect(() => {
    if (!activeCase) {
      setRecords(null);
      setNoMatch(false);
      setDefectType('');
      setQcCategory('');
      setNote('');
      setFilter({ ...DEFAULT_RESULT_FILTER });
      setOnlyWithBoxes(false);
      setActiveIndex(0);
      return;
    }
    setDefectType(activeCase.defect_type || '');
    setQcCategory(activeCase.qc_category || '');
    setNote(activeCase.note || '');
    setNoMatch(activeCase.match_status === 'not_found');
    setFilter({ ...DEFAULT_RESULT_FILTER });
    setOnlyWithBoxes(false);
    loadCandidates(activeCase.product_no);
  }, [activeCase, loadCandidates]);

  const viewItems = useMemo(
    () => (records || []).map((r, i) => normalizePlatformRecord(r, i)).filter(Boolean),
    [records],
  );

  const filteredItems = useMemo(() => {
    let items = viewItems;
    if (onlyWithBoxes) {
      items = items.filter((r) => (r.annotations || []).length > 0);
    }
    if (Object.values(filter).some((v) => v != null && String(v).trim() !== '')) {
      items = items.filter((r) => itemMatchesFilter(r, filter));
    }
    return items;
  }, [viewItems, filter, onlyWithBoxes]);

  const ngTotal = useMemo(() => viewItems.filter((r) => String(r.check_status) === '1').length, [viewItems]);
  const boxTotal = useMemo(
    () => viewItems.filter((r) => (r.annotations || []).length > 0).length,
    [viewItems],
  );

  useEffect(() => {
    if (noMatch || !filteredItems.length) return;
    const matchedId = activeCase?.matched_detail_id;
    if (matchedId) {
      const idx = filteredItems.findIndex((r) => r.id === matchedId);
      if (idx >= 0) {
        setActiveIndex(idx);
        setNoMatch(false);
        return;
      }
    }
    if (activeIndex >= filteredItems.length) setActiveIndex(0);
  }, [filteredItems, activeCase, noMatch, activeIndex]);

  const selectedDetailId = noMatch ? null : filteredItems[activeIndex]?.id ?? null;

  const reviewPayload = () => ({
    matched_detail_id: noMatch ? undefined : selectedDetailId,
    no_match: noMatch,
    qc_category: qcCategory,
    defect_type: defectType.trim() || undefined,
    note: note.trim() || undefined,
    force: forceArchive,
  });

  const saveReview = async () => {
    if (!activeCase) return;
    if (!qcCategory) { toast('请选择成像情况', 'error'); return; }
    if (!noMatch && !selectedDetailId) { toast('请选择平台图或标记无匹配', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcReview(activeCase.id, reviewPayload());
      if (r.success) {
        toast('已暂存待确认');
        await loadQueues();
        setActiveId(null);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const confirmCurrent = async () => {
    if (!activeCase) return;
    if (!qcCategory) { toast('请选择成像情况', 'error'); return; }
    if (!noMatch && !selectedDetailId) { toast('请选择平台图或标记无匹配', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcConfirm({ id: activeCase.id, ...reviewPayload() });
      if (r.success) {
        toast(`已归档 #${r.result?.id}`);
        await loadQueues();
        onArchived?.();
        const next = queue.find((x) => x.id !== activeCase.id) || confirmed[0];
        setActiveId(next?.id || null);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const confirmSelected = async () => {
    const ids = selectedConfirm.size > 0 ? [...selectedConfirm] : confirmed.map((r) => r.id);
    if (!ids.length) { toast('无待确认条目', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcConfirm({ ids, force: forceArchive });
      if (r.success) {
        toast(`已归档 ${r.summary?.archived || 0} 条`);
        setSelectedConfirm(new Set());
        await loadQueues();
        onArchived?.();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const voidCase = async (id) => {
    try {
      await api.forgeManualQcVoid([id]);
      toast('已作废');
      if (activeId === id) setActiveId(null);
      loadQueues();
    } catch (e) { toast(e.message, 'error'); }
  };

  const openVizGallery = async () => {
    if (!activeCase?.product_no) return;
    setVizOpening(true);
    try {
      await openSampleGalleryWhenReady(
        () => api.forgeManualQcVizOpen({ product_no: activeCase.product_no, limit: SN_PAGE }),
        '人工质检 SN 平台图',
        { returnTo: '/manual-qc', newWindow: true },
      );
    } catch (e) { toast(e.message, 'error'); }
    finally { setVizOpening(false); }
  };

  const navCandidate = useCallback((delta) => {
    setNoMatch(false);
    setActiveIndex((i) => {
      const next = i + delta;
      if (next < 0 || next >= filteredItems.length) return i;
      return next;
    });
  }, [filteredItems.length]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          confirmCurrent();
        }
        return;
      }
      if (e.key === 'ArrowLeft') { e.preventDefault(); navCandidate(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); navCandidate(1); }
      if (e.key === 'n' || e.key === 'N') { e.preventDefault(); setNoMatch(true); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); confirmCurrent(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const customerUrl = activeCase?.customer_img_path
    ? api.imageUrl('cust', activeCase.customer_img_path)
    : null;

  const toggleConfirmSel = (id) => {
    setSelectedConfirm((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  return (
    <div className={`mqc-review-layout${immersive ? ' is-immersive' : ''}${queueCollapsed ? ' queue-collapsed' : ''}`}>
      <aside className={`mqc-review-queue${queueCollapsed ? ' is-collapsed' : ''}`}>
        <div className="mqc-review-queue-toolbar">
          {!queueCollapsed && (
            <>
              <div className="mqc-review-queue-head">
                <strong>待核对</strong>
                <span className="muted">{queue.length}</span>
              </div>
              <ul className="mqc-review-queue-list">
                {queue.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={`mqc-review-queue-item${activeId === r.id ? ' is-active' : ''}`}
                      onClick={() => setActiveId(r.id)}
                    >
                      <span className="mqc-review-queue-sn">{r.product_no}</span>
                      <span className="muted">#{r.id}</span>
                    </button>
                  </li>
                ))}
                {!queue.length && <li className="mqc-empty-inline muted">暂无，请先在「登记入队」导入</li>}
              </ul>
              <div className="mqc-review-queue-head">
                <strong>待确认</strong>
                <span className="muted">{confirmed.length}</span>
              </div>
              <ul className="mqc-review-queue-list">
                {confirmed.map((r) => (
                  <li key={r.id} className="mqc-review-confirmed-row">
                    <label className="mqc-checkbox-row">
                      <input
                        type="checkbox"
                        checked={selectedConfirm.has(r.id)}
                        onChange={() => toggleConfirmSel(r.id)}
                      />
                    </label>
                    <button
                      type="button"
                      className={`mqc-review-queue-item${activeId === r.id ? ' is-active' : ''}`}
                      onClick={() => setActiveId(r.id)}
                    >
                      <span>{r.qc_category || '—'}</span>
                      <span className="muted">#{r.id}</span>
                    </button>
                  </li>
                ))}
              </ul>
              {confirmed.length > 0 && (
                <button type="button" className="btn btn-sm btn-primary mqc-review-batch-btn" onClick={confirmSelected} disabled={busy}>
                  确认归档所选 ({selectedConfirm.size || confirmed.length})
                </button>
              )}
            </>
          )}
        </div>
        <button
          type="button"
          className="mqc-review-queue-toggle"
          onClick={() => setQueueCollapsed((v) => !v)}
          title={queueCollapsed ? '展开队列' : '收起队列'}
        >
          {queueCollapsed ? '›' : '‹'}
        </button>
      </aside>

      <div className="mqc-review-main">
        {!activeCase && (
          <div className="mqc-review-welcome">
            <h3 className="mqc-review-welcome-title">核对确认</h3>
            <p className="mqc-review-welcome-desc">
              {queue.length || confirmed.length
                ? '请从左侧队列选择一条案卷，开始客户图与平台检测图对照。'
                : '当前没有待核对案卷，请先在「登记入队」导入客户图与 SN。'}
            </p>
            <div className="mqc-review-welcome-stats">
              <span>待核对 <strong>{queue.length}</strong></span>
              <span>待确认 <strong>{confirmed.length}</strong></span>
            </div>
            {queue.length > 0 && (
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={() => setActiveId(queue[0].id)}
              >
                开始核对第一条（{queue[0].product_no}）
              </button>
            )}
          </div>
        )}
        {activeCase && (
          <ManualQcCompareWorkbench
            activeCase={activeCase}
            customerUrl={customerUrl}
            rawCount={viewItems.length}
            ngTotal={ngTotal}
            boxTotal={boxTotal}
            filteredItems={filteredItems}
            activeIndex={activeIndex}
            onActiveIndexChange={(idx) => { setNoMatch(false); setActiveIndex(idx); }}
            filter={filter}
            onFilterChange={setFilter}
            onFilterReset={() => setFilter({ ...DEFAULT_RESULT_FILTER })}
            onlyWithBoxes={onlyWithBoxes}
            onOnlyWithBoxesChange={setOnlyWithBoxes}
            noMatch={noMatch}
            onNoMatch={setNoMatch}
            lookupBusy={lookupBusy}
            onRefresh={() => loadCandidates(activeCase.product_no)}
            onVoid={voidCase}
            immersive={immersive}
            onToggleImmersive={() => setImmersive((v) => !v)}
            categories={categories}
            defectType={defectType}
            onDefectTypeChange={setDefectType}
            qcCategory={qcCategory}
            onQcCategoryChange={setQcCategory}
            note={note}
            onNoteChange={setNote}
            forceArchive={forceArchive}
            onForceArchiveChange={setForceArchive}
            onSaveReview={saveReview}
            onConfirm={confirmCurrent}
            busy={busy}
            onOpenViz={openVizGallery}
            vizOpening={vizOpening}
          />
        )}
      </div>
    </div>
  );
}
