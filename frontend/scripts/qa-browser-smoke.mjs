// Read-only UI smoke against the local app. The signed QA cookie stays in memory.
// Screenshots may include private account data: keep them local and do not publish.
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(scriptDir, '..')
const rootDir = path.resolve(frontendDir, '..')
const backendDir = path.join(rootDir, 'backend')
const python = path.join(backendDir, '.venv', 'Scripts', 'python.exe')
const cookie = execFileSync(python, [
  '-c',
  'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _connected_owner_id;from evaluate_gate2_live import _session_cookie;print(_session_cookie(_connected_owner_id()),end="")',
], { cwd: backendDir, encoding: 'utf8' }).trim()

if (!cookie) throw new Error('Connected local QA owner is unavailable')
const base = 'http://127.0.0.1:8000'
const routes = [
  'home', 'chat', 'drive', 'gmail', 'local', 'artifacts', 'memory',
  'harness', 'audit', 'access', 'settings', 'skills',
]
const labels = {
  home: 'Bắt đầu', chat: 'Trò chuyện', drive: 'Google Drive', gmail: 'Gmail',
  local: 'Tài liệu local', artifacts: 'Kết quả đã lưu', memory: 'Bộ nhớ',
  harness: 'Cách Agent hoạt động', audit: 'Nhật ký', access: 'Phân quyền',
  settings: 'Cài đặt', skills: 'Skills của tôi',
}
const runId = new Date().toISOString().replace(/[:.]/g, '-')
const outDir = path.join(rootDir, 'design-work', 'qa', 'screenshots', `browser-smoke-${runId}`)
await mkdir(outDir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []
const interactions = []
const viewportCases = process.env.QA_EXTENDED === '1'
  ? [320, 375, 414, 768, 1440].flatMap(width => ['light', 'dark'].map(theme => [
    `${width}-${theme}`, { width, height: width < 768 ? 844 : 900 }, theme,
  ]))
  : [['desktop', { width: 1440, height: 900 }, 'dark'],
    ['mobile', { width: 390, height: 844 }, 'dark']]

try {
  for (const [viewportName, viewport, theme] of viewportCases) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
    await context.addInitScript(value => {
      if (window.top !== window) return
      try { localStorage.setItem('drive-agent-theme', value) } catch { /* about:blank has no storage. */ }
    }, theme)
    await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
    const page = await context.newPage()
    const events = []
    const externalWarnings = []
    page.on('pageerror', error => events.push({ type: 'pageerror', text: error.message }))
    page.on('console', message => {
      if (message.type() === 'error') {
        const target = message.location().url
        const item = { type: 'console', text: message.text().slice(0, 250), url: target }
        if (target && !target.startsWith(base)) externalWarnings.push(item)
        else if (message.text().includes('ERR_NETWORK_ACCESS_DENIED')) externalWarnings.push(item)
        else events.push(item)
      }
    })
    page.on('requestfailed', request => {
      if (!request.failure()?.errorText?.includes('ERR_ABORTED')) {
        const item = { type: 'requestfailed', url: request.url() }
        if (new URL(request.url()).origin === base) events.push(item)
        else externalWarnings.push(item)
      }
    })
    page.on('response', response => {
      if (response.status() >= 500) {
        events.push({ type: 'http5xx', status: response.status(), url: new URL(response.url()).pathname })
      }
    })
    for (const route of routes) {
      const routeStarted = Date.now()
      const eventStart = events.length
      const externalStart = externalWarnings.length
      const response = await page.goto(`${base}/#/${route}`, { waitUntil: 'domcontentloaded' })
      await page.locator('main').waitFor({ timeout: 15000 })
      await page.waitForFunction(
        label => document.querySelector('.topbar h1')?.textContent?.trim() === label,
        labels[route],
        { timeout: 15000 },
      )
      await page.waitForFunction(
        () => {
          const text = document.querySelector('main')?.textContent ?? ''
          return !text.includes('Đang mở khu vực') && !text.includes('Đang tải Gmail')
        },
        undefined,
        { timeout: 15000 },
      ).catch(() => {})
      if (route === 'gmail') {
        await page.locator('.mail-row').first().waitFor({ timeout: 45000 }).catch(() => {})
      }
      await page.waitForTimeout(450)
      const hashBeforeKeyboard = new URL(page.url()).hash
      let skipFocused = false
      for (let tab = 0; tab < 80 && !skipFocused; tab++) {
        await page.keyboard.press('Shift+Tab')
        skipFocused = await page.locator('.skip-link').evaluate(el => el === document.activeElement)
      }
      if (skipFocused) {
        await page.keyboard.press('Enter')
        await page.waitForFunction(() => document.activeElement?.id === 'main-content', undefined, { timeout: 2000 })
      }
      const keyboard = await page.evaluate(() => ({
        mainFocused: document.activeElement?.id === 'main-content',
        mainNotCovered: (document.querySelector('main')?.getBoundingClientRect().top ?? -1) >=
          (document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0) - 1,
        motionDisabled: getComputedStyle(document.querySelector('.workspace-canvas'), '::after').animationName === 'none',
      }))
      const keyboardPassed = skipFocused && keyboard.mainFocused && keyboard.mainNotCovered &&
        new URL(page.url()).hash === hashBeforeKeyboard && keyboard.motionDisabled
      const state = await page.evaluate(() => ({
        width: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        mainWidth: document.querySelector('main')?.getBoundingClientRect().width ?? 0,
        heading: [...document.querySelectorAll('main h1, main h2')]
          .find(element => {
            const box = element.getBoundingClientRect()
            return box.width > 0 && box.height > 0 && getComputedStyle(element).visibility !== 'hidden'
          })?.textContent?.trim().slice(0, 100) ?? '',
        visibleFocusables: [...document.querySelectorAll('button,a,input,select,textarea')]
          .filter(element => {
            const box = element.getBoundingClientRect()
            return box.width > 0 && box.height > 0 && getComputedStyle(element).visibility !== 'hidden'
          }).length,
        loadingVisible: /Đang mở khu vực|Đang tải Gmail/.test(
          document.querySelector('main')?.textContent ?? '',
        ),
      }))
      const screenshot = path.join(outDir, `${viewportName}-${route}.png`)
      await page.screenshot({ path: screenshot, fullPage: false })
      results.push({
        viewport: viewportName,
        route,
        loadMs: Date.now() - routeStarted,
        httpStatus: response?.status() ?? (page.url().startsWith(base) ? 200 : null),
        ...state,
        keyboardPassed,
        horizontalOverflow: state.documentWidth > state.width + 1,
        events: events.slice(eventStart),
        externalWarnings: externalWarnings.slice(externalStart),
        screenshot,
      })
      if (route === 'gmail') {
        const firstMail = page.locator('.mail-row').first()
        const listed = await firstMail.count() > 0
        if (listed) {
          await firstMail.click()
          await page.locator('.mail-message-card').first().waitFor({ timeout: 15000 })
          const htmlTab = page.getByRole('tab', { name: 'HTML' }).first()
          const textTab = page.getByRole('tab', { name: 'Văn bản' }).first()
          const htmlAvailable = await htmlTab.count() > 0
          const textAvailable = await textTab.count() > 0
          const htmlRendered = htmlAvailable
            ? await page.locator('iframe[title="Nội dung HTML của email"]').first().count() > 0
            : false
          if (textAvailable) await textTab.click()
          const textRendered = await page.locator('.mail-readable-text, .mail-calendar-text').first().count() > 0
          if (htmlAvailable) await htmlTab.click()
          interactions.push({
            viewport: viewportName,
            action: 'open_first_gmail_and_toggle_view',
            listed, htmlAvailable, textAvailable, htmlRendered, textRendered,
          })
        } else {
          interactions.push({ viewport: viewportName, action: 'open_first_gmail_and_toggle_view', listed })
        }
      }
    }
    let submittedChats = 0
    page.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname.startsWith('/api/chat')) submittedChats++
    })
    for (const label of ['Chuẩn bị đầu ngày', 'Chuẩn bị trước cuộc hẹn', 'Tiếp nối cuộc trao đổi']) {
      await page.goto(`${base}/#/home`, { waitUntil: 'domcontentloaded' })
      await page.locator('.home-quick-starts').getByRole('button', { name: new RegExp(label) }).click()
      const composer = page.locator('.composer-textarea textarea, textarea.composer-textarea')
      await composer.waitFor({ timeout: 15000 })
      const draft = await composer.inputValue()
      interactions.push({
        viewport: viewportName,
        action: 'consultation_quick_start',
        label,
        draftReady: draft.length > 60,
        chatRoute: new URL(page.url()).hash === '#/chat',
        noAutomaticSubmit: submittedChats === 0,
      })
    }
    let skillWrites = 0
    page.on('request', request => {
      if (['POST', 'PATCH', 'DELETE'].includes(request.method()) && new URL(request.url()).pathname.startsWith('/api/skills')) skillWrites++
    })
    await page.goto(`${base}/#/skills`, { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: '+ Thêm skill', exact: true }).click()
    await page.locator('.skills-preset-bar').getByRole('button', { name: 'Chuẩn bị cuộc hẹn tư vấn', exact: true }).click()
    interactions.push({
      viewport: viewportName,
      action: 'consultation_skill_preview',
      correctName: await page.locator('#skill-name').inputValue() === 'consultation_meeting_brief',
      correctTitle: await page.locator('#skill-title').inputValue() === 'Chuẩn bị cuộc hẹn tư vấn',
      hasCustomerInput: (await page.locator('#skill-goal').inputValue()).includes('{customer}'),
      noAutomaticWrite: skillWrites === 0,
    })
    await context.close()
  }
  // Deterministic loading-state check; the intercepted request never reaches Google.
  const slowContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  await slowContext.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
  const slowPage = await slowContext.newPage()
  await slowPage.route('**/api/gmail/messages?*', async route => {
    await new Promise(resolve => setTimeout(resolve, 8500))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ messages: [], total_found: 0, next_page_token: null }),
    })
  })
  await slowPage.goto(`${base}/#/gmail`, { waitUntil: 'domcontentloaded' })
  const slowNotice = slowPage.locator('.mail-triage-note[role="status"]')
  const slowNoticeVisible = await slowNotice.waitFor({ timeout: 12000 }).then(() => true, () => false)
  await slowPage.getByText('Không có email phù hợp').waitFor({ timeout: 15000 })
  interactions.push({
    viewport: 'mobile',
    action: 'slow_gmail_loading_notice',
    slowNoticeVisible,
    resolvedAfterDelay: await slowNotice.count() === 0,
  })
  await slowContext.close()
} finally {
  await browser.close()
}

const summary = {
  pages: results.length,
  keyboardFailures: results.filter(row => !row.keyboardPassed).map(row => `${row.viewport}:${row.route}`),
  horizontalOverflow: results.filter(row => row.horizontalOverflow).map(row => `${row.viewport}:${row.route}`),
  failingRoutes: results.filter(row => row.httpStatus !== 200 || row.events.length)
    .map(row => ({ viewport: row.viewport, route: row.route, httpStatus: row.httpStatus, events: row.events })),
  missingHeading: results.filter(row => !row.heading).map(row => `${row.viewport}:${row.route}`),
  loadingRoutes: results.filter(row => row.loadingVisible).map(row => `${row.viewport}:${row.route}`),
  interactions,
  snapshots: results,
}
const reportPath = path.join(outDir, 'report.json')
await writeFile(reportPath, JSON.stringify(summary, null, 2))
console.log(JSON.stringify({
  pages: summary.pages,
  keyboardFailures: summary.keyboardFailures,
  horizontalOverflow: summary.horizontalOverflow,
  failingRoutes: summary.failingRoutes,
  missingHeading: summary.missingHeading,
  loadingRoutes: summary.loadingRoutes,
  interactions: summary.interactions,
  reportPath,
}, null, 2))
if (summary.keyboardFailures.length || summary.horizontalOverflow.length || summary.failingRoutes.length ||
  summary.missingHeading.length || summary.loadingRoutes.length ||
  summary.interactions.some(row => row.action === 'slow_gmail_loading_notice'
    ? !row.slowNoticeVisible || !row.resolvedAfterDelay
    : row.action === 'consultation_quick_start'
      ? !row.draftReady || !row.chatRoute || !row.noAutomaticSubmit
      : row.action === 'consultation_skill_preview'
        ? !row.correctName || !row.correctTitle || !row.hasCustomerInput || !row.noAutomaticWrite
        : !row.listed || !row.textRendered || (row.htmlAvailable && !row.htmlRendered))) process.exitCode = 1
