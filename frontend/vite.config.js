import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // Con FUENTE = 'api' (src/lectura/api.js), /api va al backend y no hace falta CORS.
    // 8000 es el puerto por defecto de uvicorn.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: (ruta) => ruta.replace(/^\/api/, ''),
      },
    },
  },
})
