import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const apiTarget = env.DRIVE_AGENT_DEV_API_TARGET || 'http://localhost:8000'
  const targetUrl = new URL(apiTarget)
  const loopbackHosts = ['localhost', '127.0.0.1', '[::1]']
  if (targetUrl.protocol !== 'http:' || loopbackHosts.indexOf(targetUrl.hostname) < 0) {
    throw new Error('DRIVE_AGENT_DEV_API_TARGET must be an HTTP loopback URL.')
  }

  return {
    plugins: [react()],
    build: {
      // Mermaid is an intentionally lazy, optional diagram engine. Its largest
      // parser chunk is ~662 kB but only loads when a response contains a diagram.
      // Keep the release log actionable while retaining the 143 kB gzip boundary.
      chunkSizeWarningLimit: 700,
    },
    define: {
      __DRIVEAGENT_FRONTEND_BUILT_AT__: JSON.stringify(new Date().toISOString()),
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
