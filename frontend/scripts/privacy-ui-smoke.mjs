// Browser check for privacy disclosure UI using synthetic account/API fixtures only.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '../..')
const base = process.env.PRIVACY_UI_BASE_URL ?? 'http://127.0.0.1:4173'
const output = path.join(rootDir, 'design-work/privacy-disclosure-20261016/qa/screenshots')
await mkdir(output, { recursive: true })

const fixtures = {
  '/api/auth/status': {
    authenticated: true, oauth_configured: true, gemini_configured: true,
    demo_login_enabled: false,
    user: { id: 'synthetic-owner', email: 'qa@example.test', display_name: 'QA',
      avatar_url: null, role: 'owner', scopes: [] },
  },
  '/api/health': { status: 'ok', database: true, gemini_configured: true,
    google_oauth_configured: true, vector_store: 'synthetic', gemini_connectivity: 'not_probed',
    google_workspace_connectivity: 'not_probed', gemini_chat_model: 'synthetic',
    gemini_fallback_model: 'synthetic', gemini_embedding_model: 'synthetic', embedding_dimensions: 1 },
  '/api/chat/tasks': { items: [] },
  '/api/chat/sessions-page': { items: [], next_cursor: null },
  '/api/skills': { data: { items: [] } },
  '/api/settings/providers/gemini/status': { configured: false, credential_source: 'unconfigured',
    active_credential_id: null, active_display_name: null, effective_credential_id: null,
    display_name: null, project_alias: null, fingerprint: null, failover_active: false,
    primary_model: 'synthetic', fallback_model: 'synthetic', local_budget: null,
    circuits: [], provider_balance_available: false, provider_balance_note: 'not probed' },
  '/api/retention/status': { job: null },
  '/api/retention/preview': { approval_id: null, token: null, selected_count: 0,
    due_count: 0, active_due_count: 0, has_more: false, counts: {}, expires_at: null,
    cutoff: '2026-09-16T00:00:00Z', retention_days: 30, reset_context_count: 0 },
  '/api/local-sources': [],
  '/api/local-sources/pdf-jobs': [],
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
const requests = []
try {
  for (const [name, viewport, theme] of [
    ['desktop-dark', { width: 1440, height: 1000 }, 'dark'],
    ['mobile-light', { width: 390, height: 844 }, 'light'],
  ]) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
    await context.addInitScript(value => localStorage.setItem('drive-agent-theme', value), theme)
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(`${name}: ${error.message}`))
    await page.route('**/api/**', route => {
      const url = new URL(route.request().url())
      requests.push(url.pathname)
      const body = fixtures[url.pathname] ?? {}
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    })
    await page.goto(`${base}/#/chat`, { waitUntil: 'domcontentloaded' })
    const notice = page.locator('.chat-data-use-notice')
    await notice.waitFor({ state: 'visible', timeout: 15000 })
    const text = await notice.innerText()
    assert.match(text, /Google Gemini/)
    assert.match(text, /hạn mức miễn phí/)
    assert.match(text, /thông tin cá nhân, nhạy cảm hoặc bí mật/)
    assert.equal(await notice.getByRole('link', { name: 'Xem thông tin dữ liệu' }).getAttribute('href'), '/privacy.html')
    assert.equal(await page.getByRole('link', { name: 'Thông tin quyền riêng tư và dữ liệu' }).getAttribute('href'), '/privacy.html')
    const viewportState = await page.evaluate(() => ({
      width: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      noticeWidth: document.querySelector('.chat-data-use-notice').getBoundingClientRect().width,
      notice: (() => { const rect = document.querySelector('.chat-data-use-notice').getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom } })(),
      mascot: (() => { const rect = document.querySelector('.mascot-companion').getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
          expanded: !document.querySelector('.mascot-companion').classList.contains('mascot-companion--minimized') } })(),
    }))
    assert.ok(viewportState.documentWidth <= viewportState.width + 1, `${name} has horizontal overflow`)
    if (viewportState.mascot.expanded) {
      const overlaps = viewportState.notice.left < viewportState.mascot.right
        && viewportState.notice.right > viewportState.mascot.left
        && viewportState.notice.top < viewportState.mascot.bottom
        && viewportState.notice.bottom > viewportState.mascot.top
      assert.equal(overlaps, false, `${name} has a mascot panel over the disclosure`)
    }
    await page.screenshot({ path: path.join(output, `chat-${name}.png`), fullPage: false })
    await context.close()
  }
  const setupContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  const setupPage = await setupContext.newPage()
  setupPage.on('pageerror', error => errors.push(`setup: ${error.message}`))
  await setupPage.route('**/api/**', route => {
    const url = new URL(route.request().url())
    requests.push(url.pathname)
    const body = url.pathname === '/api/auth/status'
      ? { authenticated: false, oauth_configured: true, gemini_configured: false,
        demo_login_enabled: false, user: null }
      : fixtures[url.pathname] ?? {}
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await setupPage.goto(`${base}/#/home`, { waitUntil: 'domcontentloaded' })
  const setupNotice = setupPage.locator('.setup-intro .data-use-notice')
  await setupNotice.waitFor({ state: 'visible', timeout: 15000 })
  assert.match(await setupNotice.innerText(), /đừng gửi thông tin cá nhân, nhạy cảm hoặc bí mật/i)
  assert.equal(await setupNotice.getByRole('link', { name: 'Xem cách dữ liệu được dùng' }).getAttribute('href'), '/privacy.html')
  await setupPage.screenshot({ path: path.join(output, 'setup-data-notice-desktop.png'), fullPage: false })
  await setupContext.close()
  const sourcesContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  const sourcesPage = await sourcesContext.newPage()
  sourcesPage.on('pageerror', error => errors.push(`local-sources: ${error.message}`))
  await sourcesPage.route('**/api/**', route => {
    const url = new URL(route.request().url())
    requests.push(url.pathname)
    const body = fixtures[url.pathname] ?? {}
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await sourcesPage.goto(`${base}/#/local`, { waitUntil: 'domcontentloaded' })
  const localPrivacy = sourcesPage.locator('.local-library__privacy')
  await localPrivacy.waitFor({ state: 'visible', timeout: 15000 })
  assert.match(await localPrivacy.innerText(), /khóa miễn phí/i)
  assert.match(await localPrivacy.innerText(), /đừng tải lên dữ liệu cá nhân, nhạy cảm hoặc bí mật/i)
  assert.equal(await sourcesPage.getByRole('link', { name: 'Xem đầy đủ cách Veridra dùng và lưu dữ liệu' }).getAttribute('href'), '/privacy.html')
  await sourcesPage.screenshot({ path: path.join(output, 'local-sources-data-notice-desktop.png'), fullPage: false })
  await sourcesContext.close()
  assert.deepEqual(errors, [])
  assert.ok(requests.includes('/api/chat/tasks'))
  assert.ok(requests.includes('/api/chat/sessions-page'))
  console.log(JSON.stringify({ result: 'passed', screenshots: output, apiFixtures: Object.keys(fixtures),
    apiCalls: requests, browserErrors: errors }, null, 2))
} finally {
  await browser.close()
}
