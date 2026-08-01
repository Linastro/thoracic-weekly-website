import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  integrations: [react()],
  server: {
    host: '0.0.0.0',
    port: 4321,
  },
  vite: {
    server: {
      watch: { usePolling: true },
      proxy: {
        // 客户端 fetch('/api/*') → 转发到后端 8080
        '/api': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
      },
    },
  },
});
