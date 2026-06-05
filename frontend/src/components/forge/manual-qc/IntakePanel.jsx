import { useState } from 'react';
import { api, toast } from '../../../api/client';
import { todayBatchId } from './manualQcUtils';

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 16V8m0 0l-3 3m3-3l3 3" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

function ImageDropZone({ multiple = true, busy = false, onFiles }) {
  const [over, setOver] = useState(false);
  const pick = (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith('image/') || /\.(jpe?g|png|bmp|webp|gif)$/i.test(f.name));
    if (files.length) onFiles(files);
  };
  return (
    <div
      className={`mqc-dropzone${over ? ' is-over' : ''}${busy ? ' is-busy' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      onClick={() => document.getElementById('mqc-intake-file')?.click()}
      role="button"
      tabIndex={0}
    >
      <input id="mqc-intake-file" type="file" accept="image/*" multiple={multiple} hidden
        onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
      <div className="mqc-dropzone-icon"><UploadIcon /></div>
      <div className="mqc-dropzone-text">{busy ? '上传中…' : '拖拽客户图到此处，或点击选择（可多选）'}</div>
      <div className="mqc-dropzone-hint">登记后进入「核对确认」队列 · 亦可用 API POST /api/forge/manual-qc/intake</div>
    </div>
  );
}

export default function IntakePanel({ onIntaked }) {
  const [rows, setRows] = useState([]);
  const [batchId, setBatchId] = useState(() => todayBatchId());
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);

  const onFiles = async (files) => {
    setUploading(true);
    try {
      const r = await api.forgeManualQcUpload(files);
      if (r.success && r.data?.length) {
        setRows((p) => [
          ...p,
          ...r.data.map((d) => ({
            name: d.name, path: d.path, sn: '', note: '', external_ref: '',
          })),
        ]);
        toast(`已上传 ${r.data.length} 张`);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setUploading(false); }
  };

  const update = (i, k, v) => setRows((p) => p.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  const remove = (i) => setRows((p) => p.filter((_, idx) => idx !== i));

  const submit = async () => {
    const entries = rows
      .filter((r) => r.sn?.trim())
      .map((r) => ({
        product_no: r.sn.trim(),
        customer_img_path: r.path,
        note: r.note?.trim() || undefined,
        external_ref: r.external_ref?.trim() || undefined,
      }));
    if (!entries.length) { toast('请至少填写一行 SN', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeManualQcIntake({ entries, batch_id: batchId.trim() || undefined, source: 'ui' });
      if (r.success) {
        const s = r.summary || {};
        toast(`登记 ${s.created || 0} 条${s.errors ? `，失败 ${s.errors}` : ''}`);
        if (s.errors) toast(r.errors?.[0]?.error || '部分登记失败', 'error');
        setRows((p) => p.filter((row) => !row.sn?.trim() || r.errors?.some((e) => e.entry?.customer_img_path === row.path)));
        const firstId = r.created?.[0]?.id ?? r.result?.id ?? null;
        onIntaked?.({ firstId });
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <div className="mqc-intake-panel">
      <div className="forge-form-grid mqc-batch-meta">
        <label>批次 ID
          <input value={batchId} onChange={(e) => setBatchId(e.target.value)} placeholder="默认当日 YYYY-MM-DD" />
        </label>
        <label className="mqc-batch-today-hint">
          <span className="muted">登记仅入队，不匹配平台图</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setBatchId(todayBatchId())}>
            设为今日 {todayBatchId()}
          </button>
        </label>
      </div>
      <ImageDropZone busy={uploading} onFiles={onFiles} />
      {rows.length > 0 && (
        <div className="mqc-table-wrap">
          <table className="models-table mqc-table">
            <thead>
              <tr><th>客户图</th><th>SN *</th><th>外部引用</th><th>备注</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.path}-${i}`}>
                  <td>
                    {r.path
                      ? <img className="mqc-mini" src={api.imageUrl(r.name || 'img', r.path)} alt={r.name} />
                      : <span className="muted">无图</span>}
                  </td>
                  <td><input value={r.sn} onChange={(e) => update(i, 'sn', e.target.value)} placeholder="必填" /></td>
                  <td><input value={r.external_ref} onChange={(e) => update(i, 'external_ref', e.target.value)} placeholder="可选，API 幂等" /></td>
                  <td><input value={r.note} onChange={(e) => update(i, 'note', e.target.value)} /></td>
                  <td><button type="button" className="btn btn-sm btn-ghost" onClick={() => remove(i)}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mqc-action-bar">
        <button type="button" className="btn btn-sm btn-primary" onClick={submit} disabled={busy || !rows.length}>
          {busy ? '登记中…' : `登记入队 (${rows.filter((r) => r.sn?.trim()).length})`}
        </button>
      </div>
    </div>
  );
}
