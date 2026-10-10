// Success counts use completed events, regardless of whether latency was recorded.
// Timing statistics use only completed events with an actual, valid duration.
export function summarizeAudit(events) {
  const completed = events.filter(event => event.status !== 'started')
  const latencyEvents = completed.filter(event => typeof event.latency_ms === 'number'
    && Number.isFinite(event.latency_ms) && event.latency_ms >= 0)
  const successCount = completed.filter(event => event.status === 'success').length
  const latencies = latencyEvents.map(event => event.latency_ms).sort((a, b) => a - b)
  const toolStats = {}
  for (const event of completed) {
    const stats = toolStats[event.tool_name] ??= { total: 0, success: 0, error: 0, totalLat: 0, latencyCount: 0 }
    stats.total++
    if (event.status === 'success') stats.success++
    else stats.error++
    if (typeof event.latency_ms === 'number' && Number.isFinite(event.latency_ms) && event.latency_ms >= 0) {
      stats.totalLat += event.latency_ms
      stats.latencyCount++
    }
  }
  return {
    completed,
    latencyEvents,
    successCount,
    errorCount: completed.length - successCount,
    successPercent: completed.length ? Math.round(successCount / completed.length * 100) : null,
    avgLatency: latencies.length ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length) : null,
    p95: latencies.length ? latencies[Math.ceil(latencies.length * 0.95) - 1] : null,
    toolStats,
  }
}
