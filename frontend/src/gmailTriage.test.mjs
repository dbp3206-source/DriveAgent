import assert from 'node:assert/strict'
import test from 'node:test'
import {classifyReplyNeed} from './gmailTriage.mjs'

test('newsletter and no-reply mail never becomes a reply task', () => {
  assert.equal(classifyReplyNeed({sender: 'ByteByteGo Newsletter <no-reply@example.com>', subject: 'Weekly digest'}).needsReply, false)
  assert.equal(classifyReplyNeed({sender: 'ByteByteGo <bytebytego@substack.com>', subject: 'Why does Git revert cause conflicts?'}).needsReply, false)
  assert.equal(classifyReplyNeed({sender: 'Morning Brew <crew@morningbrew.com>', subject: 'Can AI agents work?'}).needsReply, false)
  assert.equal(classifyReplyNeed({sender: 'Team', snippet: 'Hủy đăng ký bản tin tại đây'}).needsReply, false)
})

test('personal mail with an explicit question or action is a reply task', () => {
  const result = classifyReplyNeed({
    sender: 'Lan <lan@example.com>',
    subject: 'Bạn có thể xác nhận lịch họp?',
    snippet: 'Vui lòng phản hồi trước thứ Sáu.',
  })
  assert.equal(result.needsReply, true)
  assert.match(result.reason, /yêu cầu hành động/)
})

test('ambiguous inbox mail is not overclaimed as needing a reply', () => {
  assert.equal(classifyReplyNeed({sender: 'Lan', subject: 'Tài liệu tham khảo'}).needsReply, false)
})
