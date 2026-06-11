import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
// 本地字体（@fontsource）：离线/无网环境也能加载品牌字体，替代远程 Google Fonts。
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/dm-sans/400-italic.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import './styles/app.css';
import './styles/status.css';
import './styles/command-palette.css';
import './styles/flow-studio.css';
import './styles/config.css';
import './styles/inspection-results.css';
import './styles/mqc-viewer.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
