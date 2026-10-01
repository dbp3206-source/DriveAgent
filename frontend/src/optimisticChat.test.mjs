import assert from 'node:assert/strict'
import test from 'node:test'

import {removeMessageById} from './optimisticChat.mjs'

test('failed optimistic bubble is removed before a retry appends the prompt again', () => {
  const messages = [
    {id: 'persisted-user', content: 'Câu hỏi cũ'},
    {id: 'local-failed', content: 'Câu hỏi cần thử lại'},
  ]

  assert.deepEqual(removeMessageById(messages, 'local-failed'), [messages[0]])
})

test('removing an unknown optimistic id leaves existing history intact', () => {
  const messages = [{id: 'persisted', content: 'Không được xóa'}]

  assert.deepEqual(removeMessageById(messages, 'missing'), messages)
})
