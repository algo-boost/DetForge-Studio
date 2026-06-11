import { Component, Suspense, lazy } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryJobsProvider } from '@iisp/context/QueryJobsContext';
import { ToastHost } from '@iisp/components/ToastHost';
import SceneHubNav from '@iisp/components/SceneHubNav';

const QueryPage = lazy(() => import('@iisp/pages/QueryPage'));
const QueryResultsPage = lazy(() => import('@iisp/pages/QueryResultsPage'));
const HistoryPage = lazy(() => import('@iisp/pages/HistoryPage'));
const StrategiesPage = lazy(() => import('@iisp/pages/AdminPage'));

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, maxWidth: 720 }}>
          <h3>Query 工具页面出错</h3>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#b91c1c', fontSize: 12 }}>
            {String(this.state.error?.stack || this.state.error)}
          </pre>
          <button type="button" onClick={() => this.setState({ error: null })}>重试</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <HashRouter>
      <QueryJobsProvider>
        <ToastHost />
        <div className="query-tool-app panel active">
          <SceneHubNav variant="query" className="query-tool-hub" />
          <ErrorBoundary>
            <Suspense fallback={<div style={{ padding: 24 }}>加载中…</div>}>
              <Routes>
                <Route index element={<Navigate to="/query" replace />} />
                <Route path="query" element={<QueryPage />} />
                <Route path="query-results" element={<QueryResultsPage />} />
                <Route path="history" element={<HistoryPage />} />
                <Route path="strategies" element={<StrategiesPage />} />
                <Route path="admin" element={<Navigate to="/strategies" replace />} />
                <Route path="*" element={<Navigate to="/query" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </div>
      </QueryJobsProvider>
    </HashRouter>
  );
}
