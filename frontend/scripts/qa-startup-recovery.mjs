// Fault injection at the browser boundary; no Google or Gemini calls.
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const output = path.join(root, 'design-work/qa/RELEASE-20261002', `startup-recovery-${Date.now()}`)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const cases = []
try {
  for (const failure of ['unavailable', 'disconnected', 'stalled']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const page = await context.newPage()
    let attempts = 0
    await page.route('**/api/auth/status', async route => {
      attempts++
      if (attempts > 1) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false, oauth_configured: true }) })
      if (failure === 'unavailable') return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Máy chủ thử đang tạm thời không sẵn sàng.' }) })
      if (failure === 'disconnected') return route.abort('failed')
      // Browser request remains stalled until its actual 120-second deadline.
      // Route is not fulfilled; closing the context releases it safely.
    })
    const started = Date.now()
    await page.goto('http://127.0.0.1:8000/#/audit', { waitUntil: 'domcontentloaded' })
    const retry = page.getByRole('button', { name: 'Thử lại', exact: true })
    await retry.waitFor({ timeout: failure === 'stalled' ? 130000 : 15000 })
    const errorVisibleMs = Date.now() - started
    await page.screenshot({ path: path.join(output, `${failure}.png`) })
    await retry.click()
    await page.locator('.setup-gate, .setup-page').first().waitFor({ timeout: 15000 })
    cases.push({ failure, errorVisibleMs, attempts, recovered: true })
    await context.close()
  }
} catch (error) {
  cases.push({ recovered: false, error: error.message })
} finally { await browser.close() }
await writeFile(path.join(output, 'report.json'), JSON.stringify({ scope: 'Anonymous startup recovery only', cases }, null, 2))
console.log(JSON.stringify({ output, cases }, null, 2))
if (cases.length !== 3 || cases.some(row => !row.recovered || row.attempts !== 2)) process.exitCode = 1
