import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./pages/ArtifactsPage.tsx', import.meta.url), 'utf8')

test('saved-result editor does not introduce a second main landmark', () => {
  assert.doesNotMatch(source, /<main\b/)
  assert.match(source, /aria-label="Chỉnh sửa kết quả đã lưu"/)
})

test('document templates are unfinished business forms, not fabricated measurements', () => {
  assert.doesNotMatch(source, /92%|1\.8s|Antigravity Typography|Markdown Rendered/)
  assert.match(source, /không phải kết quả đo hoặc báo cáo đã kiểm chứng/)
  assert.match(source, /\[Điền nguồn\]/)
  assert.match(source, /Người phụ trách/)
})

test('editor controls explain operations in Vietnamese', () => {
  for (const label of ['Chữ đậm', 'Chữ nghiêng', 'Danh sách công việc', 'Chèn liên kết', 'Bản xem trước']) {
    assert.ok(source.includes(label), label)
  }
  assert.doesNotMatch(source, /\(Bold\)|\(Italic\)|\(Task checklist\)|Live Preview/)
})
