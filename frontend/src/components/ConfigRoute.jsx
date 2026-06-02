import { Navigate, useSearchParams } from 'react-router-dom';
import ConfigPage from '../pages/ConfigPage';

/** /config 仅系统设置；旧 ?section=strategy|docs 重定向到新路由 */
export default function ConfigRoute() {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section');
  if (section === 'strategy') return <Navigate to="/strategies" replace />;
  if (section === 'docs') return <Navigate to="/docs" replace />;
  return <ConfigPage />;
}
