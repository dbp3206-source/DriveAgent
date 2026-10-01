import assert from 'node:assert/strict'
import test from 'node:test'
import {buildGmailQuery, filterLabel} from './gmailQuery.mjs'

test('query builder keeps status, time, scope and attachment filters explicit', () => {
  assert.equal(
    buildGmailQuery({status: 'unread', period: '3d', scope: 'inbox', attachments: true}),
    'in:inbox is:unread newer_than:3d has:attachment',
  )
  assert.equal(
    buildGmailQuery({status: 'read', period: 'all', scope: 'everywhere', userQuery: 'from:protonx'}),
    'is:read from:protonx',
  )
})

test('filter label gives a concise, human-readable description', () => {
  assert.equal(filterLabel({status: 'read', period: '7d', scope: 'inbox'}), 'Hộp thư đến · Đã đọc · 1 tuần')
})
