import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

test('every displayed scenario illustration is shipped as a valid PNG', () => {
  for (const scenario of ['banking', 'education', 'ecommerce']) {
    for (const theme of ['light', 'dark']) {
      const bytes = readFileSync(new URL(`../public/harness/${scenario}.visual-check.1440x900.${theme}.png`, import.meta.url))
      assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
      assert.equal(bytes.readUInt32BE(16), 1440)
      assert.equal(bytes.readUInt32BE(20), 900)
    }
  }
})
