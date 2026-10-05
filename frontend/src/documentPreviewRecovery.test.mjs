import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { documentPreviewKey, renewDocumentPreviewKey } from './documentPreviewRecovery.mjs'

const id = '01234567-89ab-cdef-0123-456789abcdef'
function storage() {
  const values = new Map()
  return { values, getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}

test('authoritative expiry renews a preview; reload and retries retain the same key', async () => {
  const saved = storage()
  assert.equal(documentPreviewKey(saved, 'owner-a', 'message-a'), 'doc-export-message-a')
  const fresh = await renewDocumentPreviewKey(saved, 'owner-a', 'message-a', id, async () => ({state: 'expired'}))
  assert.equal(fresh, `doc-repreview-${id}`)
  assert.equal(documentPreviewKey(saved, 'owner-a', 'message-a'), fresh)
  assert.equal(await renewDocumentPreviewKey(saved, 'owner-a', 'message-a', id, async () => ({state: 'expired'})), fresh)
  assert.equal(documentPreviewKey(saved, 'owner-b', 'message-a'), 'doc-export-message-a')
  assert.equal(documentPreviewKey(saved, 'owner-a', 'message-b'), 'doc-export-message-b')
  assert.deepEqual([...saved.values.values()], [fresh])
})

for (const state of ['pending', 'running', 'uncertain', 'unknown', 'succeeded', 'failed']) {
  test(`${state} cannot rotate a request key or prepare another preview`, async () => {
    const saved = storage()
    await assert.rejects(renewDocumentPreviewKey(saved, 'owner', 'message', id, async () => ({state})))
    assert.equal(saved.values.size, 0)
  })
}

test('status outage and unavailable storage fail closed before preparing', async () => {
  const saved = storage()
  await assert.rejects(renewDocumentPreviewKey(saved, 'owner', 'message', id, async () => {throw new Error('offline')}))
  assert.equal(saved.values.size, 0)
  await assert.rejects(renewDocumentPreviewKey({getItem: () => null, setItem() {}}, 'owner', 'message', id, async () => ({state: 'expired'})))
  assert.throws(() => documentPreviewKey(saved, undefined, 'message'))
})

function approvalTree(state) {
  const source = readFileSync(new URL('./components/DocumentExportApproval.tsx', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}}).outputText
  const exports = {}
  const jsx = (type, props) => ({type, props})
  vm.runInNewContext(code, {exports, require(path) {
    if (path === 'react') return {useState: value => [value, () => {}], useRef: value => ({current: value})}
    if (path === 'react/jsx-runtime') return {jsx, jsxs: jsx}
    if (path.includes('react-components')) return {Button: 'Button'}
    return new Proxy({}, {get: (_obj, name) => String(name)})
  }})
  return exports.DocumentExportApproval({prepared: {operation_id: id, digest: 'a'.repeat(64), title: 'Dữ liệu giả lập', state}, onReprepare: async () => {}})
}
function buttons(tree, result = []) {
  if (!tree || typeof tree !== 'object') return result
  if (tree.type === 'Button') result.push(tree.props.children)
  for (const child of Object.values(tree.props ?? {})) {
    if (Array.isArray(child)) child.forEach(item => buttons(item, result))
    else buttons(child, result)
  }
  return result
}
test('actual approval component offers renewal only for expired, and fresh pending needs approval again', () => {
  assert.ok(buttons(approvalTree('expired')).includes('Tạo lại bản xem trước'))
  assert.ok(!buttons(approvalTree('expired')).includes('Xác nhận tạo Google Doc'))
  assert.ok(buttons(approvalTree('pending')).includes('Xác nhận tạo Google Doc'))
  for (const state of ['running', 'uncertain', 'unknown', 'succeeded', 'failed']) {
    assert.ok(!buttons(approvalTree(state)).includes('Tạo lại bản xem trước'))
  }
})
