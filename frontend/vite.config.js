import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 배포 경로를 빌드 시점에 받는다. Cloudflare Pages에서 하위 경로로 서비스할 때
// BASE_PATH=/opsboard/ 로 빌드하면 되고, 기본값은 루트다.
// 컴포넌트는 import.meta.env.BASE_URL로 데이터를 읽으므로 여기만 맞추면 된다.
const base = process.env.BASE_PATH ?? '/'

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
})
