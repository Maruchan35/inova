import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api se redirige al backend: el frontend nunca escribe la URL del servidor.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
