// Read-only theme and responsive verification against the real local app.
// Screenshots can contain private account data; keep them in local QA evidence only.
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
const routes = ['settings', 'chat', 'audit', 'harness']
const viewports = [
  ['desktop', { width: 1440, height: 900 }],
  ['intermediate', { width: 1024, height: 768 }],
  ['mobile', { width: 390, height: 844 }],
]
const themes = ['light', 'dark']
const outDir = path.join(rootDir, 'design-work', 'qa', 'screenshots', 'theme-pages-20260929')
await mkdir(outDir, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []
try {
  for (const theme of themes) {
    for (const [viewportName, viewport] of viewports) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
      await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
      await context.addInitScript(selectedTheme => {
        localStorage.setItem('drive-agent-theme', selectedTheme)
      }, theme)
      const page = await context.newPage()
      const events = []
      page.on('pageerror', error => events.push({ type: 'pageerror', text: error.message }))
      page.on('console', message => {
        if (message.type() === 'error' && message.location().url.startsWith(base)) {
          events.push({ type: 'console', text: message.text().slice(0, 240) })
        }
      })
      page.on('requestfailed', request => {
        if (request.url().startsWith(base) && !request.failure()?.errorText?.includes('ERR_ABORTED')) {
          events.push({ type: 'requestfailed', url: request.url() })
        }
      })
      page.on('response', response => {
        if (response.url().startsWith(base) && response.status() >= 500) {
          events.push({ type: 'http5xx', status: response.status(), url: response.url() })
        }
      })

      for (const route of routes) {
        const eventStart = events.length
        await page.goto(`${base}/#/${route}`, { waitUntil: 'domcontentloaded' })
        await page.locator('main').waitFor({ timeout: 15000 })
        if (route === 'harness') {
          await page.locator('.harness-story').waitFor({ timeout: 15000 })
        }
        await page.waitForTimeout(route === 'chat' ? 1400 : 800)
        const state = await page.evaluate(() => {
          const visible = element => {
            const box = element.getBoundingClientRect()
            return box.width > 0 && box.height > 0 && getComputedStyle(element).visibility !== 'hidden'
          }
          const offenders = [...document.querySelectorAll('body *')]
            .filter(visible)
            .map(element => {
              const box = element.getBoundingClientRect()
              return {
                tag: element.tagName,
                className: String(element.className).slice(0, 120),
                text: (element.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 100),
                parent: element.parentElement ? `${element.parentElement.tagName}.${String(element.parentElement.className).slice(0, 80)}#${element.parentElement.id}` : '',
                left: box.left,
                right: box.right,
              }
            })
            .filter(item => item.left < -1 || item.right > window.innerWidth + 1)
            .slice(0, 12)
          const rootStyle = getComputedStyle(document.documentElement)
          const chatUser = document.querySelector('.message--user')
          const chatAssistant = document.querySelector('.message--assistant')
          const composer = document.querySelector('.composer textarea')
          const sidebar = document.querySelector('.sidebar')
          const benchmarkScores = [...document.querySelectorAll('.release-benchmark__table tbody tr')]
            .map(row => row.querySelectorAll('td')[2]?.textContent?.trim() ?? '')
          const benchmarkVerdict = document.querySelector('.release-verdict')?.textContent
            ?.trim().replace(/\s+/g, ' ') ?? ''
          const styleSnapshot = element => element ? {
            color: getComputedStyle(element).color,
            backgroundColor: getComputedStyle(element).backgroundColor,
            backgroundImage: getComputedStyle(element).backgroundImage,
          } : null
          return {
            theme: document.documentElement.dataset.theme,
            width: innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
            offenders,
            variables: {
              canvas: rootStyle.getPropertyValue('--canvas').trim(),
              text: rootStyle.getPropertyValue('--text').trim(),
              surface: rootStyle.getPropertyValue('--surface').trim(),
            },
            sidebar: styleSnapshot(sidebar),
            chatUser: styleSnapshot(chatUser),
            chatAssistant: styleSnapshot(chatAssistant),
            composer: styleSnapshot(composer),
            benchmarkVisible: Boolean(document.querySelector('.release-benchmark')),
            benchmarkScores,
            benchmarkVerdict,
            harnessStoryVisible: Boolean(document.querySelector('.harness-story')),
          }
        })
        const screenshot = path.join(outDir, `${theme}-${viewportName}-${route}.png`)
        await page.screenshot({ path: screenshot, fullPage: false })
        results.push({ requestedTheme: theme, viewport: viewportName, route, ...state, events: events.slice(eventStart), screenshot })
      }
      await context.close()
    }
  }
} finally {
  await browser.close()
}

const summary = {
  checked: results.length,
  overflow: results.filter(row => row.horizontalOverflow).map(row => ({ key: `${row.theme}:${row.viewport}:${row.route}`, offenders: row.offenders })),
  eventFailures: results.filter(row => row.events.length).map(row => ({ key: `${row.theme}:${row.viewport}:${row.route}`, events: row.events })),
  wrongTheme: results.filter(row => row.theme !== row.requestedTheme).map(row => `${row.requestedTheme}:${row.viewport}:${row.route}`),
  missingBenchmark: results.filter(row => row.route === 'audit' && !row.benchmarkVisible).map(row => `${row.theme}:${row.viewport}`),
  incompleteBenchmark: results
    .filter(row => row.route === 'audit' && (
      row.benchmarkScores.length !== 7 || row.benchmarkScores.some(score => {
        if (score === 'N/A') {
          return !/N\/A.*giữ phát hành/i.test(row.benchmarkVerdict)
        }
        return !/^\d+(\.\d+)?$/.test(score) || Number(score) < 0 || Number(score) > 10
      })
    ))
    .map(row => ({ key: `${row.theme}:${row.viewport}`, scores: row.benchmarkScores, verdict: row.benchmarkVerdict })),
  missingHarnessStory: results.filter(row => row.route === 'harness' && !row.harnessStoryVisible).map(row => `${row.theme}:${row.viewport}`),
  results,
}
const reportPath = path.join(outDir, 'report.json')
await writeFile(reportPath, JSON.stringify(summary, null, 2))
console.log(JSON.stringify({
  checked: summary.checked,
  wrongTheme: summary.wrongTheme,
  overflow: summary.overflow,
  eventFailures: summary.eventFailures,
  missingBenchmark: summary.missingBenchmark,
  incompleteBenchmark: summary.incompleteBenchmark,
  missingHarnessStory: summary.missingHarnessStory,
  reportPath,
}, null, 2))
if (summary.wrongTheme.length || summary.overflow.length || summary.eventFailures.length || summary.missingBenchmark.length || summary.incompleteBenchmark.length || summary.missingHarnessStory.length) process.exitCode = 1
