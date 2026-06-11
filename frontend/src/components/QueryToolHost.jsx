import { lazy } from 'react';
import ToolHost from './ToolHost';

const PAGES = {
  query: lazy(() => import('../pages/QueryPage')),
  'query-results': lazy(() => import('../pages/QueryResultsPage')),
  history: lazy(() => import('../pages/HistoryPage')),
  strategies: lazy(() => import('../pages/AdminPage')),
};

export default function QueryToolHost({ page }) {
  return <ToolHost toolId="query" page={page} pages={PAGES} />;
}
