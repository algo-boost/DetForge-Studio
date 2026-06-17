import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../api/client';
import PlatformPredictPanel from '../../forge/PlatformPredictPanel';

/** 嵌入完整批量预测 UI（项目 / 数据源 / 模型 / 阈值 / 设备） */
export default function PredictComposeModule({ value, onChange, bindHints = [] }) {
  const taskBound = bindHints.some((h) => h.param === 'task_id' && h.ok);
  const [projects, setProjects] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(value?._ui?.projectId ?? null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, dRes] = await Promise.all([
        api.forgeSyncProjects(),
        api.forgeSyncDatasets(selectedProjectId ? `?project_id=${selectedProjectId}` : ''),
      ]);
      if (pRes.success) setProjects(pRes.data || []);
      if (dRes.success) setDatasets(dRes.data || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!projects.length || selectedProjectId != null) return;
    const uiPid = value?._ui?.projectId;
    if (uiPid && projects.some((p) => p.id === uiPid)) {
      setSelectedProjectId(uiPid);
      return;
    }
    const preferred = projects.find((p) => p.approach_id) || projects[0];
    setSelectedProjectId(preferred?.id ?? null);
  }, [projects, selectedProjectId, value?._ui?.projectId]);

  const project = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  if (loading && !projects.length) {
    return <p className="muted compose-module-loading">加载预测配置…</p>;
  }

  return (
    <div className="compose-module-embed compose-module-predict">
      {value?._ui?.multiModelNote && (
        <p className="compose-step-hint">{value._ui.multiModelNote}</p>
      )}
      <PlatformPredictPanel
        project={project}
        projects={projects}
        onProjectChange={setSelectedProjectId}
        datasets={datasets}
        preselectedDatasetId={value?._ui?.datasetId ? Number(value._ui.datasetId) : null}
        composeMode
        composeParams={value}
        onComposeParamsChange={onChange}
        upstreamTaskBound={taskBound}
        standalone
        compactIntro
        wideLayout={false}
        allowLocalDir={!taskBound}
      />
    </div>
  );
}
