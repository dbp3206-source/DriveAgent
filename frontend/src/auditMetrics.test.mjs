import assert from 'node:assert/strict'
import test from 'node:test'
import { summarizeAudit } from './auditMetrics.mjs'

const event = (status, latency_ms, tool_name = 'read') => ({ status, latency_ms, tool_name })

test('success counts retain completed events with missing timings; pending events are excluded', () => {
  const events = [
    ...Array.from({ length: 82 }, () => event('success', 100)),
    event('success', null), event('success', null),
    ...Array.from({ length: 14 }, () => event('error', 300)),
    event('started', null), event('started', 50),
  ]
  const result = summarizeAudit(events)
  assert.equal(result.completed.length, 98)
  assert.equal(result.successCount, 84)
  assert.equal(result.errorCount, 14)
  assert.equal(result.successPercent, 86)
  assert.equal(result.latencyEvents.length, 96)
  assert.equal(result.toolStats.read.total, 98)
  assert.equal(result.toolStats.read.success, 84)
  assert.equal(result.toolStats.read.latencyCount, 96)
})

test('unknown timings are not zero, while a measured zero is valid', () => {
  const result = summarizeAudit([
    event('success', null), event('success', Number.NaN),
    event('error', -1), event('denied', Infinity), event('success', 0),
  ])
  assert.equal(result.completed.length, 5)
  assert.equal(result.successPercent, 60)
  assert.equal(result.latencyEvents.length, 1)
  assert.equal(result.avgLatency, 0)
  assert.equal(result.p95, 0)
  assert.equal(result.toolStats.read.latencyCount, 1)
})

test('no completed events means no score or duration', () => {
  for (const events of [[], [event('started', 20)]]) {
    const result = summarizeAudit(events)
    assert.equal(result.successPercent, null)
    assert.equal(result.avgLatency, null)
    assert.equal(result.p95, null)
    assert.deepEqual(result.toolStats, {})
  }
})
