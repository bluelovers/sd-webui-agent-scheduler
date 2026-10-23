import { defineConfig } from 'vite';

import { cssBuildOutput } from './vite.css-format';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [cssBuildOutput()],
  build: {
    outDir: '../',
    copyPublicDir: false,
    lib: {
      name: 'agentScheduler',
      entry: 'src/extension/index.ts',
      fileName: 'javascript/agent-scheduler',
      formats: ['iife']
    },
  },
});
