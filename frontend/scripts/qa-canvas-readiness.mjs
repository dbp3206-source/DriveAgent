// Real browser QA; account screenshots are local/private, never publish them.
import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = path.join(root, 'backend')
const cookie = execFileSync(path.join(backend, '.venv/Scripts/python.exe'), ['-c',
  'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _connected_owner_id;from evaluate_gate2_live import _session_cookie;print(_session_cookie(_connected_owner_id()),end="")',
], { cwd: backend, encoding: 'utf8' }).trim()
const base = 'http://127.0.0.1:8000'
const output = path.join(root, 'design-work/qa/screenshots/canvas-readiness-20260930')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []
try {
  for (const theme of ['light', 'dark']) {
    for (const width of [320, 375, 414, 768, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
      await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
      await context.addInitScript(value => localStorage.setItem('drive-agent-theme', value), theme)
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      for (const route of ['home', 'local', 'audit']) {
        await page.goto(`${base}/#/${route}`, { waitUntil: 'domcontentloaded' })
        await page.locator('.workspace-canvas').waitFor()
        if (route === 'audit') await page.locator('.readiness-provenance').waitFor()
        await page.waitForTimeout(200)
        const state = await page.evaluate(() => {
          const canvas = document.querySelector('.workspace-canvas')
          const style = getComputedStyle(canvas)
          const wrapper = document.querySelector('.page-content')
          return {
            canvasCount: document.querySelectorAll('.workspace-canvas').length,
            grid: style.backgroundImage.includes('linear-gradient'),
            canvasColor: style.backgroundColor,
            wrapperColor: wrapper ? getComputedStyle(wrapper).backgroundColor : null,
            overflow: document.documentElement.scrollWidth > innerWidth + 1,
            motion: getComputedStyle(canvas, '::after').animationName,
            verdict: document.querySelector('.readiness-status')?.dataset.verdict ?? null,
          }
        })
        if (route === 'audit') {
          const disclosure = page.locator('.readiness-gate summary').first()
          await disclosure.focus()
          await page.keyboard.press('Enter')
          state.keyboardDisclosure = await disclosure.evaluate(element => element.parentElement.open)
        }
        if (route === 'home') {
          const toggle = page.getByRole('button', { name: /nền động/i })
          state.toggleExists = await toggle.count() > 0
          if (state.toggleExists) {
            await toggle.click()
            state.toggleChangesCanvas = await page.locator('.workspace-canvas--motion').count() === 0
          }
        }
        const screenshot = path.join(output, `${theme}-${width}-${route}.png`)
        await page.screenshot({ path: screenshot })
        results.push({ theme, width, route, ...state, errors: [...errors], screenshot })
      }
      await context.close()
    }
  }
} finally { await browser.close() }
const failures = results.filter(row => row.overflow || row.errors.length || row.canvasCount !== 1 || !row.grid
  || row.wrapperColor !== 'rgba(0, 0, 0, 0)' || row.motion !== 'none'
  || (row.route === 'audit' && (row.verdict !== 'HOLD' || !row.keyboardDisclosure))
  || (row.route === 'home' && (!row.toggleExists || !row.toggleChangesCanvas)))
await writeFile(path.join(output, 'report.json'), JSON.stringify({ results, failures }, null, 2))
console.log(JSON.stringify({ pages: results.length, failures, report: path.join(output, 'report.json') }, null, 2))
if (failures.length) process.exitCode = 1
