import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { documentPreviewKey, renewDocumentPreviewKey } from './documentPreviewRecovery.mjs'
import { suggestedDocumentTitle, validatedDocumentTitle } from './documentTitle.mjs'
import { markdownToDocumentBlocks } from './documentMarkdown.js'

// Execute the real handlers extracted by TypeScript AST. This checks sequencing
// and request data, not layout/browser behavior or a real Google write.
const source = readFileSync(new URL('./pages/ChatPage.tsx', import.meta.url), 'utf8')
const parsed = ts.createSourceFile('ChatPage.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
function handler(name) {
  let found
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === name) found = node
    ts.forEachChild(node, visit)
  }
  visit(parsed)
  assert.ok(found, `${name} exists in real ChatPage`)
  return `export ${found.getText(parsed)}`
}
const code = ts.transpileModule(handler('openDocumentExport') + '\n' + handler('exportToGoogleDoc'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText
const message = {id: 'message-01234567', content: '# Bản xem trước\nNội dung giả lập.', citations: []}
const locked = {operation_id: '01234567-89ab-cdef-0123-456789abcdef', digest: 'a'.repeat(64), state: 'pending', title: 'Tên người dùng đã chọn'}
function flow(api) {
  const values = new Map()
  const state = {prepared: {}, target: null, exporting: null, error: ''}
  const exports = {}
  const lock = {current: false}
  vm.runInNewContext(code, {exports, api, ownerId: 'owner-a', docExportLock: lock,
    sessionStorage: {getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value)},
    documentPreviewKey, renewDocumentPreviewKey, suggestedDocumentTitle, validatedDocumentTitle, markdownToDocumentBlocks,
    setPreparedDocs: update => {state.prepared = update(state.prepared)},
    setDocumentTitleTarget: value => {state.target = value},
    setExportingDoc: value => {state.exporting = value},
    setError: value => {state.error = value},
  })
  return {handlers: exports, state, lock}
}

test('real export handler sends the chosen title, not model heading; only prepares', async () => {
  const calls = []
  const {handlers, state, lock} = flow(async (path, init) => {
    calls.push({path, body: JSON.parse(init.body)})
    return {data: locked}
  })
  await handlers.exportToGoogleDoc(message, '  Đề xuất thử cổng nội bộ  ')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].path, '/api/documents/prepare')
  assert.equal(calls[0].body.document.title, 'Đề xuất thử cổng nội bộ')
  assert.equal(calls[0].body.request_key, `doc-export-${message.id}`)
  assert.equal(state.prepared[message.id].title, 'Đề xuất thử cổng nội bộ')
  assert.equal(state.target, null)
  assert.equal(lock.current, false)
  assert.equal(state.exporting, null)
})
test('real lookup opens title dialog only when owner preview is absent', async () => {
  const calls = []
  const {handlers, state} = flow(async path => {calls.push(path); return {data: null}})
  await handlers.openDocumentExport(message)
  assert.deepEqual(calls, [`/api/documents/previews/doc-export-${message.id}`])
  assert.equal(state.target.message.id, message.id)
  assert.equal(state.target.title, suggestedDocumentTitle(message.content))
})
for (const status of ['pending', 'expired', 'running', 'uncertain', 'succeeded', 'failed']) {
  test(`real reload lookup recovers ${status} preview without renaming or preparing again`, async () => {
    const calls = []
    const {handlers, state} = flow(async path => {calls.push(path); return {data: {...locked, state: status}}})
    await handlers.openDocumentExport(message)
    assert.equal(calls.length, 1)
    assert.equal(state.target, null)
    assert.equal(state.prepared[message.id].title, locked.title)
    assert.equal(state.prepared[message.id].operation_id, locked.operation_id)
    assert.equal(state.prepared[message.id].state, status)
  })
}
test('lookup failure fails closed, invalid name does not call API, write failure never retries', async () => {
  let count = 0
  const {handlers, state, lock} = flow(async () => {count++; throw Error('offline')})
  await handlers.openDocumentExport(message)
  assert.equal(count, 1)
  assert.equal(state.target, null)
  await handlers.exportToGoogleDoc(message, '')
  assert.equal(count, 1)
  await handlers.exportToGoogleDoc(message, 'Tên hợp lệ')
  assert.equal(count, 2)
  assert.equal(Object.keys(state.prepared).length, 0)
  assert.equal(lock.current, false)
  assert.equal(state.exporting, null)
})
test('in-flight guard rejects concurrent export before another request is issued', async () => {
  let release
  let count = 0
  const {handlers} = flow(() => {count++; return new Promise(resolve => {release = resolve})})
  const first = handlers.exportToGoogleDoc(message, 'Tên một')
  await handlers.exportToGoogleDoc(message, 'Tên hai')
  assert.equal(count, 1)
  release({data: locked})
  await first
})
