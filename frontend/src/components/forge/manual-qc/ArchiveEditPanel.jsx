import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, openSampleGalleryWhenReady, toast } from '../../../api/client';
import {
  DEFAULT_RESULT_FILTER,
  itemMatchesFilter,
} from '../../../lib/resultFilters';
import ManualQcCompareWorkbench from './ManualQcCompareWorkbench';
import MqcRevisionHistory from './MqcRevisionHistory';
import { normalizePlatformRecord } from './manualQcUtils';

const SN_PAGE = 100;
const LS_IMMERSIVE = 'mqc-review-immersive';

function readImmersive() {
  try {
    if (localStorage.getItem(LS_IMMERSIVE) === '1') return true;
  } catch { /* ignore */ }
  return false;
}

export default function ArchiveEditPanel({
  recordId,
  categories,
  onBack,
  onSaved,
  onImmersiveChange,
}) {
  const [activeCase, setActiveCase] = useState(null);
  const [records, setRecords] = useState(null);
  const [filter, setFilter] = useState({ ...DEFAULT_RESULT_FILTER });
  const [onlyWithBoxes, setOnlyWithBoxes] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [noMatch, setNoMatch] = useState(false);
  const [defectType, setDefectType] = useState('');
  const [qcCategory, setQcCategory] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [lookupBusy, setLookupBusy] = useState(false);
  const [immersive, setImmersive] = useState(readImmersive);
  const [vizOpening, setVizOpening] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);

  const loadRecord = useCallback(async () => {
    if (!recordId) return;
    try {
      const r = await api.forgeManualQcGet(recordId);
      if (r.success && r.data) {
        setActiveCase(r.data);
      }
    } catch (e) {
      toast(e.message, 'error');
      onBack?.();
    }
  }, [recordId, onBack]);

  const loadHistory = useCallback(async () => {
    if (!recordId) return;
    setHistoryBusy(true);
    try {
      const r = await api.forgeManualQcHistory(recordId);
      if (r.success) setHistory(r.data || []);
    } catch { /* ignore */ }
    finally { setHistoryBusy(false); }
  }, [recordId]);

  useEffect(() => { loadRecord(); loadHistory(); }, [loadRecord, loadHistory]);

  useEffect(() => {
    onImmersiveChange?.(immersive && !!activeCase);
    try { localStorage.setItem(LS_IMMERSIVE, immersive ? '1' : '0'); } catch { /* ignore */ }
  }, [immersive, activeCase, onImmersiveChange]);

  const loadCandidates = useCallback(async (sn) => {
    if (!sn?.trim()) { setRecords([]); return; }
    setLookupBusy(true);
    try {
      const r = await api.forgeManualQcLookup(sn.trim(), SN_PAGE);
      if (r.success) setRecords(r.records || []);
    } catch (e) {
      toast(e.message, 'error');
      setRecords(null);
    } finally { setLookupBusy(false); }
  }, []);

  useEffect(() => {
    if (!activeCase) return;
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
    if (onlyWithBoxes) items = items.filter((r) => (r.annotations || []).length > 0);
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
    if (noMatch || !filteredItems.length || !activeCase) return;
    const mid = activeCase.matched_detail_id;
    if (mid) {
      const idx = filteredItems.findIndex((r) => r.id === mid);
      if (idx >= 0) {
        setActiveIndex(idx);
        setNoMatch(false);
        return;
      }
    }
    if (activeIndex >= filteredItems.length) setActiveIndex(0);
  }, [filteredItems, activeCase, noMatch, activeIndex]);

  const saveRevision = async () => {
    if (!activeCase) return;
    if (!qcCategory) { toast('请选择成像情况', 'error'); return; }
    const selectedDetailId = noMatch ? null : filteredItems[activeIndex]?.id ?? null;
    if (!noMatch && !selectedDetailId) { toast('请选择平台图或标记无匹配', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcRevise(activeCase.id, {
        matched_detail_id: noMatch ? undefined : selectedDetailId,
        no_match: noMatch,
        qc_category: qcCategory,
        defect_type: defectType.trim() || undefined,
        note: note.trim() || undefined,
      });
      if (r.success) {
        toast('已保存修订');
        setActiveCase(r.record || activeCase);
        loadHistory();
        onSaved?.(r.record);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
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

  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          saveRevision();
        }
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        saveRevision();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        onBack?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const customerUrl = activeCase?.customer_img_path
    ? api.imageUrl('cust', activeCase.customer_img_path)
    : null;

  if (!activeCase) {
    return (
      <div className="mqc-empty-state">
        <p>加载归档记录…</p>
      </div>
    );
  }

  return (
    <div className={`mqc-archive-edit${immersive ? ' is-immersive' : ''}`}>
      <ManualQcCompareWorkbench
        mode="archive"
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
        onBack={onBack}
        immersive={immersive}
        onToggleImmersive={() => setImmersive((v) => !v)}
        categories={categories}
        defectType={defectType}
        onDefectTypeChange={setDefectType}
        qcCategory={qcCategory}
        onQcCategoryChange={setQcCategory}
        note={note}
        onNoteChange={setNote}
        onSaveReview={saveRevision}
        onConfirm={saveRevision}
        busy={busy}
        onOpenViz={openVizGallery}
        vizOpening={vizOpening}
        sidebarExtra={(
          <section className="detail-panel mqc-history-panel">
            <h3 className="detail-panel-title">变更历史</h3>
            <MqcRevisionHistory entries={history} loading={historyBusy} />
          </section>
        )}
      />
    </div>
  );
}
