import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'

// 从 package.json 读版本号，注入到前端代码中
const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'))

export default defineConfig({
  plugins: [vue()],
  define: {
    // 让前端代码可以用 import.meta.env.VITE_APP_VERSION 或全局变量 VITE_APP_VERSION
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(pkg.version),
    VITE_APP_VERSION: JSON.stringify(pkg.version),
    VITE_API_BASE: JSON.stringify('http://localhost:8767'),
  },
  server: {
    host: '0.0.0.0',   // ← 允许同局域网手机访问
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8767', changeOrigin: true },
      '/health': { target: 'http://localhost:8767', changeOrigin: true },
      '/docs': { target: 'http://localhost:8767', changeOrigin: true },
      '/redoc': { target: 'http://localhost:8767', changeOrigin: true },
      '/openapi.json': { target: 'http://localhost:8767', changeOrigin: true },
      '/updates': { target: 'http://localhost:8767', changeOrigin: true },
    }
  }
})
