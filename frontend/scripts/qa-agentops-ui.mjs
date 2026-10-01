// Real Chrome QA. No cloud writes. Optional single synthetic model request.
import {execFileSync} from 'node:child_process'
import {mkdir, writeFile} from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {chromium} from 'playwright'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = path.join(root, 'backend')
const cookie = execFileSync(path.join(backend, '.venv/Scripts/python.exe'), ['-c',
  'import sys;sys.path.insert(0,"../scripts");from qa_google_read_smoke import _connected_owner_id;from evaluate_gate2_live import _session_cookie;print(_session_cookie(_connected_owner_id()),end="")',
], {cwd: backend, encoding: 'utf8'}).trim()
const base = 'http://127.0.0.1:8000'
const output = path.join(root, 'design-work/qa/screenshots/agentops-20260930')
await mkdir(output, {recursive: true})
const browser = await chromium.launch({channel: 'chrome', headless: true})
const checks = []
const errors = []
try {
  for (const theme of ['light', 'dark']) {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}})
    await context.addCookies([{name: 'drive_agent_session', value: cookie, url: base}])
    await context.addInitScript(t => localStorage.setItem('drive-agent-theme', t), theme)
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${base}/#/home`)
    await page.locator('.home-flow-layer i').first().waitFor()
    const motion = await page.locator('.home-flow-layer i').first().evaluate(e => getComputedStyle(e).animationName)
    await page.screenshot({path: path.join(output, `${theme}-home.png`)})
    await page.emulateMedia({reducedMotion: 'reduce'})
    const reduced = await page.locator('.home-flow-layer i').first().evaluate(e => getComputedStyle(e).animationName)
    checks.push({name: `${theme}-motion`, passed: motion === 'veridra-flow' && reduced === 'none', motion, reduced})
    if (theme === 'light') {
      await page.goto(`${base}/#/audit`)
      await page.getByRole('button', {name: 'Chạy regression offline', exact: true}).waitFor()
      const queuedResponse = page.waitForResponse(r => r.url().endsWith('/api/evaluation-jobs') && r.request().method() === 'POST')
      await page.getByRole('button', {name: 'Chạy regression offline', exact: true}).click()
      const queued = await (await queuedResponse).json()
      await page.waitForFunction(id => {
        const status = document.querySelector('.evaluation-job-control [role="status"]')
        return status?.getAttribute('data-job-id') === id && status.querySelector('strong')?.textContent === 'completed'
      }, queued.job_id, {timeout: 30000})
      checks.push({name: 'durable-evaluation-ui', passed: await page.locator('.evaluation-job-control li').count() === 4})
      await page.reload()
      await page.waitForFunction(() => document.querySelector('.evaluation-job-control strong')?.textContent === 'completed')
      checks.push({name: 'evaluation-reload', passed: await page.locator('.evaluation-job-control li').count() === 4})
      await page.locator('.evaluation-job-control').screenshot({path: path.join(output, 'evaluation-job.png')})
      if (process.env.VERIDRA_QA_LIVE_CHAT === '1') {
        await page.goto(`${base}/#/chat`)
        await page.locator('#chat-input').waitFor()
        const responsePromise = page.waitForResponse(r => r.url() === `${base}/api/chat` && r.request().method() === 'POST', {timeout: 75000})
        await page.locator('#chat-input').fill('/general Tình huống giả lập, chỉ dùng số liệu sau: lớp có 40 học sinh, 10 em điểm thấp, 6 em chuyên cần thấp, 4 em thuộc cả hai nhóm. Tính số em thuộc ít nhất một nhóm, chỉ điểm thấp, chỉ chuyên cần thấp và không thuộc nhóm nào. Trình bày bảng và phép tính, không đọc nguồn ngoài.')
        await page.getByRole('button', {name: 'Gửi', exact: true}).click()
        const pendingVisible = await page.locator('.agent-working-events').waitFor({timeout: 12000}).then(() => true).catch(() => false)
        if (pendingVisible) await page.locator('.agent-working').screenshot({path: path.join(output, 'live-progress.png')})
        const response = await responsePromise
        const body = await response.json()
        const answer = String(body.answer ?? '')
        const id = response.headers()['x-request-id']
        const progress = id ? await context.request.get(`${base}/api/chat/progress/${id}`).then(r => r.json()) : {events: []}
        checks.push({name: 'synthetic-chat', passed: response.ok() && body.status === 'completed' && ['12','6','2','28'].every(n => new RegExp(`\\b${n}\\b`).test(answer)), httpStatus: response.status(), pendingVisible, eventCount: progress.events.length, sessionId: body.session_id ?? null})
        await page.locator('.message--assistant').last().screenshot({path: path.join(output, 'synthetic-answer.png')}).catch(() => {})
      }
    }
    await context.close()
  }
} catch (error) { errors.push(String(error)) }
finally { await browser.close() }
const report = {checks, errors, passed: errors.length === 0 && checks.every(c => c.passed), cloudWrites: 0}
await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
if (!report.passed) process.exitCode = 1
