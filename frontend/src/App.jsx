import { Component, Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ToastHost } from './components/ToastHost';

const QueryPage = lazy(() => import('./pages/QueryPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
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
      return (
        <div style={{ padding: 24 }}>
          <h3>页面出错了</h3>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#b91c1c' }}>{String(this.state.error?.stack || this.state.error)}</pre>
          <button type="button" onClick={() => this.setState({ error: null })}>重试</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastHost />
      <ErrorBoundary>
        <Suspense fallback={<div className="panel active" style={{ padding: 24 }}>加载中…</div>}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<QueryPage />} />
              <Route path="config" element={<SettingsPage />} />
              <Route path="admin" element={<Navigate to="/config?section=strategy" replace />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="curation" element={<CurationPage />} />
              <Route path="models" element={<ModelsPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="training" element={<TrainingPlatformPage />} />
              <Route path="sync" element={<Navigate to="/training" replace />} />
              <Route path="manual-qc" element={<ManualQcPage />} />
              <Route path="docs" element={<Navigate to="/config?section=docs" replace />} />
              <Route path="viewer" element={<ViewerPage />} />
              <Route path="online-predict" element={<OnlinePredictPage />} />
              <Route path="compare" element={<Navigate to="/online-predict" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
