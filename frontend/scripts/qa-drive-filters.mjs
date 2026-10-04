// Real Chromium rendering with synthetic API responses; no Google calls or user data.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const base = process.env.QA_FRONTEND_URL || 'http://127.0.0.1:4173'
const out = path.resolve('../design-work/qa/screenshots/drive-filters-20261004')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []
try {
  for (const [width, theme] of [[1440, 'dark'], [768, 'dark'], [375, 'light'], [320, 'dark']]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
    await context.addInitScript(value => localStorage.setItem('drive-agent-theme', value), theme)
    const page = await context.newPage()
    const requests = []
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url())
      if (url.pathname === '/api/auth/status') {
        return route.fulfill({ json: {
          authenticated: true, oauth_configured: true, gemini_configured: true, demo_login_enabled: false,
          user: { id: 'synthetic-qa', email: 'qa@example.invalid', display_name: 'Dữ liệu kiểm giao diện',
            avatar_url: null, role: 'owner', scopes: [] },
        } })
      }
      if (url.pathname === '/api/drive/files') {
        requests.push(Object.fromEntries(url.searchParams))
        const folder = url.searchParams.get('item_type') === 'folders'
        return route.fulfill({ json: {
          files: [{ id: folder ? 'folder-qa' : 'file-qa', name: folder ? 'Hồ sơ khách hàng mẫu' : 'Ghi chú cuộc hẹn mẫu',
            mime_type: folder ? 'application/vnd.google-apps.folder' : 'text/plain',
            modified_time: '2026-10-04T10:00:00Z', size: '2048', web_view_link: null,
            owners: ['Dữ liệu giả lập'], indexed: false, index_status: 'not_indexed' }],
          next_page_token: null,
        } })
      }
      return route.fulfill({ json: {} })
    })
    await page.goto(`${base}/#/drive`, { waitUntil: 'domcontentloaded' })
    await page.locator('.drive-file-table').waitFor()
    await page.waitForFunction(() => Number(getComputedStyle(document.querySelector('.stack-page')).opacity) >= .99)
    assert.equal(requests.at(-1).item_type, undefined)
    assert.equal(requests.at(-1).starred, undefined)
    const dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }))
    assert.ok(dimensions.scrollWidth <= width + 1, `Overflow at ${width}`)
    const screenshot = path.join(out, `${width}-${theme}.png`)
    await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled' })
    for (const [label, expected] of [
      ['Thư mục', { item_type: 'folders' }],
      ['Đã gắn sao', { item_type: 'folders', starred: 'true' }],
      ['Tệp', { item_type: 'files', starred: 'true' }],
      ['Đã gắn sao', { item_type: 'files' }],
      ['Tất cả', {}],
    ]) {
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/drive/files')
      await page.getByRole('button', { name: label, exact: true }).click()
      await response
      await page.locator('.drive-file-table').waitFor()
      assert.equal(requests.at(-1).item_type, expected.item_type)
      assert.equal(requests.at(-1).starred, expected.starred)
    }
    await page.locator('#drive-search').fill('khách hàng')
    const searchResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/drive/files')
    await page.getByRole('button', { name: 'Tìm kiếm', exact: true }).click()
    await searchResponse
    assert.equal(requests.at(-1).query, 'khách hàng')
    assert.deepEqual(errors, [])
    results.push({ width, theme, ...dimensions, requests, errors, screenshot })
    await context.close()
  }
} finally {
  await browser.close()
}
await writeFile(path.join(out, 'report.json'), JSON.stringify({ synthetic: true, results }, null, 2))
console.log(JSON.stringify({ passed: results.length, synthetic: true, screenshots: results.map(row => row.screenshot) }, null, 2))
