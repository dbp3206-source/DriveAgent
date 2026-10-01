import test from 'node:test'
import assert from 'node:assert/strict'
import {
  hasDriveReadScope,
  hasGmailReadScope,
  integrationFailureStatus,
  integrationFor,
} from './integrationStatus.mjs'

test('maps Drive and Gmail endpoint paths without query strings', () => {
  assert.equal(integrationFor('/api/drive/files?page_size=20'), 'drive')
  assert.equal(integrationFor('/api/gmail/threads/t-123?include=body'), 'gmail')
  assert.equal(integrationFor('/api/gmail'), 'gmail')
  assert.equal(integrationFor('/api/gmailish'), null)
  assert.equal(integrationFor('/api/health'), null)
})

test('requires real read scopes instead of any scope containing drive or gmail', () => {
  assert.equal(hasDriveReadScope(['https://www.googleapis.com/auth/drive.readonly']), true)
  assert.equal(hasDriveReadScope(['https://www.googleapis.com/auth/drive.file']), false)
  assert.equal(hasGmailReadScope(['https://www.googleapis.com/auth/gmail.send']), false)
  assert.equal(hasGmailReadScope(['https://www.googleapis.com/auth/gmail.modify']), true)
  assert.equal(hasGmailReadScope(undefined), false)
})

test('does not confuse app session and application RBAC errors with Google health', () => {
  assert.equal(integrationFailureStatus('drive', undefined, 401), null)
  assert.equal(integrationFailureStatus('gmail', 'access_denied', 403), null)
  assert.equal(integrationFailureStatus('drive', 'invalid_arguments', 400), null)
})

test('marks explicit Google token refresh and provider permission failures as degraded', () => {
  assert.equal(integrationFailureStatus('drive', 'google_connection_error', 503), 'degraded')
  assert.equal(integrationFailureStatus('gmail', 'google_connection_error', 503), 'degraded')
  assert.equal(integrationFailureStatus('drive', 'google_workspace_permission_denied', 403), 'permission')
})

test('classifies provider permissions, configuration, and availability separately', () => {
  assert.equal(integrationFailureStatus('gmail', 'gmail_insufficient_permissions', 403), 'permission')
  assert.equal(integrationFailureStatus('gmail', 'gmail_api_disabled', 403), 'misconfigured')
  assert.equal(integrationFailureStatus('gmail', 'gmail_error', 500), 'degraded')
  assert.equal(integrationFailureStatus('gmail', 'gmail_503', 503), 'degraded')
  assert.equal(integrationFailureStatus('gmail', 'gmail_429', 429), 'degraded')
  assert.equal(integrationFailureStatus('gmail', 'gmail_403', 403), null)
  assert.equal(integrationFailureStatus('drive', 'google_drive_503', 503), 'degraded')
  assert.equal(integrationFailureStatus('drive', 'google_drive_403', 403), 'permission')
  assert.equal(integrationFailureStatus('gmail', 'google_drive_503', 503), null)
  assert.equal(integrationFailureStatus('drive', 'gmail_error', 500), null)
})
