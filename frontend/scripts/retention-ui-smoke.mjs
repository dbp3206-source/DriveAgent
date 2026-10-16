import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const base = process.env.RETENTION_UI_BASE_URL ?? 'http://127.0.0.1:5173'
const executablePath = process.env.RETENTION_UI_CHROMIUM
const output = path.resolve('..', 'design-work', 'retention-ui-20261016', 'qa', 'screenshots')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) })

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
  const page = await context.newPage()
  const errors = []
  const confirms = []
  const networkTargets = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => {
    const origin = new URL(request.url()).origin
    if (origin !== base) networkTargets.push(origin)
  })
  await page.route('**/api/auth/status', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ authenticated: false, oauth_configured: false,
      gemini_configured: false, demo_login_enabled: false, user: null }),
  }))
  await page.route('**/api/health', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }),
  }))
  await page.route('**/api/retention/status', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ job: null }),
  }))
  await page.route('**/api/retention/preview', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      approval_id: 'synthetic-approval', token: 'synthetic-preview-token',
      selected_count: 3, due_count: 4, active_due_count: 1, has_more: true,
      counts: { chat: 2, source: 1 }, expires_at: '2026-10-16T11:00:00Z',
      cutoff: '2026-09-16T00:00:00Z', retention_days: 30, reset_context_count: 1,
    }),
  }))
  await page.route('**/api/retention/confirm', async route => {
    confirms.push(route.request().postDataJSON())
    await route.fulfill({ status: 202, contentType: 'application/json', body: '{}' })
  })

  await page.goto(`${base}/?theme=dark`, { waitUntil: 'domcontentloaded' })
  await page.locator('#root').waitFor({ state: 'attached' })
  await page.evaluate(() => document.querySelector('#root')?.remove())
  await page.evaluate(() => {
    const host = document.createElement('div')
    host.id = 'retention-ui-harness'
    document.body.append(host)
  })
  await page.addScriptTag({ type: 'module', url: `${base}/src/retention-notice-harness.tsx` })
  const dialog = page.getByRole('dialog')
  await dialog.waitFor({ state: 'visible', timeout: 15000 })
  await page.waitForTimeout(500)
  assert.match(await dialog.innerText(), /Dữ liệu Veridra đã quá 30 ngày/)
  assert.match(await dialog.innerText(), /chỉ dọn dữ liệu Veridra/i)
  assert.match(await dialog.innerText(), /đặt lại 1 mục ngữ cảnh/)
  const checkbox = dialog.getByRole('checkbox')
  const confirm = dialog.getByRole('button', { name: 'Xác nhận dọn dữ liệu' })
  assert.equal(await checkbox.isChecked(), false)
  assert.equal(await confirm.isDisabled(), true)
  assert.equal(await dialog.getAttribute('aria-modal'), 'true')
  await page.keyboard.press('Tab')
  assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true)
  assert.equal(confirms.length, 0)
  await page.screenshot({ path: path.join(output, 'retention-dark-desktop.png'), fullPage: false })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(200)
  const layout = await dialog.evaluate(el => [...el.querySelectorAll('p, .fui-MessageBar, .fui-MessageBarBody, .fui-Checkbox, .fui-DialogActions')].map(item => {
    const style = getComputedStyle(item)
    const box = item.getBoundingClientRect()
    return { tag: item.tagName, className: String(item.className), text: item.textContent?.trim().slice(0, 55),
      width: Math.round(box.width), clientWidth: item.clientWidth, scrollWidth: item.scrollWidth,
      whiteSpace: style.whiteSpace, overflow: style.overflow, minWidth: style.minWidth, opacity: style.opacity }
  }))
  await page.screenshot({ path: path.join(output, 'retention-dark-mobile.png'), fullPage: false })
  const dimensions = await dialog.evaluate(el => ({
    width: el.getBoundingClientRect().width,
    viewport: window.innerWidth,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
  }))
  assert.ok(dimensions.width <= dimensions.viewport)
  assert.equal(dimensions.overflow, false)
  assert.deepEqual(layout.filter(item => item.scrollWidth > item.clientWidth + 1), [])
  await page.setViewportSize({ width: 320, height: 780 })
  await page.waitForTimeout(100)
  const narrow = await dialog.evaluate(el => ({
    width: Math.round(el.getBoundingClientRect().width), viewport: window.innerWidth,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    contentOverflow: el.scrollWidth > el.clientWidth + 1,
  }))
  assert.ok(narrow.width <= narrow.viewport)
  assert.equal(narrow.overflow, false)
  assert.equal(narrow.contentOverflow, false)

  await context.close()
  const lightContext = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' })
  const lightPage = await lightContext.newPage()
  lightPage.on('pageerror', error => errors.push(error.message))
  await lightPage.route('**/api/auth/status', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ authenticated: false, oauth_configured: false,
      gemini_configured: false, demo_login_enabled: false, user: null }),
  }))
  await lightPage.route('**/api/health', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }),
  }))
  await lightPage.route('**/api/retention/status', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ job: null }),
  }))
  await lightPage.route('**/api/retention/preview', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({
      approval_id: 'synthetic-approval', token: 'synthetic-preview-token',
      selected_count: 3, due_count: 4, active_due_count: 1, has_more: true,
      counts: { chat: 2, source: 1 }, expires_at: '2026-10-16T11:00:00Z',
      cutoff: '2026-09-16T00:00:00Z', retention_days: 30, reset_context_count: 1,
    }),
  }))
  lightPage.on('request', request => {
    const origin = new URL(request.url()).origin
    if (origin !== base) networkTargets.push(origin)
  })
  await lightPage.goto(`${base}/?theme=light`, { waitUntil: 'domcontentloaded' })
  await lightPage.locator('#root').waitFor({ state: 'attached' })
  await lightPage.evaluate(() => document.querySelector('#root')?.remove())
  await lightPage.evaluate(() => {
    const host = document.createElement('div')
    host.id = 'retention-ui-harness'
    document.body.append(host)
  })
  await lightPage.addScriptTag({ type: 'module', url: `${base}/src/retention-notice-harness.tsx` })
  await lightPage.getByRole('dialog').waitFor({ state: 'visible', timeout: 15000 })
  await lightPage.waitForTimeout(500)
  await lightPage.screenshot({ path: path.join(output, 'retention-light-desktop.png'), fullPage: false })
  assert.deepEqual(errors, [])
  assert.deepEqual(networkTargets, [])
  await lightContext.close()
  console.log(JSON.stringify({
    result: 'passed', confirmRequests: confirms.length, responsive: { ...dimensions, narrow }, layout,
    screenshots: output, browserErrors: errors,
  }, null, 2))
} finally {
  await browser.close()
}
