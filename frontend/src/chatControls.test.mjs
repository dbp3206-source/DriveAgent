import assert from 'node:assert/strict'
import test from 'node:test'

import {DEFAULT_CHAT_CONTROLS, displaySessionTitle, localChatLaunch, mergeChatControls, normalizeChatControls} from './chatControls.ts'

test('local-to-chat launch follows the current strict API contract', () => {
  const launch = localChatLaunch('tài liệu.md')
  assert.equal(launch.prompt, '/local tài liệu.md ')
  assert.deepEqual(launch.controls, {source: 'local', agent: 'research', output: 'chat', workflow: 'auto'})
})

test('old stored launch fields cannot leak into a new chat request', () => {
  assert.deepEqual(normalizeChatControls({domain: 'all', skill: 'general'}), DEFAULT_CHAT_CONTROLS)
  assert.deepEqual(normalizeChatControls({source: 'local', agent: 'research', output: 'invalid', workflow: 'invalid', domain: 'all'}),
    {source: 'local', agent: 'research', output: 'chat', workflow: 'auto'})
  assert.deepEqual(normalizeChatControls(null), DEFAULT_CHAT_CONTROLS)
})

test('legacy conversation titles hide only recognized leading slash commands', () => {
  assert.equal(
    displaySessionTitle('/rag /research Chỉ dùng tài liệu đã lập chỉ mục'),
    'Chỉ dùng tài liệu đã lập chỉ mục',
  )
  assert.equal(
    displaySessionTitle('/skill:qa-study /doc Tạo báo cáo tuần'),
    'Tạo báo cáo tuần',
  )
  assert.equal(displaySessionTitle('/unknown giữ nguyên'), '/unknown giữ nguyên')
  assert.equal(displaySessionTitle('Dùng /drive trong ví dụ'), 'Dùng /drive trong ví dụ')
})

test('saved skills compose as an ordered de-duplicated chain', () => {
  const first = mergeChatControls(DEFAULT_CHAT_CONTROLS, {skill_name: 'daily_news_brief'})
  const second = mergeChatControls(first, {skill_name: 'research_knowledge_brief'})
  const duplicate = mergeChatControls(second, {skill_name: 'daily_news_brief'})

  assert.equal(second.skill_name, 'daily_news_brief+research_knowledge_brief')
  assert.equal(duplicate.skill_name, second.skill_name)
})
