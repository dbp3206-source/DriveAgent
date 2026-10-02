import test from 'node:test'
import assert from 'node:assert/strict'
import { ApiError, api, apiBlob, apiText, formatDate } from './api.ts'

test('bounded upload preserves binary body and explicit content type', async (t) => {
  const body = new Blob(['sample'])
  stubApi(t, async (_path, init) => {
    assert.equal(init.body, body)
    assert.equal(init.headers.get('Content-Type'), 'application/octet-stream')
    return Response.json({ id: 'saved' })
  })
  assert.deepEqual(await api('/api/local-sources', {
    method: 'POST', body, headers: { 'Content-Type': 'application/octet-stream' },
  }), { id: 'saved' })
})

test('bounded readers preserve text and binary responses', async (t) => {
  stubApi(t, async () => new Response('xin chào', { headers: { 'Content-Type': 'text/plain' } }))
  assert.equal(await apiText('/api/local-sources/a/text'), 'xin chào')
  assert.equal(await (await apiBlob('/api/gmail/attachment')).text(), 'xin chào')
})

test('deadline bounds a stalled request without retrying a write', async (t) => {
  let calls = 0
  let signal
  const events = stubApi(t, async (_path, init) => {
    calls++
    signal = init.signal
    return new Promise(() => {})
  })
  await assert.rejects(api('/api/artifacts', {
    method: 'POST', body: '{}', timeoutMs: 10,
  }), (error) => error instanceof ApiError && error.code === 'request_timeout')
  assert.equal(calls, 1)
  assert.equal(signal.aborted, true)
  assert.deepEqual(events, [])
})

test('deadline also bounds a stalled response body', async (t) => {
  stubApi(t, async () => ({
    ok: true, status: 200, json: () => new Promise(() => {}),
  }))
  await assert.rejects(api('/api/system/status', { timeoutMs: 10 }),
    (error) => error.code === 'request_timeout')
})

test('caller cancellation remains an AbortError and cancels the request', async (t) => {
  let signal
  stubApi(t, async (_path, init) => {
    signal = init.signal
    return new Promise(() => {})
  })
  const caller = new AbortController()
  const pending = api('/api/chat/tasks', { signal: caller.signal, timeoutMs: 500 })
  caller.abort()
  await assert.rejects(pending, (error) => error.name === 'AbortError')
  assert.equal(signal.aborted, true)
})

test('an already cancelled request never reaches fetch', async (t) => {
  let calls = 0
  stubApi(t, async () => { calls++; return Response.json({}) })
  const caller = new AbortController()
  caller.abort()
  await assert.rejects(api('/api/auth/me', { signal: caller.signal }),
    (error) => error.name === 'AbortError')
  assert.equal(calls, 0)
})

function stubApi(t, fetchImpl) {
  const previousFetch = globalThis.fetch
  const previousWindow = globalThis.window
  const events = []

  globalThis.fetch = fetchImpl
  globalThis.window = {
    dispatchEvent(event) {
      events.push(event)
      return true
    },
  }
  t.after(() => {
    globalThis.fetch = previousFetch
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  })
  return events
}

test('Google refresh failure marks only that integration as degraded', async (t) => {
  const events = stubApi(t, async () => Response.json(
    { detail: 'Google refresh failed safely.', code: 'google_connection_error', retryable: true },
    { status: 503, headers: { 'X-Request-ID': 'drive-refresh_42' } },
  ))

  await assert.rejects(api('/api/drive/files'), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 503)
    assert.equal(error.code, 'google_connection_error')
    assert.equal(error.requestId, 'drive-refresh_42')
    assert.match(error.message, /Mã yêu cầu: drive-refresh_42/)
    return true
  })
  assert.deepEqual(events.map(({ detail }) => detail), [
    { service: 'drive', status: 'degraded' },
  ])
})

test('does not display or preserve malformed request identifiers', async (t) => {
  stubApi(t, async () => ({
    ok: false,
    status: 502,
    headers: { get: () => 'bad id\r\nsecret' },
    json: async () => ({ detail: 'Lỗi provider.' }),
  }))

  await assert.rejects(api('/api/drive/files'), (error) => {
    assert.equal(error.requestId, undefined)
    assert.equal(error.message, 'Lỗi provider.')
    return true
  })
})

test('Google scope failure shows permission state instead of connection outage', async (t) => {
  const events = stubApi(t, async () => Response.json(
    { detail: 'Google permission required.', code: 'gmail_insufficient_permissions' },
    { status: 403 },
  ))

  await assert.rejects(api('/api/gmail/messages'), ApiError)
  assert.deepEqual(events.map(({ detail }) => detail), [
    { service: 'gmail', status: 'permission' },
  ])
})

test('disabled Gmail API is shown as configuration issue, not outage', async (t) => {
  const events = stubApi(t, async () => Response.json(
    { detail: 'Enable Gmail API.', code: 'gmail_api_disabled' },
    { status: 403 },
  ))

  await assert.rejects(api('/api/gmail/messages'), ApiError)
  assert.deepEqual(events.map(({ detail }) => detail), [
    { service: 'gmail', status: 'misconfigured' },
  ])
})

test('plain app-session 401 does not mark Google as degraded', async (t) => {
  const events = stubApi(t, async () => Response.json(
    { detail: 'Bạn chưa đăng nhập.' },
    { status: 401 },
  ))

  await assert.rejects(api('/api/gmail/messages'), ApiError)
  assert.deepEqual(events, [])
})

test('successful Google request marks only its service healthy', async (t) => {
  const events = stubApi(t, async () => Response.json({ messages: [] }))

  assert.deepEqual(await api('/api/gmail/messages'), { messages: [] })
  assert.deepEqual(events.map(({ detail }) => detail), [
    { service: 'gmail', status: 'healthy' },
  ])
})

test('local app network failure does not misclassify Google as degraded', async (t) => {
  const events = stubApi(t, async () => { throw new TypeError('connection refused') })

  await assert.rejects(api('/api/drive/files'), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 0)
    assert.equal(error.code, 'network_error')
    return true
  })
  assert.deepEqual(events, [])
})

test('generic server 503 does not imply a Google provider outage', async (t) => {
  const events = stubApi(t, async () => Response.json(
    { detail: 'Local service unavailable.', code: 'internal_error' },
    { status: 503 },
  ))

  await assert.rejects(api('/api/drive/files'), ApiError)
  assert.deepEqual(events, [])
})

test('aborted request does not create a false degradation signal', async (t) => {
  const events = stubApi(t, async () => { throw new DOMException('Aborted', 'AbortError') })

  await assert.rejects(api('/api/drive/files'), (error) => {
    assert.ok(error instanceof DOMException)
    assert.equal(error.name, 'AbortError')
    return true
  })
  assert.deepEqual(events, [])
})

test('date formatter fails safely for missing or malformed provider dates', () => {
  assert.equal(formatDate(null), 'Không rõ')
  assert.equal(formatDate('not-an-email-date'), 'Không rõ')
  assert.match(formatDate('Fri, 11 Sep 2026 20:40:00 +0000'), /2026/)
})
