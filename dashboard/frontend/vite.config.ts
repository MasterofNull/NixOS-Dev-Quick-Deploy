import path from "path"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  const frontendPort = env.DASHBOARD_FRONTEND_PORT || '8890'
  const apiProxyHost = env.DASHBOARD_API_PROXY_HOST || '127.0.0.1'
  const apiPort = env.DASHBOARD_API_PORT || '8889'
  const apiTarget = env.DASHBOARD_API_URL || `http://${apiProxyHost}:${apiPort}`
  const wsTarget = env.DASHBOARD_WS_URL || `ws://${apiProxyHost}:${apiPort}`

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: Number(frontendPort),
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: wsTarget,
          ws: true,
        }
      }
    }
  }
})
