import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8767', changeOrigin: true },
      '/health': { target: 'http://localhost:8767', changeOrigin: true },
      '/docs': { target: 'http://localhost:8767', changeOrigin: true },
      '/redoc': { target: 'http://localhost:8767', changeOrigin: true },
      '/openapi.json': { target: 'http://localhost:8767', changeOrigin: true },
    }
  }
})
