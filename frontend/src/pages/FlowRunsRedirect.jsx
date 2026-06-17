import { Navigate, useSearchParams } from 'react-router-dom';

/** /flows/runs → /flows?tab=history（保留 status 等查询参数） */
export default function FlowRunsRedirect() {
  const [searchParams] = useSearchParams();
  const next = new URLSearchParams(searchParams);
  next.set('tab', 'history');
  return <Navigate to={`/flows?${next.toString()}`} replace />;
}
