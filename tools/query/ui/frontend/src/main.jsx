import { mountUrl } from './mount.js';

const _fetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  if (typeof input === 'string') {
    return _fetch(mountUrl(input), init);
  }
  if (input instanceof Request) {
    const u = mountUrl(input.url);
    if (u !== input.url) {
      return _fetch(new Request(u, input), init);
    }
  }
  return _fetch(input, init);
};

import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import '@iisp/styles/app.css';

const container = document.getElementById('root');
if (container) {
  createRoot(container).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
