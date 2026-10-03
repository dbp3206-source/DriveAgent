import assert from 'node:assert/strict'
import test from 'node:test'
import { readHistoryWithRecovery } from './historyRecovery.mjs'

test('successful history read runs once without waiting', async () => {
  let calls = 0
  const result = await readHistoryWithRecovery(async () => {
    calls += 1
    return { items: [], next_cursor: null }
  }, new AbortController().signal, async () => assert.fail('unnecessary wait'))
  assert.deepEqual(result, { items: [], next_cursor: null })
  assert.equal(calls, 1)
})
test('recovers one transient failure and returns actual history', async () => {
  let calls = 0
  const result = await readHistoryWithRecovery(async () => {
    if (++calls === 1) throw { status: 0 }
    return { items: ['saved'], next_cursor: 'next' }
  }, new AbortController().signal, async () => {})
  assert.deepEqual(result, { items: ['saved'], next_cursor: 'next' })
  assert.equal(calls, 2)
})
test('stops after two server failures', async () => {
  let calls = 0
  await assert.rejects(readHistoryWithRecovery(async () => {
    calls += 1
    throw new Error('down', { cause: null })
  }, new AbortController().signal), /down/)
  assert.equal(calls, 1)
  calls = 0
  await assert.rejects(readHistoryWithRecovery(async () => {
    calls += 1
    throw Object.assign(new Error('server'), { status: 503 })
  }, new AbortController().signal, async () => {}), /server/)
  assert.equal(calls, 2)
})
test('never retries authentication or permission failures', async () => {
  for (const status of [401, 403, 404, 429]) {
    let calls = 0
    await assert.rejects(readHistoryWithRecovery(async () => {
      calls += 1
      throw Object.assign(new Error('denied'), { status })
    }, new AbortController().signal), /denied/)
    assert.equal(calls, 1)
  }
})
test('unmount abort prevents the scheduled retry', async () => {
  const controller = new AbortController()
  let calls = 0
  await assert.rejects(readHistoryWithRecovery(async () => {
    calls += 1
    throw { status: 0 }
  }, controller.signal, async () => controller.abort()), { name: 'AbortError' })
  assert.equal(calls, 1)
})
