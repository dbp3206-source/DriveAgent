import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('./pages/MemoryPage.tsx', import.meta.url), 'utf8')

test('memory management can list archived items without changing agent retrieval', () => {
  assert.ok(page.includes('/api/memories?include_archived=true'))
  assert.ok(page.includes("aria-label={item.is_archived ? 'Khôi phục' : 'Lưu trữ'}"))
  assert.ok(page.includes('is_archived: !item.is_archived'))
})
