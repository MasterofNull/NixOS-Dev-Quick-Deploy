import path from "path"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 8890,
    proxy: {
      '/api': {
        target: 'http://localhost:8889',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8889',
        ws: true,
      }
    }
  }
})