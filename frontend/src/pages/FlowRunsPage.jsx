import { Link } from 'react-router-dom';
import FlowRunsHistoryPanel from '../components/flows/FlowRunsHistoryPanel';
import FlowsSceneShell from '../components/flows/FlowsSceneShell';
import { api, toast } from '../api/client';

/** 兼容旧路由；主入口为 /flows?tab=history */
export default function FlowRunsPage() {
  const resumeFlow = async (item) => {
    const runKey = item?.meta?.run_key
      || (item?.href?.includes('/flows/runs/') ? decodeURIComponent(item.href.split('/flows/runs/')[1] || '') : '');
    if (!runKey) return;
    try {
      const r = await api.orchestrationResume({ run_key: runKey });
      if (r.success) toast('已继续执行', 'success');
      else toast(r.error || 'Resume 失败', 'error');
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  };

  return (
    <FlowsSceneShell layout="wide">
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">执行历史</h1>
          <p className="flows-page-desc">全部运行的执行记录与待人工处理</p>
        </div>
        <Link to="/flows" className="btn btn-sm">流水线目录</Link>
      </header>
      <FlowRunsHistoryPanel onResume={resumeFlow} />
    </FlowsSceneShell>
  );
}
