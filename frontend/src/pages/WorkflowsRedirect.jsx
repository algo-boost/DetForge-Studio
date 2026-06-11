import { Navigate, useSearchParams } from 'react-router-dom';
import { flowRunPath, parseRunKeyFromParams } from '../lib/flowsRun';

/** 兼容旧书签 /workflows?run=9 → /flows/runs/workflow:9 */
export default function WorkflowsRedirect() {
  const [searchParams] = useSearchParams();
  const runKey = parseRunKeyFromParams(searchParams);
  if (runKey) {
    return <Navigate to={flowRunPath(runKey)} replace />;
  }
  return <Navigate to="/flows/runs" replace />;
}
