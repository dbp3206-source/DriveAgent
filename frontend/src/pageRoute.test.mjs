import assert from 'node:assert/strict'
import test from 'node:test'
import { hashForPage, pageFromHash } from './pageRoute.mjs'

test('maps explicit hash routes to workspace pages', () => {
  assert.equal(pageFromHash('#/chat'), 'chat')
  assert.equal(pageFromHash('#drive'), 'drive')
  assert.equal(pageFromHash('#/gmail?filter=unread'), 'gmail')
})

test('rejects unknown or empty routes instead of opening the wrong screen', () => {
  assert.equal(pageFromHash(''), null)
  assert.equal(pageFromHash('#/visuals'), null)
  assert.equal(pageFromHash('#/chatty'), null)
})

test('creates stable bookmarkable hashes and rejects invalid page names', () => {
  assert.equal(hashForPage('harness'), '#/harness')
  assert.throws(() => hashForPage('unknown'), /Unknown DriveAgent page/)
})
