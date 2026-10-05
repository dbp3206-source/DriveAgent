import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'
import * as labels from './executionTraceLabels.mjs'

const require = createRequire(import.meta.url)
const source = readFileSync(new URL('./components/ExecutionTrace.tsx', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText
const componentModule = { exports: {} }
new Function('require', 'module', 'exports', compiled)(
  (name) => name.endsWith('executionTraceLabels.mjs') ? labels : require(name),
  componentModule, componentModule.exports,
)
const { ExecutionTrace } = componentModule.exports

test('main assistant roles and tools have understandable Vietnamese labels', () => {
  assert.equal(labels.executionAgentLabel('user'), 'Bạn')
  for (const name of ['drive_coordinator', 'Coordinator', 'web_research_agent', 'email_agent',
    'company_info_agent', 'calendar_agent', 'report_generation_agent', 'memory_agent',
    'human_approval_agent', 'skill_agent']) {
    assert.notEqual(labels.executionAgentLabel(name), 'Trợ lý khác')
    assert.equal(labels.executionAgentLabel(name).includes('_'), false)
  }
  assert.equal(labels.executionToolLabel('local_source_search'), 'Tìm tài liệu đã tải lên')
  assert.equal(labels.executionToolLabel('local_source_read'), 'Đọc tài liệu đã tải lên')
  assert.equal(labels.executionToolLabel('docs_execute'), 'Tạo hoặc sửa tài liệu đã duyệt')
  assert.equal(labels.executionToolLabel('new_tool'), 'Công cụ khác')
})

test('known identifiers in step descriptions are translated without rewriting other content', () => {
  assert.equal(labels.executionTextLabel('memory_agent gọi local_source_search.'),
    'Trợ lý bộ nhớ gọi Tìm tài liệu đã tải lên.')
  assert.equal(labels.executionTextLabel('Giữ 15/10/2026 và 3.250 tỷ đồng.'),
    'Giữ 15/10/2026 và 3.250 tỷ đồng.')
  assert.equal(labels.executionModelLabel('gemini-2.5-flash'), 'Gemini 2.5 Flash')
})

test('model labels preserve Lite, standard, and preview variants without capability claims', () => {
  assert.equal(labels.executionModelLabel('gemini-3.5-flash-lite'), 'Gemini 3.5 Flash Lite')
  assert.equal(labels.executionModelLabel('gemini-3.8-flash'), 'Gemini 3.8 Flash')
  assert.equal(labels.executionModelLabel('gemini-2.5-pro'), 'Gemini 2.5 Pro')
  assert.equal(labels.executionModelLabel('gemini-2.5-flash-preview-05-20'), 'Gemini 2.5 Flash-preview-05-20')
})

test('registered indexing, saved-result, and personal-workflow tools have labels', () => {
  for (const name of ['rag_index_drive_file', 'rag_unindex_drive_file', 'rag_search',
    'artifact_list', 'artifact_save', 'skill_save', 'skill_run', 'skill_list', 'skill_archive']) {
    assert.notEqual(labels.executionToolLabel(name), 'Công cụ khác', name)
    assert.equal(labels.executionToolLabel(name).includes('_'), false, name)
  }
  assert.equal(labels.executionToolLabel('memory_delete'), 'Công cụ khác')
  assert.equal(labels.executionToolLabel('constructor'), 'Công cụ khác')
  assert.equal(labels.executionAgentLabel('toString'), 'Trợ lý khác')
  assert.equal(labels.executionTextLabel('constructor toString'), 'constructor toString')
})

test('rendered explanation hides internal names but preserves the exact technical trace', () => {
  const trace = [
    { stage: 'agent_selection', status: 'success', agent: 'memory_agent' },
    { stage: 'multi_agent', status: 'ready', coordinator: 'drive_coordinator', agents: ['web_research_agent'] },
    { stage: 'agent_handoff', status: 'success', from: 'Coordinator', to: 'memory_agent' },
    { stage: 'tool', status: 'success', tool: 'local_source_search' },
    { stage: 'usage', status: 'success', total_token_count: 14, model: 'gemini-2.5-flash' },
    { stage: 'future_internal_stage', status: 'future_status' },
  ]
  const before = JSON.stringify(trace)
  const html = renderToStaticMarkup(createElement(ExecutionTrace, { trace }))
  const visible = html.split('<summary>Dữ liệu kỹ thuật</summary>')[0]
  for (const rawName of ['agent_selection', 'Coordinator', 'memory_agent', 'web_research_agent',
    'local_source_search', 'future_internal_stage', 'future_status', 'Model thực dùng', 'Tổng token']) {
    // Status identifiers remain in CSS class names, not in visible text.
    assert.equal(visible.replace(/class="[^"]*"/g, '').includes(rawName), false, rawName)
  }
  assert.ok(visible.includes('Chọn trợ lý phụ trách'))
  assert.ok(visible.includes('Trợ lý bộ nhớ'))
  assert.ok(visible.includes('Tìm tài liệu đã tải lên'))
  assert.ok(visible.includes('Đơn vị văn bản đã xử lý: 14'))
  assert.ok(html.includes('local_source_search'))
  assert.equal(JSON.stringify(trace), before)
})
