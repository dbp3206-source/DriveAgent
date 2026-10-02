import { execFileSync } from 'node:child_process'
import { chromium } from 'playwright'
const cookie = execFileSync('../backend/.venv/Scripts/python.exe', ['-c',
  'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _cookie;print(_cookie(),end="")'],
{ cwd: '../backend', encoding: 'utf8' }).trim()
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 320, height: 844 } })
  await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: 'http://127.0.0.1:8000' }])
  const page = await context.newPage()
  for (const route of ['memory', 'harness', 'skills']) {
    await page.goto(`http://127.0.0.1:8000/#/${route}`)
    await page.waitForTimeout(1500)
    console.log(JSON.stringify({ route, elements: await page.evaluate(() =>
      [...document.querySelectorAll('main *')].filter(el => {
        for (let ancestor = el.parentElement; ancestor && ancestor.tagName !== 'MAIN'; ancestor = ancestor.parentElement) {
          if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(ancestor).overflowX)) return false
        }
        return true
      }).map(el => ({
        tag: el.tagName, class: el.className, right: el.getBoundingClientRect().right,
        width: el.getBoundingClientRect().width,
        parent: el.parentElement?.className,
        scroll: el.scrollWidth,
      })).filter(row => row.right > innerWidth + 1 && /^[A-Z]+$/.test(row.tag)).slice(0, 18)) }))
  }
} finally { await browser.close() }
