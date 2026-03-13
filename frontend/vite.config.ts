import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
  },
  // Electron の本番ビルドでファイルを相対パスで読み込むため
  base: './',
})
