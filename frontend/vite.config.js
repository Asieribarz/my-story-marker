import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // /api va al backend y no hace falta CORS. 8000 es el puerto por defecto de uvicorn;
    // MSM_BACKEND lo cambia (por ejemplo, un segundo backend mientras otro genera).
    proxy: {
      '/api': {
        target: process.env.MSM_BACKEND ?? 'http://127.0.0.1:8000',
        rewrite: (ruta) => ruta.replace(/^\/api/, ''),
      },
    },
  },
})
