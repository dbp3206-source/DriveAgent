import assert from 'node:assert/strict'
import test from 'node:test'
import {emailActionConfig, roleCanCreateDraft, roleCanSendEmail} from './emailWorkflow.mjs'

test('draft workflow never routes to a send endpoint', () => {
  const config = emailActionConfig('draft')
  assert.equal(config.prepareEndpoint, '/api/gmail/draft')
  assert.equal(config.approveEndpoint, '/api/gmail/draft/approve')
  assert.match(config.successLabel, /Chưa có email nào được gửi/)
})

test('send workflow remains an explicit separate action', () => {
  const config = emailActionConfig('send')
  assert.equal(config.prepareEndpoint, '/api/gmail/prepare')
  assert.equal(config.approveEndpoint, '/api/gmail/approve')
  assert.match(config.actionLabel, /Xác nhận gửi/)
})

test('unknown runtime values fail safe to the draft workflow', () => {
  const config = emailActionConfig('unexpected')
  assert.equal(config.approveEndpoint, '/api/gmail/draft/approve')
})

test('Gmail write actions mirror application RBAC', () => {
  assert.equal(roleCanCreateDraft('viewer'), false)
  assert.equal(roleCanCreateDraft('editor'), true)
  assert.equal(roleCanCreateDraft('owner'), true)
  assert.equal(roleCanSendEmail('editor'), false)
  assert.equal(roleCanSendEmail('owner'), true)
  assert.equal(roleCanSendEmail('super_admin'), true)
})
