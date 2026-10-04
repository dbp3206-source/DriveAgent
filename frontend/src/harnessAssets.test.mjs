import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

test('user supplied workflow illustration is shipped intact and displayed without theme duplication', () => {
  const bytes = readFileSync(new URL('../public/harness/veridra-verified-workflow.png', import.meta.url))
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
  assert.equal(bytes.readUInt32BE(16), 1672)
  assert.equal(bytes.readUInt32BE(20), 941)
  const page = readFileSync(new URL('./pages/HarnessPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /src="\/harness\/veridra-verified-workflow\.png"/)
  assert.doesNotMatch(page, /visual-check\.1440x900/)
  assert.match(page, /không phải số đo hoặc cam kết/)
})
