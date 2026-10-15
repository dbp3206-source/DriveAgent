import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { suggestedDocumentTitle, validatedDocumentTitle } from './documentTitle.mjs'

test('suggestion is only a short editable default, without markdown or invented date', () => {
  assert.equal(suggestedDocumentTitle('\n# **Đề xuất thử**\nNội dung'), 'Veridra: Đề xuất thử')
  assert.equal(suggestedDocumentTitle(''), 'Tài liệu Veridra')
  assert.ok(suggestedDocumentTitle('a'.repeat(500)).length <= 200)
})
test('explicit title is retained, including Vietnamese; invalid names never prepare', () => {
  assert.equal(validatedDocumentTitle('  Đề xuất thử cổng nội bộ  '), 'Đề xuất thử cổng nội bộ')
  for (const title of ['', '  ', 'a'.repeat(201), 'A\nB', 'A\tB', 'A\u0000B']) assert.throws(() => validatedDocumentTitle(title))
})

function titleDialog(props) {
  const source = readFileSync(new URL('./components/DocumentExportTitleDialog.tsx', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}}).outputText
  const exports = {}
  const jsx = (type, componentProps) => ({type, props: componentProps})
  vm.runInNewContext(code, {exports, require(path) {
    if (path === 'react/jsx-runtime') return {jsx, jsxs: jsx}
    return new Proxy({}, {get: (_obj, name) => String(name)})
  }})
  return exports.DocumentExportTitleDialog(props)
}
function find(tree, type) {
  if (!tree || typeof tree !== 'object') return []
  return [...(tree.type === type ? [tree] : []), ...Object.values(tree.props ?? {}).flatMap(value =>
    Array.isArray(value) ? value.flatMap(child => find(child, type)) : find(value, type))]
}
test('actual title dialog uses controlled name and explicit prepare, not approval', () => {
  const calls = []
  const tree = titleDialog({title: 'Tên đã chọn', busy: false, error: '', onTitleChange: value => calls.push(value), onCancel: () => calls.push('cancel'), onPrepare: () => calls.push('prepare')})
  const input = find(tree, 'Input')[0]
  assert.equal(input.props.value, 'Tên đã chọn')
  assert.equal(input.props.maxLength, 200)
  input.props.onChange(null, {value: 'Tên khác'})
  const actions = find(tree, 'Button')
  actions.find(button => button.props.children === 'Hủy').props.onClick()
  actions.find(button => button.props.children === 'Chuẩn bị bản xem trước').props.onClick()
  assert.deepEqual(calls, ['Tên khác', 'cancel', 'prepare'])
  assert.ok(!JSON.stringify(tree).includes('Xác nhận tạo Google Doc'))
})
test('empty name/busy state disable preparation and busy dialog cannot dismiss', () => {
  let cancelled = false
  const base = {title: '', busy: false, error: 'Lỗi kiểm', onTitleChange() {}, onCancel() {cancelled = true}, onPrepare() {}}
  assert.equal(find(titleDialog(base), 'Button').find(button => button.props.children === 'Chuẩn bị bản xem trước').props.disabled, true)
  const tree = titleDialog({...base, title: 'Tên', busy: true})
  assert.ok(find(tree, 'Button').every(button => button.props.disabled))
  tree.props.onOpenChange(null, {open: false})
  assert.equal(cancelled, false)
})
