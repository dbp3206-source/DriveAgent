import test from 'node:test'
import assert from 'node:assert/strict'
import {waitForChatTask} from './chatTaskPolling.mjs'

test('waits for queued/running SQL state and returns checkpoint exactly once', async () => {
  const states = [{status: 'queued'}, {status: 'running'}, {status: 'completed', result: {answer: 'ready'}}]
  let count = 0
  const events = []
  const result = await waitForChatTask(async () => states[count++], undefined,
    state => events.push(state.status), {sleep: async () => {}})
  assert.deepEqual(result, {answer: 'ready'})
  assert.equal(count, 3)
  assert.deepEqual(events, ['queued', 'running', 'completed'])
})

test('retries server restart/transport failures without resubmitting task', async () => {
  let count = 0
  const result = await waitForChatTask(async () => {
    if (count++ < 2) throw Object.assign(new Error('offline'), {status: 503})
    return {status: 'completed', result: {answer: 'recovered'}}
  }, undefined, undefined, {sleep: async () => {}})
  assert.equal(result.answer, 'recovered')
  assert.equal(count, 3)
})

test('does not retry authentication errors or hide terminal failure', async () => {
  await assert.rejects(waitForChatTask(async () => {
    throw Object.assign(new Error('sign in'), {status: 401})
  }), /sign in/)
  await assert.rejects(waitForChatTask(async () => ({status: 'failed', error: 'quota'})), /quota/)
})

test('aborted observation never submits server cancellation', async () => {
  const controller = new AbortController()
  controller.abort()
  let reads = 0
  await assert.rejects(waitForChatTask(async () => { reads++; return {} }, controller.signal),
    error => error.name === 'AbortError')
  assert.equal(reads, 0)
})
