import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://n8n.1215group.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/webhook'),
      },
      '/webhook': {
        target: 'https://n8n.1215group.com',
        changeOrigin: true,
      },
      '/videos': {
        target: 'https://karaoke.1215group.com',
        changeOrigin: true,
      },
    },
  },
})
