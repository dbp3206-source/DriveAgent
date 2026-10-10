type MeasuredEvent = { status: string; latency_ms: number | null; tool_name: string }
export function summarizeAudit<T extends MeasuredEvent>(events: T[]): {
  completed: T[]
  latencyEvents: T[]
  successCount: number
  errorCount: number
  successPercent: number | null
  avgLatency: number | null
  p95: number | null
  toolStats: Record<string, { total: number; success: number; error: number; totalLat: number; latencyCount: number }>
}
