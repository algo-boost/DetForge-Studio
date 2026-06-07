import { useEffect, useRef, useState } from 'react';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import ManualQcTabBar from '../components/forge/manual-qc/ManualQcTabBar';
import ArchiveEditPanel from '../components/forge/manual-qc/ArchiveEditPanel';
import ArchiveLibrary from '../components/forge/manual-qc/ArchiveLibrary';
import IntakePanel from '../components/forge/manual-qc/IntakePanel';
import ReviewPanel from '../components/forge/manual-qc/ReviewPanel';
import { todayBatchId } from '../components/forge/manual-qc/manualQcUtils';

function SurfaceCard({ title, desc, children, className = '' }) {
  return (
    <section className={`platform-surface-card mqc-surface-card ${className}`.trim()}>
      {(title || desc) && (
        <div className="platform-surface-card-head mqc-surface-head">
          <div>
            {title && <h4>{title}</h4>}
            {desc && <p className="mqc-surface-desc">{desc}</p>}
          </div>
        </div>
      )}
      {children}
    </section>
  );
}

function ArchiveRootConfig({ summary, onSaved }) {
  const [root, setRoot] = useState('');
  const [autoSync, setAutoSync] = useState(false);
  const [include, setInclude] = useState('both');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setRoot(summary?.archive_root || '');
    setAutoSync(!!summary?.archive_auto_sync);
    setInclude(summary?.archive_include || 'both');
  }, [summary]);

  const save = async () => {
    setBusy(true);
    try {
      const r = await api.forgeManualQcSaveArchiveSettings({
        archive_root: root.trim(),
        auto_sync: autoSync,
        include,
      });
      if (r.success) {
        toast('归档目录配置已保存');
        onSaved?.(r);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <SurfaceCard
      title="归档根目录"
      desc="配置后可将已定案记录自动同步到该目录（年/月/日/成像类别/SN/图片 + SN 级 COCO）；亦可作为统一归档库"
    >
      <div className="forge-form-grid">
        <label className="forge-span2">
          归档根目录（服务器路径）
          <input
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="例如 exports/manual_qc_archive 或 D:/QCArchive"
          />
        </label>
        {summary?.archive_root_resolved && (
          <p className="forge-span2 muted mqc-api-hint">
            解析路径：<code className="forge-path">{summary.archive_root_resolved}</code>
          </p>
        )}
        <label>
          同步内容
          <select value={include} onChange={(e) => setInclude(e.target.value)}>
            <option value="both">平台图 + 客户图</option>
            <option value="platform">仅平台缺陷图</option>
            <option value="customer">仅客户图</option>
          </select>
        </label>
        <label className="forge-inline mqc-checkbox-row">
          <input type="checkbox" checked={autoSync} onChange={(e) => setAutoSync(e.target.checked)} />
          确认归档时自动写入根目录
        </label>
      </div>
      <div className="mqc-action-bar">
        <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={busy}>
          {busy ? '保存中…' : '保存归档配置'}
        </button>
      </div>
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
        <label>
          成像情况（每行一个，默认：未拍到、成像不清、检出、漏检）
          <textarea rows={5} value={imaging} onChange={(e) => setImaging(e.target.value)} placeholder={'未拍到\n成像不清\n检出\n漏检'} />
        </label>
        <label>缺陷类型（每行一个）<textarea rows={5} value={defects} onChange={(e) => setDefects(e.target.value)} /></label>
        <label className="forge-span2 mqc-checkbox-row">
          <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} />
          缺陷类型严格模式（仅允许从配置列表选择，禁止自由输入）
        </label>
      </div>
      <div className="mqc-api-hint muted">
        批量登记 API：<code>POST /api/forge/manual-qc/intake</code>
        {' '}· 上传：<code>POST /api/forge/manual-qc/upload</code>
        {' '}· 脚本示例：<code>scripts/manual_qc_intake.py</code>
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
  const [summary, setSummary] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [lightbox, setLightbox] = useState(null);
  const [activeTab, setActiveTab] = useState('intake');
  const [reviewFocusId, setReviewFocusId] = useState(null);
  const [reviewImmersive, setReviewImmersive] = useState(false);
  const [libraryEditId, setLibraryEditId] = useState(null);
  const didAutoReviewTab = useRef(false);

  const loadCategories = async () => {
    try {
      const r = await api.forgeManualQcCategories();
      if (r.success) {
        setCategories({
          imaging_categories: r.imaging_categories || [],
          defect_types: r.defect_types || [],
          defect_strict: !!r.defect_strict,
        });
      }
    } catch (e) { /* ignore */ }
  };
  const loadSummary = async () => {
    try {
      const r = await api.forgeManualQcSummary();
      if (r.success) setSummary(r);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => { loadCategories(); loadSummary(); }, []);

  useEffect(() => {
    if (didAutoReviewTab.current || !summary) return;
    const pending = (summary.intake_count || 0) + (summary.confirmed_count || 0);
    if (pending > 0) {
      didAutoReviewTab.current = true;
      setActiveTab('review');
    }
  }, [summary]);
  const onArchived = () => { loadSummary(); setReloadKey((k) => k + 1); };
  const onIntaked = ({ firstId } = {}) => {
    loadSummary();
    setReviewFocusId(firstId || null);
    setActiveTab('review');
  };

  const tabCounts = {
    review: (summary?.intake_count || 0) + (summary?.confirmed_count || 0),
    library: summary?.pending || 0,
  };

  const onTabChange = (tab) => {
    setActiveTab(tab);
    if (tab !== 'library') setLibraryEditId(null);
  };

  const immersiveActive = reviewImmersive && (
    (activeTab === 'review') || (activeTab === 'library' && libraryEditId)
  );

  return (
    <div className={`panel active mqc-page${immersiveActive ? ' mqc-page-immersive' : ''}`}>
      <SceneHubNav variant="qc" />
      <div className="mqc-chrome-sticky">
        <header className="mqc-header">
        <div>
          <div className="topbar-title">人工质检</div>
          <p className="mqc-header-desc">
            登记入队 → 核对确认（左客户 / 右平台检测框）→ 归档库（批次 <code>{todayBatchId()}</code>）
          </p>
        </div>
        <div className="mqc-header-stats">
          <div className="mqc-stat">
            <span className="mqc-stat-value">{summary?.intake_count ?? 0}</span>
            <span className="mqc-stat-label">待核对</span>
          </div>
          <div className="mqc-stat">
            <span className="mqc-stat-value">{summary?.confirmed_count ?? 0}</span>
            <span className="mqc-stat-label">待确认</span>
          </div>
          <div className="mqc-stat">
            <span className="mqc-stat-value">{summary?.total ?? 0}</span>
            <span className="mqc-stat-label">已定案</span>
          </div>
        </div>
        </header>

        <ManualQcTabBar activeTab={activeTab} onTabChange={onTabChange} counts={tabCounts} />
      </div>

      <div className="mqc-workspace">
        {activeTab === 'intake' && (
          <SurfaceCard title="登记入队" desc="导入客户图与 SN，写入待核对队列（可通过 API / 脚本批量导入）">
            <IntakePanel onIntaked={onIntaked} />
          </SurfaceCard>
        )}
        {activeTab === 'review' && (
          <SurfaceCard
            title={reviewImmersive ? null : '核对确认'}
            desc={reviewImmersive ? null : '左客户图、右平台检测框；Ctrl+Enter 单条确认归档'}
            className={`mqc-review-card${reviewImmersive ? ' mqc-review-card-immersive' : ''}`}
          >
            <ReviewPanel
              categories={categories}
              onArchived={onArchived}
              focusId={reviewFocusId}
              onImmersiveChange={setReviewImmersive}
            />
          </SurfaceCard>
        )}
        {activeTab === 'library' && (
          libraryEditId ? (
            <ArchiveEditPanel
              recordId={libraryEditId}
              categories={categories}
              onBack={() => setLibraryEditId(null)}
              onSaved={() => { loadSummary(); setReloadKey((k) => k + 1); }}
              onImmersiveChange={setReviewImmersive}
            />
          ) : (
            <ArchiveLibrary
              categories={categories}
              reloadKey={reloadKey}
              onCompare={setLightbox}
              onOpenEdit={setLibraryEditId}
            />
          )
        )}
        {activeTab === 'settings' && (
          <>
            <ArchiveRootConfig summary={summary} onSaved={loadSummary} />
            <CategoryConfig categories={categories} onSaved={loadCategories} />
          </>
        )}
        <datalist id="forge-defect-types">{categories.defect_types.map((d) => <option key={d} value={d} />)}</datalist>
      </div>

      {lightbox && (
        <div className="mqc-lightbox" onClick={() => setLightbox(null)} role="presentation">
          <div className="mqc-lightbox-body" onClick={(e) => e.stopPropagation()}>
            {lightbox.customer && <img src={lightbox.customer} alt="客户" />}
            {lightbox.platform && <img src={lightbox.platform} alt="平台" />}
          </div>
        </div>
      )}
    </div>
  );
}
