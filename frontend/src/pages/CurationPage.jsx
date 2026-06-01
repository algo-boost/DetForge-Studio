import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import ReplayRunWizard from '../components/ReplayRunWizard';
import SceneLoopHub from '../components/curation/SceneLoopHub';
import BatchFlowPanel from '../components/curation/BatchFlowPanel';
import { Modal } from '../components/Modal';
import { INTENT_LABEL, STATUS_LABEL } from '../lib/curationFlow';

const INTENT_FILTERS = [
  { id: 'all', label: '全部' },
  { id: 'daily_ng', label: '每日 NG' },
  { id: 'replay_eval', label: '历史回跑' },
  { id: 'customer_qc', label: '人工质检' },
];

function StatusPill({ status }) {
  return <span className={`cur-pill cur-pill-${status || 'created'}`}>{STATUS_LABEL[status] || status}</span>;
}

export default function CurationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get('id') ? Number(searchParams.get('id')) : null;
  const showReplayWizard = searchParams.get('replay') === '1' || searchParams.get('wizard') === 'replay';
  const replayJobId = searchParams.get('job_id') || searchParams.get('predict_job');

  const [batches, setBatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [batch, setBatch] = useState(null);
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [schemaOk, setSchemaOk] = useState(true);
  const [qcSummary, setQcSummary] = useState(null);
  const [intentFilter, setIntentFilter] = useState('all');
  const [deleteTarget, setDeleteTarget] = useState(null);

  const loadList = useCallback(async () => {
    try {
      const r = await api.forgeArchiveHandoffList('?limit=50');
      setBatches(r.curation_batches || []);
      setTotal(r.total_curation || 0);
      setQcSummary(r.manual_qc_summary || null);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, []);

  const loadDetail = useCallback(async (id) => {
    if (!id) { setBatch(null); setItems([]); return; }
    try {
      const [b, it] = await Promise.all([
        api.forgeCurationGet(id),
        api.forgeCurationItems(id, '?limit=200'),
      ]);
      setBatch(b.data);
      setItems(it.data || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, []);

  useEffect(() => {
    api.forgeSchemaStatus().then((r) => setSchemaOk(!!r.ready)).catch(() => setSchemaOk(false));
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const selectBatch = (id) => {
    if (id) setSearchParams({ id: String(id) });
    else setSearchParams({});
  };

  const openReplayWizard = () => setSearchParams({ replay: '1' });

  const onReplayCreated = (batchId) => {
    if (batchId) setSearchParams({ id: String(batchId) });
  };

  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      await fn();
      if (okMsg) toast(okMsg);
      await loadList();
      if (selectedId) await loadDetail(selectedId);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const onExport = () => run(
    () => api.forgeCurationExport(selectedId, { include_images: true }),
    '出站包已生成',
  );

  const onImportFile = async (file) => {
    if (!file || !selectedId) return;
    setBusy(true);
    try {
      const r = await api.forgeCurationImport(selectedId, file);
      const msg = r.matched_keep != null
        ? `COCO 回传：保留 ${r.keep} / 剔除 ${r.reject}`
        : `已匹配 ${r.matched} 条；保留 ${r.keep} / 剔除 ${r.reject}`;
      toast(msg);
      await loadList();
      await loadDetail(selectedId);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const onArchiveHandoff = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      await api.forgeCurationArchive(selectedId, { treat_pending_as: 'reject' });
      await api.forgeCurationHandoff(selectedId, { split: 'both' });
      toast('归档并生成交接包完成');
      await loadList();
      await loadDetail(selectedId);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const onHandoff = (split = 'both') => run(
    () => api.forgeCurationHandoff(selectedId, { split }),
    '训练交接包已生成',
  );

  const onQcHandoff = () => run(
    () => api.forgeManualQcHandoff({ training_status: 'pending' }),
    '人工质检交接包已生成',
  );

  const onHandoffDone = () => run(
    () => api.forgeCurationHandoffDone(selectedId, { note: '训练侧已领取' }),
    '已标记为已交接',
  );

  const initSchema = () => run(() => api.forgeSchemaInit(), '写库表已初始化');

  const confirmDelete = async () => {
    if (!deleteTarget?.id) return;
    const id = deleteTarget.id;
    setBusy(true);
    try {
      await api.forgeCurationDelete(id);
      toast(`已删除批次 ${deleteTarget.batch_code}`, 'success');
      setDeleteTarget(null);
      if (selectedId === id) selectBatch(null);
      await loadList();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const filteredBatches = intentFilter === 'all'
    ? batches
    : batches.filter((b) => b.intent_type === intentFilter);

  const onFilterIntent = (intent) => {
    setIntentFilter(intent);
    selectBatch(null);
  };

  return (
    <div className="cur-page">
      <SceneHubNav variant="query" />
      <header className="cur-header">
        <div>
          <h1 className="topbar-title">筛选归档</h1>
          <p className="cur-header-desc">管理 NG 捞取、历史回跑等归档批次：导出 COCO → 外部筛图 → 回传 → 交接训练</p>
        </div>
        {!schemaOk && (
          <button type="button" className="btn btn-primary" onClick={initSchema} disabled={busy}>
            初始化写库表
          </button>
        )}
      </header>

      <div className="cur-layout">
        <aside className="cur-list-panel">
          <div className="cur-list-head">
            <strong>历史批次</strong>
            <span className="muted">{total}</span>
          </div>
          <div className="cur-intent-filters">
            {INTENT_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`cur-intent-chip${intentFilter === f.id ? ' is-active' : ''}`}
                onClick={() => setIntentFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {filteredBatches.length === 0 ? (
            <p className="cur-list-empty muted">暂无批次</p>
          ) : (
            <ul className="cur-batch-list">
              {filteredBatches.map((b) => (
                <li key={b.id} className={`cur-batch-row${selectedId === b.id ? ' is-active' : ''}`}>
                  <button
                    type="button"
                    className="cur-batch-item"
                    onClick={() => selectBatch(b.id)}
                  >
                    <div className="cur-batch-code">{b.batch_code}</div>
                    <div className="cur-batch-meta">
                      <StatusPill status={b.status} />
                      <span>{INTENT_LABEL[b.intent_type] || b.intent_label || '—'}</span>
                    </div>
                    <div className="cur-batch-counts muted">
                      留 {b.keep_count} · 剔 {b.reject_count}
                    </div>
                  </button>
                  <button
                    type="button"
                    className="cur-batch-delete"
                    title="删除批次"
                    disabled={busy}
                    onClick={() => setDeleteTarget(b)}
                    data-testid={`curation-delete-${b.id}`}
                  >
                    删除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="cur-detail-panel">
          {showReplayWizard && !selectedId ? (
            <ReplayRunWizard
              initialJobId={replayJobId}
              onCreated={onReplayCreated}
              onCancel={() => setSearchParams({})}
            />
          ) : batch ? (
            <BatchFlowPanel
              batch={batch}
              items={items}
              busy={busy}
              onExport={onExport}
              onImportFile={onImportFile}
              onArchiveHandoff={onArchiveHandoff}
              onHandoff={onHandoff}
              onHandoffDone={onHandoffDone}
              onDeleteRequest={setDeleteTarget}
            />
          ) : (
            <SceneLoopHub
              qcSummary={qcSummary}
              onReplay={openReplayWizard}
              onQcHandoff={onQcHandoff}
              onFilterIntent={onFilterIntent}
              busy={busy}
            />
          )}
        </main>
      </div>

      <Modal open={!!deleteTarget} title="确认删除批次" onClose={() => !busy && setDeleteTarget(null)}>
        <div className="cur-delete-modal">
          <p>
            确定要删除批次 <code className="cur-delete-code">{deleteTarget?.batch_code}</code> 吗？
          </p>
          <p className="muted">
            将永久删除该批次及其全部条目记录，此操作不可恢复。已生成的出站/归档目录不会自动从磁盘删除。
          </p>
          <div className="cur-delete-actions">
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setDeleteTarget(null)}>
              取消
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={busy}
              onClick={confirmDelete}
              data-testid="curation-delete-confirm"
            >
              {busy ? '删除中…' : '确认删除'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
