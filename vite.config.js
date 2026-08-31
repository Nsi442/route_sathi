import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The frontend always talks to the API through same-origin `/api/...` paths.
// In production Vercel routes those to the FastAPI serverless function; in
// development this proxy forwards them to the local Uvicorn server, so no
// component ever needs to know an API hostname.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
