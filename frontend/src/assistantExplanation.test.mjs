import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

// Source contract checks, supplemented by real browser QA; not model evaluation.
const page = readFileSync(new URL('./pages/HarnessPage.tsx', import.meta.url), 'utf8')
const guide = page.slice(page.indexOf('export function HarnessPage()'))

test('approved four-step explanation is short and keeps the approval boundary explicit', () => {
  assert.match(guide, /Cách trợ lý làm việc/)
  const headings = [...guide.matchAll(/<h2>([^<]+)<\/h2>/g)].map(match => match[1])
  assert.deepEqual(headings, ['Hiểu việc', 'Chọn nguồn', 'Đưa kết quả', 'Duyệt và bàn giao'])
  assert.match(guide, /Chưa xác nhận kết quả thì không tự ghi lại/)
  assert.match(guide, /câu hỏi đơn giản không phải chạy mọi trợ lý/)
  assert.match(guide, /không ép thêm nhiều lựa chọn/)
})

test('only the selected everyday example renders and illustrations are clearly labeled', () => {
  assert.match(guide, /useState\(0\)/)
  assert.match(guide, /ASSISTANT_EXAMPLES\[exampleIndex\]/)
  assert.match(guide, /aria-pressed=\{index === exampleIndex\}/)
  assert.match(guide, /Ví dụ minh họa, không phải kết quả chạy thật/)
  assert.match(guide, /không phải số đo hoặc cam kết/)
  assert.equal((page.match(/src="\/harness\/veridra-verified-workflow.png"/g) ?? []).length, 1)
})

test('technical content is conditional, starts closed without a bookmark, and retains deep links', () => {
  assert.match(guide, /params.domain !== undefined \|\| params.stepIndex !== undefined/)
  assert.match(guide, /showTechnical && <div id="assistant-technical-details"><HarnessTechnicalDetails \/>/)
  assert.match(guide, /aria-expanded=\{showTechnical\}/)
  assert.match(guide, /aria-controls="assistant-technical-details"/)
  assert.match(page, /#\/harness\?domain=\$\{selectedId\}&step=\$\{activeStep \+ 1\}/)
  assert.doesNotMatch(page, /isInternalUpdate/)
  assert.doesNotMatch(page, /Nhấn vào từng bước để xem việc thật đã xảy ra/)
})
