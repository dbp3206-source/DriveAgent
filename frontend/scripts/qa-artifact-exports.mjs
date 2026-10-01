// Read-only browser check of all report export formats. Downloaded bytes stay
// in Playwright's temporary context and are not copied into the repository.
import { execFileSync } from 'node:child_process'
import { readFile } from 'node:fs/promises'
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
  for (const [viewportName, viewport] of [
    ['desktop', { width: 1440, height: 900 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    const context = await browser.newContext({ viewport, acceptDownloads: true })
    await context.addCookies([{ name: 'drive_agent_session', value: cookie, url: base }])
    const page = await context.newPage()
    await page.goto(`${base}/#/artifacts`)
    await page.locator('.artifact-item-card').first().click()
    const formatSelect = page.locator('select[aria-label="Định dạng xuất bản đã lưu"]')
    await formatSelect.waitFor()
    for (const format of ['md', 'docx', 'pdf']) {
      await formatSelect.selectOption(format)
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('link', { name: 'Xuất bản đã lưu' }).click(),
      ])
      const bytes = await readFile(await download.path())
      const magic = format === 'md' ? '# ' : format === 'pdf' ? '%PDF-' : 'PK'
      if (!download.suggestedFilename().endsWith(`.${format}`) ||
          !bytes.subarray(0, magic.length).equals(Buffer.from(magic))) {
        throw new Error(`Export ${format} is not a valid download`)
      }
    }
    const title = page.locator('#artifact-title')
    await title.fill(`${await title.inputValue()} (chưa lưu)`)
    if (!await page.getByRole('button', { name: 'Lưu trước khi xuất' }).isDisabled()) {
      throw new Error('Unsaved edits must not download the previous revision')
    }
    console.log(JSON.stringify({ viewport: viewportName, exports: ['md', 'docx', 'pdf'], dirtyGuard: true }))
    await context.close()
  }
} finally {
  await browser.close()
}
