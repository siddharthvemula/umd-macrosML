// Vite settings for the React frontend: the dev server, the /api proxy to FastAPI,
// and the Vitest test setup (Vitest reads this same file).

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // The browser only talks to Vite (localhost:5173). Vite forwards /api/* to FastAPI and
    // strips the /api prefix, so the browser sees one origin and FastAPI needs no CORS setup.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    // jsdom is a fake browser (document, window) so tests can render components.
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
  },
})
