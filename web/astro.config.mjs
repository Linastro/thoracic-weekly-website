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
    },
  },
});
