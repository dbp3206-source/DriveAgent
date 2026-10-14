import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'
import React from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import * as activity from './chatActivity.mjs'
import {ChatTaskError, waitForChatTask} from './chatTaskPolling.mjs'

const id = '11111111-1111-4111-8111-111111111111'
const session = '22222222-2222-4222-8222-222222222222'
const event = phase => ({ownerId: 'owner-a', taskId: id, sessionId: session, phase})

test('background completion stays unread; a viewed conversation does not notify', () => {
  const running = activity.reduceChatActivity(null, event('running'), 'owner-a', false)
  assert.equal(running.unread, false)
  assert.equal(activity.reduceChatActivity(running, event('completed'), 'owner-a', false).unread, true)
  assert.equal(activity.reduceChatActivity(running, event('completed'), 'owner-a', true).unread, false)
})
test('terminal outcomes are distinct, never inferred from busy=false', () => {
  for (const phase of ['failed', 'cancelled', 'waiting', 'incomplete']) {
    const value = activity.reduceChatActivity(null, event(phase), 'owner-a', false)
    assert.equal(value.phase, phase)
    assert.notEqual(activity.chatActivityCopy(phase).title, activity.chatActivityCopy('completed').title)
  }
})
test('stale task/other owner cannot replace latest status; duplicate cannot re-alert', () => {
  const complete = activity.reduceChatActivity(null, event('completed'), 'owner-a', false)
  const seen = {...complete, unread: false}
  assert.equal(activity.reduceChatActivity(seen, event('completed'), 'owner-a', false), seen)
  assert.equal(activity.reduceChatActivity(seen, event('running'), 'owner-a', false), seen)
  assert.equal(activity.reduceChatActivity(seen, {...event('failed'), taskId: session}, 'owner-a', false), seen)
  assert.equal(activity.reduceChatActivity(seen, event('failed'), 'owner-b', false), seen)
})
test('new task replaces old notification and recovery may settle waiting state', () => {
  const previous = activity.reduceChatActivity(null, event('completed'), 'owner-a', false)
  const next = activity.reduceChatActivity(previous, {...event('running'), taskId: session}, 'owner-a', false)
  assert.equal(next.taskId, session)
  const waiting = activity.reduceChatActivity(null, event('waiting'), 'owner-a', false)
  assert.equal(activity.reduceChatActivity(waiting, event('completed'), 'owner-a', false).phase, 'completed')
})
test('metadata is owner-scoped, reload-safe and excludes prompt/answer', () => {
  const map = new Map()
  const storage = {getItem: key => map.get(key), setItem: (key, value) => map.set(key, value)}
  activity.saveChatActivity(storage, {...event('completed'), unread: true, answer: 'private', prompt: 'private'})
  assert.equal([...map.values()][0].includes('private'), false)
  assert.equal(activity.readChatActivity(storage, 'owner-a').sessionId, session)
  assert.equal(activity.readChatActivity(storage, 'owner-b'), null)
  map.set('veridra-chat-activity:owner-a', 'invalid JSON')
  assert.equal(activity.readChatActivity(storage, 'owner-a'), null)
  assert.doesNotThrow(() => activity.saveChatActivity({setItem() {throw Error('denied')}}, {...event('running'), unread: false}))
})
test('polling distinguishes actual terminal errors and observation timeout', async () => {
  for (const phase of ['failed', 'cancelled']) {
    await assert.rejects(waitForChatTask(async () => ({status: phase})), error => error instanceof ChatTaskError && error.phase === phase)
  }
  await assert.rejects(waitForChatTask(async () => ({}), undefined, undefined, {timeoutMs: 0}), error => error.phase === 'waiting')
  await assert.rejects(waitForChatTask(async () => ({status: 'completed'})), error => error.phase === 'waiting')
})

function mascotHtml(phase, enabled = true) {
  const source = readFileSync(new URL('./components/MascotAssistant.tsx', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true}}).outputText
  const require = createRequire(import.meta.url)
  const storage = {getItem: key => key === 'driveagent_mascot_enabled' ? String(enabled) : key === 'driveagent_mascot_minimized' ? 'true' : null}
  const exports = {}
  vm.runInNewContext(code, {exports, localStorage: storage, window: {matchMedia: () => ({matches: true})}, require(path) {
    if (path === 'react' || path === 'react/jsx-runtime') return require(path)
    if (path === '../chatActivity.mjs') return activity
    if (path === 'page-mascot') return {Mascot: () => React.createElement('span')}
    return new Proxy({}, {get: () => () => null})
  }})
  return renderToStaticMarkup(React.createElement(exports.MascotAssistant, {activity: {...event(phase), unread: true}, currentPage: 'drive'}))
}
for (const phase of ['completed', 'incomplete', 'failed', 'cancelled', 'waiting']) {
  test(`minimized companion renders persistent ${phase} notice with action`, () => {
    const html = mascotHtml(phase)
    assert.match(html, /mascot-companion--minimized/)
    assert.match(html, /role="status"/)
    assert.ok(html.includes(activity.chatActivityCopy(phase).title))
    assert.ok(html.includes(activity.chatActivityCopy(phase).action))
    assert.match(html, /Xem thông báo chưa đọc/)
  })
}
test('disabled companion does not re-enable itself to notify', () => assert.equal(mascotHtml('completed', false), ''))

test('full-row mobile notice restores text clipped by legacy icon-only styling', () => {
  const css = readFileSync(new URL('./mascot-restore.css', import.meta.url), 'utf8')
  assert.match(css, /\.topbar__actions \.topbar-chat-indicator > span\s*\{[^}]*clip: auto;[^}]*position: static;[^}]*width: auto;[^}]*height: auto;/)
})
