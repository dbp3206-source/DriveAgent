// Isolated layout regression check using the product's actual CSS and synthetic copy.
// It does not authenticate, call APIs, or load any user content.
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(scriptDir, '..')
const rootDir = path.resolve(frontendDir, '..')
const outDir = path.join(rootDir, 'design-work', 'qa', 'settings-retention-layout-20261017')
const styleFiles = [
  'src/legacy-surface-recovery.css',
  'src/styles.css',
  'src/workspace.css',
  'src/mascot-restore.css',
  'src/theme-polish.css',
  'src/release-canvas.css',
]
const styles = (await Promise.all(styleFiles.map(file => readFile(path.join(frontendDir, file), 'utf8'))))
  .join('\n')
const markup = `
  <div class="app-shell">
    <aside class="sidebar"><div class="brand-lockup">Veridra</div></aside>
    <div class="workspace">
      <header class="topbar"><h1>Cài đặt</h1></header>
      <main class="page-content">
        <section class="stack-page settings-page">
          <div class="page-heading"><div><h2>Cài đặt Veridra</h2><p>Nhóm cài đặt tổng thể.</p></div></div>
          <nav class="settings-index" aria-label="Nhóm cài đặt"><button>Hệ thống</button><button>Dữ liệu đã lưu</button></nav>
          <section id="settings-system" class="settings-group"><header class="settings-group__heading"><div><span>Hệ thống</span><h3>Trạng thái dịch vụ</h3></div><p>Cấu hình hệ thống.</p></header><p>Dữ liệu giả lập.</p></section>
          <section id="settings-retention" class="settings-group retention-settings"><header class="settings-group__heading"><div><span>Dữ liệu đã lưu</span><h3>Thời hạn lưu giữ</h3></div><p>Dữ liệu Veridra đến hạn sau 30 ngày. Trước khi dọn, Veridra hiển thị phạm vi và chờ bạn xác nhận.</p></header><p>Việc dọn chỉ áp dụng cho dữ liệu Veridra đã lưu. Bản gốc Google không bị xóa.</p><button>Kiểm tra dữ liệu cần dọn</button></section>
          <section class="operation-ledger settings-group"><header><h3>Thao tác Google cần theo dõi</h3></header><p>Dữ liệu giả lập.</p></section>
          <section class="gemini-credentials settings-group"><header><h3>Gemini API & hạn mức</h3></header><p>Dữ liệu giả lập.</p></section>
          <section id="settings-experience" class="settings-group"><header><h3>Trải nghiệm</h3></header></section>
          <section id="settings-google" class="settings-group"><header><h3>Google Workspace</h3></header></section>
          <section class="oauth-scope-ledger settings-group"><h3>Quyền Google</h3></section>
          <section class="settings-security settings-group"><h3>Bảo mật</h3></section>
        </section>
      </main>
    </div>
  </div>`

await mkdir(outDir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const cases = [
  { name: 'desktop-light', viewport: { width: 1280, height: 900 }, theme: 'light' },
  { name: 'mobile-light', viewport: { width: 390, height: 844 }, theme: 'light' },
  { name: 'desktop-dark', viewport: { width: 1280, height: 900 }, theme: 'dark' },
  { name: 'mobile-dark', viewport: { width: 390, height: 844 }, theme: 'dark' },
]
const results = []

try {
  for (const item of cases) {
    const page = await browser.newPage({ viewport: item.viewport, reducedMotion: 'reduce' })
    await page.setContent(`<html data-theme="${item.theme}"><head><style>${styles}</style></head><body>${markup}</body></html>`)
    const layout = await page.evaluate(() => {
      const page = document.querySelector('.settings-page')
      const retention = document.querySelector('#settings-retention')
      const system = document.querySelector('#settings-system')
      const heading = retention?.querySelector('.settings-group__heading')
      const rect = element => {
        const box = element.getBoundingClientRect()
        return {
          left: box.left,
          right: box.right,
          top: box.top,
          bottom: box.bottom,
          width: box.width,
        }
      }
      return {
        viewportWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        settings: rect(page),
        system: rect(system),
        retention: rect(retention),
        retentionHeading: rect(heading),
      }
    })
    const tolerance = 2
    const fullWidth = layout.retention.width >= layout.settings.width * 0.95
    const belowSystem = layout.retention.top >= layout.system.bottom - tolerance
    const noOverflow = layout.documentWidth <= layout.viewportWidth + tolerance
    const result = { ...item, ...layout, fullWidth, belowSystem, noOverflow }
    results.push(result)
    await page.screenshot({ path: path.join(outDir, `${item.name}.png`), fullPage: true })
    await page.close()
  }
} finally {
  await browser.close()
}

const report = {
  purpose: 'Verify the retention settings section spans the settings grid without horizontal overflow.',
  source: styleFiles,
  data: 'Synthetic UI copy only; no API, account, or user content was loaded.',
  passed: results.every(item => item.fullWidth && item.belowSystem && item.noOverflow),
  results,
}
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify({ passed: report.passed, results, outDir }, null, 2))
if (!report.passed) process.exitCode = 1
