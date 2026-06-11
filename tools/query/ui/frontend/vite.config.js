import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const shellSrc = path.resolve(__dirname, '../../../../frontend/src');
const mountPrefix = '/tools/query';
const isProd = process.env.NODE_ENV === 'production';

export default defineConfig({
  plugins: [react()],
  root: __dirname,
  base: isProd ? `${mountPrefix}/static/dist/` : '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@iisp': shellSrc,
    },
  },
  build: {
    outDir: path.resolve(__dirname, '..', 'static', 'dist'),
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    rollupOptions: {
      input: path.resolve(__dirname, 'src', 'main.jsx'),
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        manualChunks(id) {
          if (id.includes('@codemirror') || id.includes('@uiw/react-codemirror')) return 'codemirror';
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) return 'react-vendor';
          if (id.includes('/pages/QueryPage')) return 'page-query';
          if (id.includes('/pages/AdminPage')) return 'page-strategies';
          if (id.includes('/pages/QueryResultsPage')) return 'page-results';
          if (id.includes('/pages/HistoryPage')) return 'page-history';
        },
      },
    },
  },
  server: {
    port: 5174,
    strictPort: false,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5050', changeOrigin: true },
    },
  },
});
