// Local synthetic observability UI only. Credentials are never printed.
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'
const root = path.resolve('..')
const env = Object.fromEntries((await readFile(path.join(root, 'ops/secrets/langfuse.env'), 'utf8'))
  .split(/\r?\n/).filter(line => line.includes('=')).map(line => {
    const index = line.indexOf('='); return [line.slice(0, index), line.slice(index + 1)]
  }))
const output = path.join(root, 'design-work/qa/screenshots/langfuse-20260930')
await mkdir(output, {recursive: true})
const browser = await chromium.launch({channel: 'chrome', headless: true})
const page = await browser.newPage({viewport: {width: 1440, height: 900}})
const errors = []
page.on('pageerror', error => errors.push(error.name))
try {
  await page.goto('http://localhost:3035/auth/sign-in')
  await page.getByLabel('Email', {exact: true}).fill(env.LANGFUSE_INIT_USER_EMAIL)
  await page.locator('input[type="password"]').fill(env.LANGFUSE_INIT_USER_PASSWORD)
  await page.getByRole('button', {name: /sign in/i, exact: true}).click()
  await page.waitForURL(url => !url.pathname.includes('/auth/'), {timeout: 30000})
  await page.goto('http://localhost:3035/project/veridra-operations/traces')
  await page.getByText('veridra.request', {exact: true}).first().waitFor({timeout: 45000})
  await page.screenshot({path: path.join(output, 'traces.png')})
  const report = {signedIn: true, requestTraceRendered: true, errors, passed: errors.length === 0}
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
} finally { await browser.close() }
