// Read-only UI check: inject a synthetic sanitized trace into an existing
// conversation response in the browser. No account content is written to disk.
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backendDir = path.join(rootDir, 'backend')
const cookie = execFileSync(path.join(backendDir, '.venv', 'Scripts', 'python.exe'), [
  '-c',
  'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _connected_owner_id;from evaluate_gate2_live import _session_cookie;print(_session_cookie(_connected_owner_id()),end="")',
], { cwd: backendDir, encoding: 'utf8' }).trim()

if (!cookie) throw new Error('Connected local QA owner is unavailable')
const base = 'http://127.0.0.1:8000'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  for (const [name, viewport] of [
    ['desktop', { width: 1440, height: 900 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    const context = await browser.newContext({ viewport })
    await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
    const sessionResponse = await context.request.get(`${base}/api/chat/sessions-page`)
    const sessions = await sessionResponse.json()
    const sessionId = sessions.items?.[0]?.id
    if (!sessionId) throw new Error('No existing QA session is available')
    await context.addInitScript(id => {
      sessionStorage.setItem('drive_agent_session_id', id)
    }, sessionId)
    const page = await context.newPage()
    let injected = false
    await page.route('**/api/chat/sessions/*/messages-page*', async route => {
      const response = await route.fetch()
      const body = await response.json()
      const target = body.items?.find(item => item.role === 'assistant')
      if (target) {
        target.trace = [{
          stage: 'output_contract',
          status: 'degraded',
          violations: ['above_explicit_word_maximum', 'missing_action_section'],
        }]
        injected = true
      }
      await route.fulfill({ response, json: body })
    })
    await page.goto(`${base}/#/chat`)
    await page.locator('.trace-panel').first().waitFor({ timeout: 15000 })
    await page.locator('.trace-panel summary').first().click()
    await page.getByText('Kiểm tra yêu cầu đầu ra').first().waitFor()
    await page.getByText('Dài hơn độ dài đã yêu cầu.').first().waitFor()
    await page.getByText('Thiếu hành động cùng ngưỡng kích hoạt định lượng.').first().waitFor()
    if (!injected) throw new Error('Synthetic trace was not delivered to the browser')
    console.log(JSON.stringify({ status: 'passed', viewport: name, traceReasonsRendered: 2 }))
    await context.close()
  }
} finally {
  await browser.close()
}
