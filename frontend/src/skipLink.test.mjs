import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('./components/AppShell.tsx', import.meta.url), 'utf8')

test('skip link preserves the hash route and focuses main content', () => {
  assert.match(source, /onClick=\{skipToMainContent\}/)
  assert.match(source, /event\.preventDefault\(\)/)
  assert.match(source, /document\.getElementById\('main-content'\)/)
  assert.match(source, /requestAnimationFrame/)
  assert.match(source, /main\?\.focus\(\{ preventScroll: true \}\)/)
})
