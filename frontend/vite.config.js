import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5050', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    // 避免懒加载路由预加载 CSS 失败时整页白屏（旧 index.js 缓存 + 新 hash 不一致）
    modulePreload: false,
  },
});
