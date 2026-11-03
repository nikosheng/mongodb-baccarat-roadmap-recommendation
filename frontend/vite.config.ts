import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Backend target is configurable so this works both for local dev
// (localhost:8000) and inside docker-compose (service name "backend").
const backendTarget = process.env.VITE_BACKEND_URL || 'http://localhost:8000'
const backendWsTarget = backendTarget.replace(/^http/, 'ws')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': backendTarget,
      '/ws': {
        target: backendWsTarget,
        ws: true,
      },
    },
  },
})
