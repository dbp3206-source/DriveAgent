import assert from 'node:assert/strict'
import test from 'node:test'

import {DEFAULT_CHAT_CONTROLS, displaySessionTitle, mergeChatControls} from './chatControls.ts'

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
