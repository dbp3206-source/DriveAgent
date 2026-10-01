import {
  Badge,
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Dropdown,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components'
import { ArrowDownload24Regular, ArrowSync24Regular } from '@fluentui/react-icons'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, formatDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { HarnessOverviewData } from '../harnessScenarios'
import type { AuditEvent } from '../types'
import { ReleaseReadiness } from '../components/ReleaseReadiness'

type AuditPagePayload = {
  items: AuditEvent[]
  next_cursor: string | null
}

const statusLabel: Record<string, string> = {
  started: 'Đang chạy',
  success: 'Thành công',
  warning: 'Cảnh báo',
  error: 'Lỗi',
  denied: 'Bị từ chối',
}

function DonutPieChart({
  successCount,
  errorCount,
  size = 140,
}: {
  successCount: number
  errorCount: number
  size?: number
}) {
  const total = successCount + errorCount
  const successPct = total > 0 ? Math.round((successCount / total) * 100) : null
  const radius = 46
  const strokeWidth = 14
  const circumference = 2 * Math.PI * radius
  const successStroke = total > 0 ? (successCount / total) * circumference : 0
  const errorStroke = total > 0 ? (errorCount / total) * circumference : 0

  return (
    <div className="donut-pie-container">
      <svg width={size} height={size} viewBox="0 0 120 120" className="donut-pie-svg">
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
          opacity="0.3"
        />
        <g transform="rotate(-90 60 60)">
          {/* Success Arc */}
          <circle
            cx="60"
            cy="60"
            r={radius}
            fill="none"
            stroke="#10b981"
            strokeWidth={strokeWidth}
            strokeDasharray={`${successStroke} ${circumference}`}
            strokeDashoffset={0}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.5s ease' }}
          />
          {/* Error Arc */}
          {errorCount > 0 && (
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#ef4444"
              strokeWidth={strokeWidth}
              strokeDasharray={`${errorStroke} ${circumference}`}
              strokeDashoffset={-successStroke}
              strokeLinecap="round"
              style={{ transition: 'stroke-dasharray 0.5s ease' }}
            />
          )}
        </g>
        <text x="60" y="54" textAnchor="middle" dominantBaseline="middle" className="donut-center-pct">
          {successPct == null ? 'N/A' : `${successPct}%`}
        </text>
        <text x="60" y="71" textAnchor="middle" dominantBaseline="middle" className="donut-center-label">
          Thành công
        </text>
      </svg>
      <div className="donut-legend">
        <div className="donut-legend-item">
          <span className="d-dot d-dot--success" />
          <span>Thành công: <strong>{successCount}</strong> ({successPct == null ? 'N/A' : `${successPct}%`})</span>
        </div>
        <div className="donut-legend-item">
          <span className="d-dot d-dot--error" />
          <span>Lỗi / Từ chối: <strong>{errorCount}</strong> ({total > 0 ? `${100 - (successPct ?? 0)}%` : 'N/A'})</span>
        </div>
      </div>
    </div>
  )
}

function AuditPerformanceChart({ events, p95 }: { events: AuditEvent[]; p95: number | null }) {
  const [chartMode, setChartMode] = useState<'line' | 'bar' | 'pie'>('line')
  const [hoveredPoint, setHoveredPoint] = useState<{
    tool: string
    latency: number
    status: string
    index: number
    x: number
    y: number
  } | null>(null)

  const validEvents = events
    .filter((e) => e.status !== 'started' && e.latency_ms !== null && Number.isFinite(e.latency_ms) && e.latency_ms >= 0)
    .slice(0, 24)
    .reverse()

  const toolStats = events.reduce<Record<string, { total: number; success: number; error: number; totalLat: number }>>(
    (acc, ev) => {
      const name = ev.tool_name
      if (!acc[name]) acc[name] = { total: 0, success: 0, error: 0, totalLat: 0 }
      acc[name].total += 1
      if (ev.status === 'success') acc[name].success += 1
      else acc[name].error += 1
      if (ev.latency_ms && Number.isFinite(ev.latency_ms)) acc[name].totalLat += ev.latency_ms
      return acc
    },
    {}
  )
  const sortedTools = Object.entries(toolStats)
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 8)

  const totalSuccess = events.filter((e) => e.status === 'success').length
  const totalError = events.filter((e) => e.status === 'error' || e.status === 'denied').length

  const svgWidth = 540
  const svgHeight = 200
  const padLeft = 48
  const padRight = 20
  const padTop = 20
  const padBottom = 26
  const chartW = svgWidth - padLeft - padRight
  const chartH = svgHeight - padTop - padBottom

  const latencies = validEvents.map((e) => e.latency_ms ?? 0)
  const maxLat = Math.max(...latencies, p95 ?? 100, 100)
  const stepX = validEvents.length > 1 ? chartW / (validEvents.length - 1) : chartW / 2

  const points = validEvents.map((ev, i) => {
    const lat = ev.latency_ms ?? 0
    const x = padLeft + i * stepX
    const y = padTop + chartH - (lat / maxLat) * chartH
    return { x, y, lat, tool: ev.tool_name, status: ev.status, index: i }
  })

  const linePath = points.reduce(
    (acc, pt, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)},${pt.y.toFixed(1)}`,
    ''
  )
  const firstPt = points[0]
  const lastPt = points[points.length - 1]
  const areaPath =
    firstPt && lastPt
      ? `${linePath} L ${lastPt.x.toFixed(1)},${(padTop + chartH).toFixed(1)} L ${firstPt.x.toFixed(1)},${(padTop + chartH).toFixed(1)} Z`
      : ''

  const p95Y = p95 !== null ? padTop + chartH - (p95 / maxLat) * chartH : null

  return (
    <div className="audit-chart-card">
      <div className="audit-chart-header">
        <div>
          <h4 className="audit-chart-title">Trực quan hóa hoạt động, tỷ lệ & độ trễ</h4>
          <p className="audit-chart-subtitle">
            {chartMode === 'line'
              ? `Xu hướng độ trễ qua ${validEvents.length} lượt gọi gần nhất kèm biểu đồ tròn tỷ lệ thành công`
              : chartMode === 'bar'
              ? `Đánh giá từng công cụ: thanh xanh (Thành công) và thanh đỏ (Lỗi / Từ chối)`
              : `Tổng quan phân bổ kết quả thực thi công cụ toàn hệ thống`}
          </p>
        </div>
        <div className="audit-chart-toggle">
          <Button
            size="small"
            appearance={chartMode === 'line' ? 'primary' : 'subtle'}
            onClick={() => setChartMode('line')}
          >
            Xu hướng & Tỷ lệ (Line + Pie)
          </Button>
          <Button
            size="small"
            appearance={chartMode === 'bar' ? 'primary' : 'subtle'}
            onClick={() => setChartMode('bar')}
          >
            Theo công cụ (Bar Xanh/Đỏ)
          </Button>
        </div>
      </div>

      {chartMode === 'line' && (
        <div className="audit-line-pie-row">
          {validEvents.length === 0 ? (
            <p className="audit-chart-empty">Chưa có đủ dữ liệu độ trễ để dựng biểu đồ đường.</p>
          ) : (
            <div className="audit-svg-wrapper">
              <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="audit-chart-svg"
                onMouseLeave={() => setHoveredPoint(null)}
              >
                <defs>
                  <linearGradient id="latencyAreaGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.45" />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                <line x1={padLeft} y1={padTop} x2={svgWidth - padRight} y2={padTop} stroke="var(--border)" strokeDasharray="3 3" opacity="0.6" />
                <line x1={padLeft} y1={padTop + chartH / 2} x2={svgWidth - padRight} y2={padTop + chartH / 2} stroke="var(--border)" strokeDasharray="3 3" opacity="0.6" />
                <line x1={padLeft} y1={padTop + chartH} x2={svgWidth - padRight} y2={padTop + chartH} stroke="var(--border)" />

                <text x={padLeft - 8} y={padTop + 4} textAnchor="end" className="chart-axis-text">
                  {(maxLat / 1000).toFixed(1)}s
                </text>
                <text x={padLeft - 8} y={padTop + chartH / 2 + 4} textAnchor="end" className="chart-axis-text">
                  {(maxLat / 2000).toFixed(1)}s
                </text>
                <text x={padLeft - 8} y={padTop + chartH + 4} textAnchor="end" className="chart-axis-text">
                  0s
                </text>

                {p95Y !== null && p95Y >= padTop && p95Y <= padTop + chartH ? (
                  <g>
                    <line
                      x1={padLeft}
                      y1={p95Y}
                      x2={svgWidth - padRight}
                      y2={p95Y}
                      stroke="#f59e0b"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                    />
                    <text x={svgWidth - padRight} y={p95Y - 4} textAnchor="end" fill="#f59e0b" fontSize="10" fontWeight="600">
                      P95: {p95 != null ? (p95 / 1000).toFixed(2) : '-'}s
                    </text>
                  </g>
                ) : null}

                <path d={areaPath} fill="url(#latencyAreaGradient)" />
                <path d={linePath} fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {points.map((pt) => {
                  const isHovered = hoveredPoint?.index === pt.index
                  return (
                    <circle
                      key={pt.index}
                      cx={pt.x}
                      cy={pt.y}
                      r={isHovered ? 6 : 4}
                      fill={pt.status === 'success' ? '#10b981' : '#ef4444'}
                      stroke="var(--surface-raised)"
                      strokeWidth="2"
                      style={{ cursor: 'pointer', transition: 'r 0.15s ease' }}
                      onMouseEnter={() =>
                        setHoveredPoint({
                          tool: pt.tool,
                          latency: pt.lat,
                          status: pt.status,
                          index: pt.index,
                          x: pt.x,
                          y: pt.y,
                        })
                      }
                    />
                  )
                })}

                {hoveredPoint ? (
                  <g transform={`translate(${Math.min(hoveredPoint.x, svgWidth - 140)}, ${Math.max(hoveredPoint.y - 45, 8)})`}>
                    <rect width="136" height="38" rx="6" fill="var(--surface-raised)" stroke="var(--border-strong)" filter="drop-shadow(0 2px 8px rgba(0,0,0,0.3))" />
                    <text x="8" y="16" fontSize="11" fontWeight="600" fill="var(--text)">
                      {hoveredPoint.tool}
                    </text>
                    <text x="8" y="30" fontSize="10" fill={hoveredPoint.status === 'success' ? '#10b981' : '#ef4444'}>
                      {(hoveredPoint.latency / 1000).toFixed(2)}s • {hoveredPoint.status === 'success' ? 'Thành công' : 'Lỗi'}
                    </text>
                  </g>
                ) : null}
              </svg>
              <div className="chart-legend">
                <span className="legend-item"><span className="legend-dot legend-dot--success" /> Thành công</span>
                <span className="legend-item"><span className="legend-dot legend-dot--error" /> Lỗi / Từ chối</span>
                <span className="legend-item"><span className="legend-dash legend-dash--p95" /> Ngưỡng P95</span>
              </div>
            </div>
          )}

          {/* Integrated Pie Chart */}
          <div className="audit-side-pie">
            <span className="side-pie-title">Tỷ lệ Thành công / Lỗi</span>
            <DonutPieChart successCount={totalSuccess} errorCount={totalError} size={150} />
          </div>
        </div>
      )}

      {chartMode === 'bar' && (
        <div className="audit-bar-chart-list">
          <div className="bar-chart-legend-top">
            <span className="legend-item"><span className="legend-box legend-box--success" /> Xanh: Lượt Thành công</span>
            <span className="legend-item"><span className="legend-box legend-box--error" /> Đỏ: Lỗi / Từ chối</span>
          </div>
          {sortedTools.map(([toolName, stats]) => {
            const successPct = Math.round((stats.success / stats.total) * 100)
            const errorPct = 100 - successPct
            const avgLatSec = (stats.totalLat / stats.total / 1000).toFixed(2)
            const firstTool = sortedTools[0]
            const maxToolCount = (firstTool ? firstTool[1].total : 1) || 1
            const widthPct = Math.round((stats.total / maxToolCount) * 100)

            return (
              <div key={toolName} className="bar-tool-row-v2">
                <div className="bar-tool-info">
                  <code className="bar-tool-name">{toolName}</code>
                  <span className="bar-tool-meta">
                    <strong>{stats.total}</strong> lượt · {successPct}% thành công · TB: {avgLatSec}s
                  </span>
                </div>
                <div className="bar-track-dual">
                  <div
                    className="bar-segment-success"
                    style={{ width: `${(widthPct * successPct) / 100}%` }}
                    title={`Thành công: ${stats.success} lượt (${successPct}%)`}
                  >
                    {stats.success > 0 && <span className="bar-inner-label">{stats.success}</span>}
                  </div>
                  {stats.error > 0 && (
                    <div
                      className="bar-segment-error"
                      style={{ width: `${(widthPct * errorPct) / 100}%` }}
                      title={`Lỗi / Từ chối: ${stats.error} lượt (${errorPct}%)`}
                    >
                      <span className="bar-inner-label">{stats.error}</span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('all')
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selected, setSelected] = useState<AuditEvent | null>(null)
  const [nowTs, setNowTs] = useState(0)
  const [benchmark, setBenchmark] = useState<HarnessOverviewData | null>(null)
  const [evaluationJob, setEvaluationJob] = useState<{id: string; status: string; checkpoint: Record<string, {passed: number; total: number}>} | null>(null)
  const [evaluationStarting, setEvaluationStarting] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    api<{items: Array<{id: string; status: string; checkpoint: Record<string, {passed: number; total: number}>}>}>('/api/evaluation-jobs', {signal: controller.signal})
      .then(data => {
        const latest = data.items[0]
        if (!controller.signal.aborted && latest) {
          setEvaluationJob(current => current ?? latest)
        }
      })
      .catch(() => { /* Other audit data remains usable if the worker is unavailable. */ })
    return () => controller.abort()
  }, [])

  async function startEvaluation() {
    setEvaluationStarting(true)
    try {
      const job = await api<{job_id: string; status: string}>('/api/evaluation-jobs', {method: 'POST'})
      setEvaluationJob({id: job.job_id, status: job.status, checkpoint: {}})
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tạo được lượt đánh giá.')
    } finally {
      setEvaluationStarting(false)
    }
  }

  useEffect(() => {
    if (!evaluationJob || !['queued', 'running'].includes(evaluationJob.status)) return
    const controller = new AbortController()
    let pending = false
    const poll = window.setInterval(() => {
      if (pending) return
      pending = true
      api<{id: string; status: string; checkpoint: Record<string, {passed: number; total: number}>}>(`/api/evaluation-jobs/${evaluationJob.id}`, {signal: controller.signal})
        .then(job => {
          if (!controller.signal.aborted) {
            setEvaluationJob(current => current?.id === job.id ? job : current)
          }
        })
        .catch(() => { /* Job continues in the worker even when polling fails. */ })
        .finally(() => { pending = false })
    }, 2000)
    return () => { clearInterval(poll); controller.abort() }
  }, [evaluationJob])
  const requestRef = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    try {
      const query = status === 'all' ? '' : `?status=${encodeURIComponent(status)}`
      const [data, benchmarkResult] = await Promise.all([
        api<AuditPagePayload>(`/api/audit/page${query}`, { signal: controller.signal }),
        api<HarnessOverviewData>('/api/harness/overview', { signal: controller.signal }).catch(() => null),
      ])
      setEvents(data.items)
      setNextCursor(data.next_cursor)
      setBenchmark(benchmarkResult)
      setNowTs(Date.now())
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      setError(caught instanceof Error ? caught.message : 'Không tải được nhật ký audit.')
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => {
    void load()
    return () => requestRef.current?.abort()
  }, [load])

  async function loadMore() {
    if (!nextCursor || loading) return
    setLoading(true)
    try {
      const query = new URLSearchParams()
      if (status !== 'all') query.set('status', status)
      query.set('cursor', nextCursor)
      const data = await api<AuditPagePayload>(`/api/audit/page?${query.toString()}`)
      setEvents((current) => [...current, ...data.items])
      setNextCursor(data.next_cursor)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải thêm được nhật ký.')
    } finally {
      setLoading(false)
    }
  }

  const completed = useMemo(
    () => events.filter((e) => e.status !== 'started' && e.latency_ms !== null && Number.isFinite(e.latency_ms) && e.latency_ms >= 0),
    [events]
  )
  const avgLatency = useMemo(
    () => completed.length ? Math.round(completed.reduce((sum, e) => sum + (e.latency_ms ?? 0), 0) / completed.length) : null,
    [completed]
  )
  const p95: number | null = useMemo(() => {
    if (!completed.length) return null
    const sorted = [...completed].map((e) => e.latency_ms ?? 0).sort((a, b) => a - b)
    const val = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))]
    return val !== undefined ? val : null
  }, [completed])

  const successCount = useMemo(() => events.filter((e) => e.status === 'success').length, [events])

  const benchmarkRows = useMemo(() => {
    const evaluation = benchmark?.evaluation
    const asScore = (rate?: number | null) => rate == null || !Number.isFinite(rate)
      ? null
      : Math.max(0, Math.min(10, (rate <= 1 ? rate * 10 : rate / 10)))
    return [
      {
        criterion: 'Định tuyến tác vụ',
        metric: evaluation?.routing_regression?.pass_rate == null ? 'Chưa đo' : `${Math.round(evaluation.routing_regression.pass_rate * 100)}%`,
        sample: `${evaluation?.routing_regression?.passed ?? 0}/${evaluation?.routing_regression?.total ?? 0} ca hồi quy`,
        score: asScore(evaluation?.routing_regression?.pass_rate),
        scope: 'Golden routing offline; không đo độ đúng của câu trả lời.',
        required: true,
      },
      {
        criterion: 'Hợp đồng đầu ra',
        metric: evaluation?.answer_contract_benchmark?.pass_rate == null ? 'Chưa đo' : `${Math.round(evaluation.answer_contract_benchmark.pass_rate * 100)}%`,
        sample: `${evaluation?.answer_contract_benchmark?.passed ?? 0}/${evaluation?.answer_contract_benchmark?.total ?? 0} ca xác định`,
        score: asScore(evaluation?.answer_contract_benchmark?.pass_rate),
        scope: 'Kiểm tra định dạng và constraint trên mẫu cố định, không phải benchmark model live.',
        required: true,
      },
      {
        criterion: 'Chất lượng output gần đây',
        metric: evaluation?.recent_output_quality?.average_score == null ? 'Chưa đo' : `${evaluation.recent_output_quality.average_score}/100`,
        sample: `${evaluation?.recent_output_quality?.measured ?? 0} câu trả lời`,
        score: evaluation?.recent_output_quality?.average_score == null ? null : evaluation.recent_output_quality.average_score / 10,
        scope: evaluation?.recent_output_quality?.scope ?? 'Chưa có mô tả phạm vi.',
        required: true,
      },
      {
        criterion: 'Độ tin cậy tool',
        metric: evaluation?.tool_success_rate == null ? 'Chưa đo' : `${(evaluation.tool_success_rate * 100).toFixed(1)}%`,
        sample: `${evaluation?.audit_sample_size ?? 0} sự kiện audit`,
        score: asScore(evaluation?.tool_success_rate),
        scope: 'Tool trả thành công; không tự chứng minh mục tiêu nghiệp vụ đã đạt.',
        required: true,
      },
      {
        criterion: 'Liên kết citation',
        metric: evaluation?.quality_audit?.grounded_citation_rate == null ? 'Chưa đo' : `${(evaluation.quality_audit.grounded_citation_rate * 100).toFixed(1)}%`,
        sample: `${evaluation?.quality_audit?.grounded_responses ?? 0} câu có citation`,
        score: asScore(evaluation?.quality_audit?.grounded_citation_rate),
        scope: 'Kiểm marker và metadata; chưa kiểm entailment ngữ nghĩa của từng claim.',
        required: true,
      },
      {
        criterion: 'Chống mutation / guardrail',
        metric: evaluation?.adversarial_mutation_regression?.pass_rate == null ? 'Chưa đo' : `${Math.round(evaluation.adversarial_mutation_regression.pass_rate * 100)}%`,
        sample: `${evaluation?.adversarial_mutation_regression?.passed ?? 0}/${evaluation?.adversarial_mutation_regression?.total ?? 0} ca`,
        score: asScore(evaluation?.adversarial_mutation_regression?.pass_rate),
        scope: 'Regression xác định cho evaluator, không thay thế pentest độc lập.',
        required: true,
      },
      {
        criterion: 'Benchmark nghiệp vụ có oracle',
        metric: evaluation?.automated_business_benchmark?.pass_rate == null ? 'N/A' : `${(evaluation.automated_business_benchmark.pass_rate * 100).toFixed(1)}%`,
        sample: evaluation?.automated_business_benchmark?.sample_size ? `${evaluation.automated_business_benchmark.sample_size} tác vụ giả lập` : 'Chưa có bộ oracle đã xuất bản',
        score: asScore(evaluation?.automated_business_benchmark?.pass_rate),
        scope: evaluation?.automated_business_benchmark?.scope ?? 'Hardgate: execution success không được dùng thay thế oracle.',
        required: true,
      },
    ]
  }, [benchmark])

  const benchmarkVerdict = useMemo(() => {
    const required = benchmarkRows.filter((row) => row.required)
    if (!required.length || required.some((row) => row.score == null)) {
      return { score: null as number | null, label: 'Chưa đủ bằng chứng - giữ phát hành', tone: 'hold' }
    }
    const score = required.reduce((sum, row) => sum + (row.score ?? 0), 0) / required.length
    return { score, label: 'Trung bình các bộ đo bên dưới — không phải quyết định phát hành', tone: 'hold' }
  }, [benchmarkRows])

  // Usage Velocity (Day / Week) computed honestly from events
  const { callsToday, callsThisWeek } = useMemo(() => {
    const refTime = nowTs || (events[0] ? new Date(events[0].created_at).getTime() : 0)
    const oneDayAgo = refTime - 24 * 60 * 60 * 1000
    const oneWeekAgo = refTime - 7 * 24 * 60 * 60 * 1000
    let day = 0
    let week = 0
    for (const ev of events) {
      const t = new Date(ev.created_at).getTime()
      if (t >= oneDayAgo) day++
      if (t >= oneWeekAgo) week++
    }
    return { callsToday: day, callsThisWeek: week }
  }, [events, nowTs])

  // Sensitive actions / HiTL control
  const { sensitiveCount, sensitivePct } = useMemo(() => {
    const sensitiveNames = [
      'gmail_send',
      'gmail_draft_create',
      'docs_create',
      'docs_edit',
      'sheets_create',
      'sheets_edit',
      'drive_delete',
    ]
    const sensitive = events.filter((e) => sensitiveNames.some((n) => e.tool_name.includes(n)))
    const pct = events.length ? Math.round((sensitive.length / events.length) * 100) : 0
    return { sensitiveCount: sensitive.length, sensitivePct: pct }
  }, [events])

  const domainCounts = useMemo(() => {
    return events.reduce<Record<string, number>>((acc, ev) => {
      const domain = ev.tool_name.startsWith('drive_')
        ? 'Google Drive'
        : ev.tool_name.startsWith('docs_')
        ? 'Google Docs'
        : ev.tool_name.startsWith('sheets_')
        ? 'Google Sheets'
        : ev.tool_name.startsWith('gmail_')
        ? 'Gmail'
        : ev.tool_name.startsWith('local_')
        ? 'Tài liệu Local'
        : 'Hệ thống'
      acc[domain] = (acc[domain] || 0) + 1
      return acc
    }, {})
  }, [events])

  const dominantDomain = useMemo(() => {
    const sorted = Object.entries(domainCounts).sort((a, b) => b[1] - a[1])
    return sorted[0]?.[0] ?? 'Google Workspace'
  }, [domainCounts])

  function download(format: 'json' | 'csv') {
    const content = format === 'json'
      ? JSON.stringify(events, null, 2)
      : [
          ['created_at', 'tool', 'status', 'latency_ms', 'request_id', 'user_email'],
          ...events.map((event) => [
            event.created_at,
            event.tool_name,
            event.status,
            event.latency_ms ?? '',
            event.request_id,
            event.user_email ?? '',
          ]),
        ].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n')
    const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `drive-agent-audit-${new Date().toISOString().slice(0, 10)}.${format}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="stack-page audit-page-v2">
      <div className="page-heading">
        <div>
          <div className="page-heading-kicker-row">
            <span className="home-kicker">Security & Telemetry Audit</span>
            <Badge appearance="filled" color="brand">6-Gate Audit Trail</Badge>
          </div>
          <h2 className="artistic-page-title">Mọi tool call đều để lại dấu vết</h2>
          <p>
            Kiểm tra chi tiết từng công cụ, trạng thái thực thi và độ trễ chính xác. Hệ thống tự động che thông tin xác thực đã nhận diện trước khi ghi audit.
          </p>
        </div>
        <div className="page-heading__actions">
          <Button appearance="subtle" icon={<ArrowDownload24Regular />} disabled={!events.length} onClick={() => download('csv')}>Xuất CSV</Button>
          <Button appearance="subtle" icon={<ArrowDownload24Regular />} disabled={!events.length} onClick={() => download('json')}>Xuất JSON</Button>
          <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={load}>Làm mới</Button>
        </div>
      </div>

      <div className="filter-row">
        <Dropdown
          aria-label="Lọc theo trạng thái"
          value={status === 'all' ? 'Tất cả trạng thái' : statusLabel[status]}
          selectedOptions={[status]}
          onOptionSelect={(_, data) => setStatus(data.optionValue ?? 'all')}
        >
          <Option value="all" text="Tất cả trạng thái">Tất cả trạng thái</Option>
          <Option value="success" text="Thành công">Thành công</Option>
          <Option value="error" text="Lỗi">Lỗi</Option>
          <Option value="denied" text="Bị từ chối">Bị từ chối</Option>
          <Option value="started" text="Đang chạy">Đang chạy</Option>
        </Dropdown>
      </div>

      {!loading && !error && events.length > 0 ? (
        <section className="audit-measurements" aria-label="Đo lường tập nhật ký hiện tại">
          <div className="measurement-heading">
            <h3>Hiệu quả thực thi công cụ</h3>
            <ul className="audit-measurement-context">
              <li><strong>Mẫu đo:</strong> {events.length} sự kiện gần nhất đã tải.</li>
              <li><strong>Thiếu dữ liệu:</strong> hiển thị N/A, không tự quy thành 0%.</li>
            </ul>
          </div>

          <div className="kpi-cards-grid kpi-cards-grid--5">
            {/* KPI 1: Latency in Seconds */}
            <div className="kpi-card">
              <span className="kpi-label">Thời gian đợi trung bình</span>
              <span className="kpi-value kpi-value--highlight">
                {avgLatency === null ? 'Chưa có' : `${(avgLatency / 1000).toFixed(2)} s`}
              </span>
              <span className="kpi-subtext">Độ trễ P95: {p95 === null ? '-' : `${(p95 / 1000).toFixed(2)} s`}</span>
            </div>

            {/* KPI 2: Usage velocity per Day / Week */}
            <div className="kpi-card kpi-card--success">
              <span className="kpi-label">Tần suất sử dụng</span>
              <span className="kpi-value">
                {callsToday} <small style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>lượt / 24h</small>
              </span>
              <span className="kpi-subtext">{callsThisWeek} lượt trong 7 ngày qua</span>
            </div>

            {/* KPI 3: Sensitive actions. This is not an approval-rate metric. */}
            <div className="kpi-card">
              <span className="kpi-label">Kiểm soát HiTL & Tác vụ ghi</span>
              <span className="kpi-value">
                {sensitiveCount} <small style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>lệnh</small>
              </span>
              <span className="kpi-subtext">{sensitivePct}% event có tên tác vụ nhạy cảm (không phải tỷ lệ phê duyệt)</span>
            </div>

            {/* KPI 4: Primary Domain */}
            <div className="kpi-card">
              <span className="kpi-label">Nghiệp vụ tương tác chính</span>
              <span className="kpi-value kpi-value--domain">{dominantDomain}</span>
              <span className="kpi-subtext">{domainCounts[dominantDomain] || 0} lần gọi trong phiên</span>
            </div>

            {/* KPI 5: Success Rate */}
            <div className="kpi-card">
              <span className="kpi-label">Tỷ lệ thực thi thành công</span>
              <span className="kpi-value">
                {completed.length ? `${Math.round((successCount / completed.length) * 100)}%` : 'N/A'}
              </span>
              <span className="kpi-subtext">{successCount}/{completed.length} sự kiện kết thúc suôn sẻ</span>
            </div>
          </div>

          <div className="status-distribution" aria-label="Phân bố trạng thái">
            {Object.entries(statusLabel).map(([key, label]) => {
              const count = events.filter((event) => event.status === key).length
              if (!count) return null
              const pct = events.length ? Math.round((count / events.length) * 100) : 0
              return (
                <div className="distribution-row" key={key}>
                  <div className="distribution-info">
                    <span className="distribution-label">{label}</span>
                    <span className="distribution-count">{count} ({pct}%)</span>
                  </div>
                  <div className="status-progress-track">
                    <div
                      className={`status-progress-fill status-fill--${key}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          <AuditPerformanceChart events={events} p95={p95} />
          <ul className="measurement-note">
            <li><strong>P95:</strong> 95% lượt hoàn tất trong khoảng thời gian này hoặc nhanh hơn.</li>
            <li><strong>Thành công:</strong> công cụ không lỗi; chưa chứng minh nội dung đúng.</li>
          </ul>
        </section>
      ) : null}

      <ReleaseReadiness />
      <section className="release-benchmark" aria-labelledby="release-benchmark-title">
        <div className="evaluation-job-control">
          <Button onClick={() => void startEvaluation()} disabled={evaluationStarting || Boolean(evaluationJob && ['queued', 'running'].includes(evaluationJob.status))}>
            {evaluationStarting ? 'Đang xếp hàng…' : 'Chạy regression offline'}
          </Button>
          <p>Golden dataset → worker → checkpoint bền. Không dùng quota Gemini, không ghi Google. Không thay thế kiểm chứng câu trả lời thật.</p>
          {evaluationJob ? <div role="status" data-job-id={evaluationJob.id}>
            <strong>{evaluationJob.status}</strong>
            <div className="evaluation-suite-progress">{Object.entries(evaluationJob.checkpoint).map(([name, result]) => <div key={name}>
              <label htmlFor={`suite-${name}`}>{name} <strong>{result.passed}/{result.total}</strong></label>
              <progress id={`suite-${name}`} value={result.passed} max={Math.max(1, result.total)} />
            </div>)}</div>
            <details><summary>Dữ liệu checkpoint thô</summary><pre>{JSON.stringify(evaluationJob.checkpoint, null, 2)}</pre></details>
          </div> : null}
        </div>
        <header className="release-benchmark__header">
          <div>
            <span>Evaluation & Governance Harness</span>
            <h3 id="release-benchmark-title">Các bộ đo và phạm vi kiểm chứng</h3>
            <p>Chỉ dùng dữ liệu runtime và bộ kiểm thử có nguồn. Ô N/A không được quy thành điểm 0 hoặc tự suy diễn là đạt.</p>
          </div>
          <div className={`release-verdict release-verdict--${benchmarkVerdict.tone}`}>
            <strong>{benchmarkVerdict.score == null ? 'N/A' : benchmarkVerdict.score.toFixed(2)}</strong>
            <span>{benchmarkVerdict.label}</span>
          </div>
        </header>
        <div className="release-benchmark__table-wrap">
          <table className="release-benchmark__table">
            <thead><tr><th>Tiêu chí</th><th>Metric thật</th><th>Mẫu đo</th><th>Điểm /10</th><th>Phạm vi và giới hạn</th></tr></thead>
            <tbody>{benchmarkRows.map((row) => <tr key={row.criterion}>
              <th scope="row">{row.criterion}</th>
              <td data-label="Metric thật">{row.metric}</td>
              <td data-label="Mẫu đo">{row.sample}</td>
              <td data-label="Điểm /10"><strong>{row.score == null ? 'N/A' : row.score.toFixed(2)}</strong></td>
              <td data-label="Phạm vi">{row.scope}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <footer>
          <span><strong>Ngưỡng release:</strong> tổng ≥ 9,2/10, nhóm quan trọng ≥ 9; tất cả gate bắt buộc PASS cùng build.</span>
          <span>Baseline/candidate chưa có bằng chứng cùng dataset: N/A. Các bộ đo này không tự cấp chứng nhận release.</span>
          <time dateTime={benchmark?.evaluation?.evaluated_at_utc}>{benchmark?.evaluation?.evaluated_at_utc ? `Đo lúc ${formatDate(benchmark.evaluation.evaluated_at_utc)}` : 'Chưa có thời điểm đo'}</time>
        </footer>
      </section>

      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}
      {!loading && !error && events.length === 0 ? (
        <EmptyState title="Chưa có sự kiện" description="Audit log sẽ xuất hiện sau lần gọi tool đầu tiên." />
      ) : null}

      {!loading && events.length > 0 ? (
        <div className="table-scroll">
          <Table aria-label="Nhật ký tool">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Thời gian</TableHeaderCell>
                <TableHeaderCell>Tool</TableHeaderCell>
                <TableHeaderCell>User</TableHeaderCell>
                <TableHeaderCell>Trạng thái</TableHeaderCell>
                <TableHeaderCell>Độ trễ</TableHeaderCell>
                <TableHeaderCell>Request ID</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => (
                <TableRow
                  key={event.id}
                  className="clickable-row"
                  tabIndex={0}
                  onClick={() => setSelected(event)}
                  onKeyDown={(key) => {
                    if (key.key === 'Enter' || key.key === ' ') {
                      key.preventDefault()
                      setSelected(event)
                    }
                  }}
                >
                  <TableCell>{formatDate(event.created_at)}</TableCell>
                  <TableCell><code>{event.tool_name}</code></TableCell>
                  <TableCell>{event.user_email ?? 'Không rõ'}</TableCell>
                  <TableCell>
                    <Badge
                      appearance="tint"
                      color={
                        event.status === 'success'
                          ? 'success'
                          : event.status === 'error' || event.status === 'denied'
                          ? 'danger'
                          : 'informative'
                      }
                    >
                      {statusLabel[event.status] ?? event.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="numeric">
                    {event.latency_ms == null ? '...' : `${(event.latency_ms / 1000).toFixed(2)} s`}
                  </TableCell>
                  <TableCell><code className="request-id">{event.request_id.slice(0, 8)}</code></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}

      {nextCursor ? (
        <Button appearance="subtle" onClick={() => void loadMore()} disabled={loading}>
          Tải thêm nhật ký cũ
        </Button>
      ) : null}

      <Dialog open={Boolean(selected)} onOpenChange={(_, data) => !data.open && setSelected(null)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Chi tiết audit</DialogTitle>
            <DialogContent>
              {selected?.error_message ? (
                <p className="audit-failure-note">
                  <strong>Nguyên nhân ghi nhận:</strong> {selected.error_message}
                </p>
              ) : null}
              <pre className="audit-json">
                {selected
                  ? JSON.stringify(
                      {
                        request_id: selected.request_id,
                        tool: selected.tool_name,
                        status: selected.status,
                        arguments: selected.arguments,
                        result: selected.result,
                        error: selected.error_message,
                      },
                      null,
                      2
                    )
                  : ''}
              </pre>
            </DialogContent>
            <DialogActions>
              <Button appearance="primary" onClick={() => setSelected(null)}>Đóng</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
