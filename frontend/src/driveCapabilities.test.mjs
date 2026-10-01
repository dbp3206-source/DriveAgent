import assert from 'node:assert/strict'
import test from 'node:test'
import { driveFileCapability } from './driveCapabilities.mjs'

test('allows only document formats implemented by the Drive extraction pipeline', () => {
  assert.equal(driveFileCapability('application/pdf', 'report.pdf').readable, false)
  assert.equal(driveFileCapability('application/pdf', 'report.pdf').previewMode, 'none')
  assert.equal(driveFileCapability('application/vnd.google-apps.document', 'Plan').indexable, true)
  assert.equal(driveFileCapability('application/octet-stream', 'agent.ipynb').readable, false)
})

test('rejects video and opaque binary files before a user starts an unsupported action', () => {
  const video = driveFileCapability('video/mp4', 'lecture.mp4')
  assert.deepEqual(video, {
    readable: false,
    indexable: false,
    previewMode: 'none',
    reason: 'Định dạng này chưa được Veridra hỗ trợ lập chỉ mục.',
  })
  assert.equal(driveFileCapability('application/octet-stream', 'unknown.bin').readable, false)
})
