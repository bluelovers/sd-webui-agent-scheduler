import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// @ts-ignore
import { cssBuildOutput } from './vite.css-format';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), cssBuildOutput()],
  build: {
    outDir: '../',
    rollupOptions: {
      input: {
        main: 'index.html',
      },
    },
    lib: {
      name: 'agent-scheduler',
      entry: 'src/extension/index.ts',
      fileName: 'javascript/extension',
      formats: ['es']
    },
  },
});
