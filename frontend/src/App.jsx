import { Component, Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ToastHost } from './components/ToastHost';
import { QueryJobsProvider } from './context/QueryJobsContext';

const QueryPage = lazy(() => import('./pages/QueryPage'));
const QueryResultsPage = lazy(() => import('./pages/QueryResultsPage'));
const ConfigRoute = lazy(() => import('./components/ConfigRoute'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const ModelsPage = lazy(() => import('./pages/ModelsPage'));
const JobsPage = lazy(() => import('./pages/JobsPage'));
const TrainingPlatformPage = lazy(() => import('./pages/TrainingPlatformPage'));
const ManualQcPage = lazy(() => import('./pages/ManualQcPage'));
const CurationPage = lazy(() => import('./pages/CurationPage'));
const ViewerPage = lazy(() => import('./pages/ViewerPage'));
const OnlinePredictPage = lazy(() => import('./pages/OnlinePredictPage'));

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      const msg = String(this.state.error?.message || this.state.error || '');
      const staleAssets = /preload CSS|Loading chunk|Failed to fetch dynamically imported module/i.test(msg);
      return (
        <div style={{ padding: 24, maxWidth: 720 }}>
          <h3>页面出错了</h3>
          {staleAssets && (
            <p style={{ color: '#b45309', marginBottom: 12 }}>
              多为前端资源缓存过期（构建后浏览器仍使用旧的 index.js）。请点「强制刷新」或按 Ctrl+F5。
            </p>
          )}
          <pre style={{ whiteSpace: 'pre-wrap', color: '#b91c1c', fontSize: 12 }}>{String(this.state.error?.stack || this.state.error)}</pre>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button type="button" onClick={() => this.setState({ error: null })}>重试</button>
            {staleAssets && (
              <button type="button" onClick={() => window.location.reload()}>强制刷新</button>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <QueryJobsProvider>
        <ToastHost />
        <ErrorBoundary>
          <Suspense fallback={<div className="panel active" style={{ padding: 24 }}>加载中…</div>}>
            <Routes>
              <Route element={<Layout />}>
              <Route index element={<QueryPage />} />
              <Route path="query-results" element={<QueryResultsPage />} />
              <Route path="config" element={<ConfigRoute />} />
              <Route path="strategies" element={<AdminPage />} />
              <Route path="admin" element={<Navigate to="/strategies" replace />} />
              <Route path="settings" element={<Navigate to="/config" replace />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="curation" element={<CurationPage />} />
              <Route path="models" element={<ModelsPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="training" element={<TrainingPlatformPage />} />
              <Route path="sync" element={<Navigate to="/training" replace />} />
              <Route path="manual-qc" element={<ManualQcPage />} />
              <Route path="docs" element={<DocsPage />} />
              <Route path="viewer" element={<ViewerPage />} />
              <Route path="online-predict" element={<OnlinePredictPage />} />
              <Route path="compare" element={<Navigate to="/online-predict" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </QueryJobsProvider>
    </BrowserRouter>
  );
}
