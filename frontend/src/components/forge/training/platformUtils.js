export function parseSubjectId(url) {
  if (!url) return null;
  const m = String(url).match(/subjectId=(\d+)/);
  return m ? m[1] : null;
}

export function buildPlatformPages(project) {
  if (!project?.approach_id) return null;
  const approachId = project.approach_id;
  const subjectId = parseSubjectId(project.training_page_url);
  const subjectQ = subjectId ? `&subjectId=${subjectId}` : '';
  const origin = 'https://www.ai.magic-fox.com';
  let training = String(project.training_page_url || '').trim();
  if (training) {
    if (!training.startsWith('http')) {
      training = training.startsWith('#') ? `${origin}/${training}` : `${origin}/#/${training.replace(/^\//, '')}`;
    }
  } else {
    training = `${origin}/#/training?approachId=${approachId}${subjectQ}`;
  }
  return {
    datasets: `${origin}/#/datasets?approachId=${approachId}${subjectQ}`,
    snapshots: `${origin}/#/enhance?approachId=${approachId}${subjectQ}`,
    training,
  };
}

export function buildPlatformDataViewUrl(ds, project) {
  const saved = String(ds.data_view_url || '').trim();
  if (saved) return saved;
  const approachId = project?.approach_id;
  const subjectId = parseSubjectId(project?.training_page_url);
  const subjectQ = subjectId ? `&subjectId=${subjectId}` : '';
  if (ds.source_type === 'dataset' && approachId && ds.source_id) {
    return (
      `https://www.ai.magic-fox.com/#/datasets/dataView?approachId=${approachId}`
      + `&datasetId=${ds.source_id}&enhanceDatasetId=${ds.source_id}${subjectQ}`
      + '&fuzzy_name=&sort_type=m_time'
    );
  }
  if (approachId && ds.source_type === 'snapshot') {
    return `https://www.ai.magic-fox.com/#/enhance?approachId=${approachId}${subjectId ? `&subjectId=${subjectId}` : ''}`;
  }
  return null;
}

export const PLATFORM_TABS = [
  { id: 'overview', label: '概览', desc: '工作流与快捷操作' },
  { id: 'discover', label: '发现导入', desc: '从 URL 批量导入' },
  { id: 'datasets', label: '数据集', desc: '同步与管理' },
  { id: 'trace', label: '样本溯源', desc: 'SN / 款型 / 时间' },
  { id: 'predict', label: '模型预测', desc: '多模型批量预测' },
  { id: 'jobs', label: '同步任务', desc: '后台作业' },
];

export function tabFromHash() {
  const h = (window.location.hash || '').replace(/^#/, '');
  const found = PLATFORM_TABS.find((t) => t.id === h);
  return found ? found.id : null;
}
