import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CAPACITY_HELP_TEXT,
  capacityPillLabel,
  effectiveCredentialLabel,
} from './providerCapacity.mjs'

const capacity = (overrides = {}) => ({
  credential_source: 'user',
  display_name: 'DriveAgent QA',
  failover_active: false,
  local_budget: {daily_remaining: 13, daily_limit: 16},
  ...overrides,
})

test('labels the effective credential as a snapshot without claiming it served a request', () => {
  assert.equal(effectiveCredentialLabel(capacity()), 'DriveAgent QA')
  assert.equal(effectiveCredentialLabel(capacity({failover_active: true})), 'DriveAgent QA · dự phòng')
  assert.equal(effectiveCredentialLabel(capacity({display_name: null, credential_source: 'environment'})), 'khóa môi trường')
  assert.equal(effectiveCredentialLabel(null), 'chưa có thông tin')
})

test('composer label names the effective key and calls the count model turns', () => {
  assert.equal(capacityPillLabel(capacity()), 'DriveAgent QA · 13/16 lượt mô hình')
  assert.equal(
    capacityPillLabel(capacity({failover_active: true, local_budget: {daily_remaining: 16, daily_limit: 16}})),
    'DriveAgent QA · dự phòng · 16/16 lượt mô hình',
  )
  assert.equal(capacityPillLabel({...capacity(), local_budget: null}), null)
})

test('help text distinguishes the local safety ledger from Google quota', () => {
  assert.match(CAPACITY_HELP_TEXT, /không phải số dư Google/)
  assert.match(CAPACITY_HELP_TEXT, /nhiều lượt mô hình/)
})
