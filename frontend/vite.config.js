import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5050', changeOrigin: true },
      '/kestra-embed': { target: 'http://127.0.0.1:5050', changeOrigin: true },
      '/tools/query': { target: 'http://127.0.0.1:5050', changeOrigin: true },
      '/viz': { target: 'http://127.0.0.1:5050', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    // 避免懒加载路由预加载 CSS 失败时整页白屏（旧 index.js 缓存 + 新 hash 不一致）
    modulePreload: false,
    rollupOptions: {
      output: {
        // 将体积大、变动少的第三方库拆成独立可缓存 chunk：
        // - codemirror 仅在查询编辑器懒加载路由命中时才加载，从大 query chunk 中剥离；
        // - react / router 抽成稳定 vendor，应用代码改动不再使其缓存失效。
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (/[\\/]node_modules[\\/](@codemirror|@lezer|@uiw[\\/]react-codemirror|codemirror|crelt|style-mod|w3c-keyname)[\\/]/.test(id)) {
            return 'vendor-codemirror';
          }
          if (/[\\/]node_modules[\\/](react-router|react-router-dom|@remix-run)[\\/]/.test(id)) {
            return 'vendor-router';
          }
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler|object-assign)[\\/]/.test(id)) {
            return 'vendor-react';
          }
          if (/[\\/]node_modules[\\/]marked[\\/]/.test(id)) {
            return 'vendor-marked';
          }
          return 'vendor';
        },
      },
    },
  },
});
