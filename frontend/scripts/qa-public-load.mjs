// Public, read-only load probe. No session, credentials or model calls.
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const origin = 'https://veridra-closed-beta.onrender.com'
const output = path.join(root, 'design-work/qa/RELEASE-20261002', `public-load-${Date.now()}`)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const measurements = []
try {
  for (let index = 0; index < 21; index++) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const started = Date.now()
    const route = ['/', '/#/home', '/#/chat', '/#/audit', '/?connected=1#/settings'][index % 5]
    try {
      const response = await page.goto(origin + route, { waitUntil: 'domcontentloaded', timeout: 120000 })
      await page.locator('a,button').filter({ hasText: /Kết nối Google|Đăng nhập.*Google/ }).first().waitFor({ timeout: index === 0 ? 120000 : 30000 })
      const elapsedMs = Date.now() - started
      const timing = await page.evaluate(() => {
        const navigation = performance.getEntriesByType('navigation')[0]
        return {
          documentFirstByteMs: navigation?.responseStart ?? null,
          documentReceivedMs: navigation?.responseEnd ?? null,
          domReadyMs: navigation?.domContentLoadedEventEnd ?? null,
          resources: performance.getEntriesByType('resource').map(entry => ({
            path: new URL(entry.name).pathname,
            type: entry.initiatorType,
            startMs: Math.round(entry.startTime),
            durationMs: Math.round(entry.duration),
          })).sort((a, b) => b.durationMs - a.durationMs).slice(0, 12),
        }
      })
      measurements.push({ index, route, httpStatus: response?.status(), elapsedMs, loginVisible: true, timing, errors })
      if (index === 0) await page.screenshot({ path: path.join(output, 'public-login.png') })
    } catch (error) {
      await page.screenshot({ path: path.join(output, `failed-${index}.png`) }).catch(() => {})
      measurements.push({ index, route, elapsedMs: Date.now() - started, loginVisible: false, error: error.message, errors })
      // Avoid twenty repeated long waits when the public service is unavailable.
      break
    } finally { await context.close() }
  }
} finally { await browser.close() }
const warm = measurements.slice(1).filter(row => row.loginVisible).map(row => row.elapsedMs).sort((a, b) => a - b)
const report = {
  time: new Date().toISOString(), origin, scope: 'Public login only; authenticated product and cold-start not proven',
  first: measurements[0], warmSamples: warm.length,
  warmP50: warm.length ? warm[Math.ceil(warm.length * .5) - 1] : null,
  warmP95: warm.length ? warm[Math.ceil(warm.length * .95) - 1] : null,
  measurements,
}
await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify({ output, ...report }, null, 2))
if (measurements.length !== 21 || measurements.some(row => !row.loginVisible || row.httpStatus !== 200 || row.errors.length)) process.exitCode = 1
