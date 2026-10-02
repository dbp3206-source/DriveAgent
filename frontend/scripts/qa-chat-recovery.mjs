// Real browser fault checks. Chat writes are intercepted and never reach the server/model.
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const cookie = execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), [
  '-c', 'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _connected_owner_id;from evaluate_gate2_live import _session_cookie;print(_session_cookie(_connected_owner_id()),end="")',
], { cwd: path.join(root, 'backend'), encoding: 'utf8' }).trim()
const base = 'http://127.0.0.1:8000'
const out = path.join(root, 'design-work/qa/screenshots', `chat-recovery-${Date.now()}`)
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const rows = []
try {
  for (const fault of ['server_error', 'network_error', 'double_submit', 'cancel', 'cancel_during_creation']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
    await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
    const page = await context.newPage()
    let submissions = 0
    let cancellationRequests = 0
    await page.route('**/api/chat/tasks', async route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ json: { items: [] } })
      }
      submissions++
      if (fault.startsWith('cancel')) {
        if (fault === 'cancel_during_creation') await new Promise(resolve => setTimeout(resolve, 1500))
        return route.fulfill({ json: { id: 'qa-task', session_id: 'qa-session' } })
      }
      await new Promise(resolve => setTimeout(resolve, 500))
      if (fault === 'network_error') return route.abort('failed')
      return route.fulfill({ status: 503, json: { detail: 'Dịch vụ kiểm thử tạm thời không phản hồi.' } })
    })
    await page.route('**/api/chat/tasks/**', route => {
      if (route.request().method() === 'POST') cancellationRequests++
      return route.fulfill({ json: {
        id: 'qa-task', session_id: 'qa-session',
        status: route.request().method() === 'POST' ? 'cancelled' : 'running',
      } })
    })
    await page.route('**/api/chat/progress/**', route => route.fulfill({ json: { events: [] } }))
    await page.route('**/api/chat/sessions/qa-session/messages-page*', route => route.fulfill({ json: { items: [], next_cursor: null } }))
    await page.route('**/api/chat/sessions-page*', route => route.fulfill({ json: { items: [], next_cursor: null } }))
    await page.goto(`${base}/#/chat`, { waitUntil: 'domcontentloaded' })
    const composer = page.locator('.composer-textarea textarea, textarea.composer-textarea')
    await composer.waitFor({ timeout: 20000 })
    const prompt = `QA giả lập ${fault}: giữ nguyên câu hỏi sau lỗi.`
    await composer.fill(prompt)
    await page.screenshot({ path: path.join(out, `before-${fault}.png`), fullPage: true })
    if (fault === 'double_submit') {
      await page.locator('.composer-container').evaluate(form => {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      })
    } else {
      await page.getByRole('button', { name: 'Gửi', exact: true }).click()
    }
    if (fault.startsWith('cancel')) {
      await page.locator('.composer-container').getByRole('button', { name: 'Dừng yêu cầu', exact: true }).click()
    }
    await page.waitForFunction(text => {
      const element = document.querySelector('.composer-textarea textarea, textarea.composer-textarea')
      return element?.value === text && !document.querySelector('button[type="submit"]')?.disabled
    }, prompt, { timeout: 10000 })
    const preserved = await composer.inputValue() === prompt
    const retryVisible = fault.startsWith('cancel')
      ? await page.getByText('Đã dừng. Nội dung đã được giữ lại trong ô nhập.', { exact: true }).isVisible()
      : await page.getByRole('button', { name: 'Thử lại câu hỏi vừa rồi', exact: true }).isVisible()
    await page.screenshot({ path: path.join(out, `${fault}.png`), fullPage: true })
    rows.push({ fault, submissions, cancellationRequests, preserved, retryVisible,
      passed: submissions === 1 && preserved && retryVisible
        && (!fault.startsWith('cancel') || cancellationRequests === 1) })
    await context.close()
  }
} finally {
  await browser.close()
}
const report = { scope: 'browser_fault_injection_no_real_chat_submission', rows,
  passed: rows.every(row => row.passed) }
await writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify({ ...report, evidence: out }))
if (!report.passed) process.exitCode = 1
