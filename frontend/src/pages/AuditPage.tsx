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
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, formatDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { AuditEvent } from '../types'

const statusLabel: Record<string, string> = {
  started: 'Đang chạy',
  success: 'Thành công',
  warning: 'Cảnh báo',
  error: 'Lỗi',
  denied: 'Bị từ chối',
}

function AuditPerformanceChart({ events, p95 }: { events: AuditEvent[]; p95: number | null }) {
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line')
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
    .slice(0, 7)

  const svgWidth = 640
  const svgHeight = 200
  const padLeft = 52
  const padRight = 24
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
          <h4 className="audit-chart-title">Trực quan hóa hoạt động & độ trễ</h4>
          <p className="audit-chart-subtitle">
            {chartMode === 'line'
              ? `Biểu đồ xu hướng độ trễ qua ${validEvents.length} lượt gọi gần nhất (ms)`
              : `Phân bổ lượt gọi và tỷ lệ thành công theo từng công cụ`}
          </p>
        </div>
        <div className="audit-chart-toggle">
          <Button
            size="small"
            appearance={chartMode === 'line' ? 'primary' : 'subtle'}
            onClick={() => setChartMode('line')}
          >
            Đường xu hướng (Line)
          </Button>
          <Button
            size="small"
            appearance={chartMode === 'bar' ? 'primary' : 'subtle'}
            onClick={() => setChartMode('bar')}
          >
            Phân bổ công cụ (Bar)
          </Button>
        </div>
      </div>

      {chartMode === 'line' ? (
        validEvents.length === 0 ? (
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
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              <line x1={padLeft} y1={padTop} x2={svgWidth - padRight} y2={padTop} stroke="var(--border)" strokeDasharray="3 3" opacity="0.6" />
              <line x1={padLeft} y1={padTop + chartH / 2} x2={svgWidth - padRight} y2={padTop + chartH / 2} stroke="var(--border)" strokeDasharray="3 3" opacity="0.6" />
              <line x1={padLeft} y1={padTop + chartH} x2={svgWidth - padRight} y2={padTop + chartH} stroke="var(--border)" />

              <text x={padLeft - 8} y={padTop + 4} textAnchor="end" className="chart-axis-text">
                {Math.round(maxLat)}ms
              </text>
              <text x={padLeft - 8} y={padTop + chartH / 2 + 4} textAnchor="end" className="chart-axis-text">
                {Math.round(maxLat / 2)}ms
              </text>
              <text x={padLeft - 8} y={padTop + chartH + 4} textAnchor="end" className="chart-axis-text">
                0ms
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
                    P95: {p95}ms
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
                <g transform={`translate(${Math.min(hoveredPoint.x, svgWidth - 150)}, ${Math.max(hoveredPoint.y - 45, 8)})`}>
                  <rect width="140" height="38" rx="6" fill="var(--surface-raised)" stroke="var(--border-strong)" filter="drop-shadow(0 2px 8px rgba(0,0,0,0.3))" />
                  <text x="8" y="16" fontSize="11" fontWeight="600" fill="var(--text)">
                    {hoveredPoint.tool}
                  </text>
                  <text x="8" y="30" fontSize="10" fill={hoveredPoint.status === 'success' ? '#10b981' : '#ef4444'}>
                    {hoveredPoint.latency}ms • {hoveredPoint.status === 'success' ? 'Thành công' : 'Lỗi'}
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
        )
      ) : (
        <div className="audit-bar-chart-list">
          {sortedTools.map(([toolName, stats]) => {
            const successPct = Math.round((stats.success / stats.total) * 100)
            const avgLat = Math.round(stats.totalLat / stats.total)
            const firstTool = sortedTools[0]
            const maxToolCount = (firstTool ? firstTool[1].total : 1) || 1
            const widthPct = Math.round((stats.total / maxToolCount) * 100)
            return (
              <div key={toolName} className="bar-tool-row">
                <div className="bar-tool-info">
                  <code className="bar-tool-name">{toolName}</code>
                  <span className="bar-tool-meta">
                    {stats.total} lượt ({successPct}% thành công) • TB: {avgLat}ms
                  </span>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill-success"
                    style={{ width: `${(widthPct * successPct) / 100}%` }}
                    title={`Thành công: ${stats.success}`}
                  />
                  {stats.error > 0 ? (
                    <div
                      className="bar-fill-error"
                      style={{ width: `${(widthPct * (100 - successPct)) / 100}%` }}
                      title={`Lỗi: ${stats.error}`}
                    />
                  ) : null}
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
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AuditEvent | null>(null)
  const loadVersion = useRef(0)

  const load = useCallback(async () => {
    const version = ++loadVersion.current
    setLoading(true)
    setError('')
    try {
      const suffix = status === 'all' ? '' : `?status=${encodeURIComponent(status)}`
      const rows = await api<AuditEvent[]>(`/api/audit${suffix}`)
      // Bộ lọc đổi nhanh: chỉ request mới nhất được cập nhật màn hình.
      if (version === loadVersion.current) setEvents(rows)
    } catch (caught) {
      if (version === loadVersion.current) setError(caught instanceof Error ? caught.message : 'Không thể tải audit log.')
    } finally {
      if (version === loadVersion.current) setLoading(false)
    }
  }, [status])

  useEffect(() => { void load() }, [load])

  // Chỉ tính trên tập sự kiện API đang trả về; không suy diễn thành số liệu toàn hệ thống.
  const completed = events.filter((event) => event.status !== 'started')
  const latencies = completed.map((event) => event.latency_ms)
    .filter((value): value is number => value !== null && Number.isFinite(value) && value >= 0)
    .sort((a, b) => a - b)
  const successCount = completed.filter((event) => event.status === 'success').length
  const p95 = latencies[Math.ceil(latencies.length * 0.95) - 1] ?? null

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
    <section className="stack-page">
      <div className="page-heading">
        <div>
          <h2>Mọi tool call đều để lại dấu vết</h2>
          <p>Kiểm tra công cụ, trạng thái và thời gian xử lý. Hệ thống che các mẫu thông tin xác thực đã nhận diện trước khi ghi.</p>
        </div>
        <div className="page-heading__actions">
          <Button appearance="subtle" icon={<ArrowDownload24Regular />} disabled={!events.length} onClick={() => download('csv')}>Xuất CSV</Button>
          <Button appearance="subtle" icon={<ArrowDownload24Regular />} disabled={!events.length} onClick={() => download('json')}>Xuất JSON</Button>
          <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={load}>Làm mới</Button>
        </div>
      </div>
      <div className="filter-row">
        <Dropdown aria-label="Lọc theo trạng thái" value={status === 'all' ? 'Tất cả trạng thái' : statusLabel[status]} selectedOptions={[status]} onOptionSelect={(_, data) => setStatus(data.optionValue ?? 'all')}>
          <Option value="all">Tất cả trạng thái</Option>
          <Option value="success">Thành công</Option>
          <Option value="error">Lỗi</Option>
          <Option value="denied">Bị từ chối</Option>
          <Option value="started">Đang chạy</Option>
        </Dropdown>
      </div>
      {!loading && !error && events.length > 0 ? (
        <section className="audit-measurements" aria-label="Đo lường tập nhật ký hiện tại">
          <div className="measurement-heading">
            <h3>Hiệu quả thực thi công cụ</h3>
            <p>Thống kê thời gian thực từ {events.length} sự kiện đang tải theo bộ lọc hiện tại. Không phải toàn bộ lịch sử hay điểm chính xác tuyệt đối.</p>
          </div>
          <div className="kpi-cards-grid">
            <div className="kpi-card">
              <span className="kpi-label">Sự kiện đã kết thúc</span>
              <span className="kpi-value">{completed.length}</span>
            </div>
            <div className="kpi-card kpi-card--success">
              <span className="kpi-label">Tỷ lệ thành công</span>
              <span className="kpi-value">{completed.length ? `${Math.round((successCount / completed.length) * 100)}%` : '—'}</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Độ trễ P95</span>
              <span className="kpi-value">{p95 === null ? '—' : `${p95.toLocaleString('vi-VN')} ms`}</span>
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
          <p className="measurement-note">P95: 95% các lượt có số đo hoàn thành trong khoảng thời gian này hoặc nhanh hơn. Thành công ở đây nghĩa là công cụ chạy xong, không đảm bảo nội dung AI luôn đúng.</p>
        </section>
      ) : null}
      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}
      {!loading && !error && events.length === 0 ? <EmptyState title="Chưa có sự kiện" description="Audit log sẽ xuất hiện sau lần gọi tool đầu tiên." /> : null}
      {!loading && events.length > 0 ? (
        <div className="table-scroll">
          <Table aria-label="Nhật ký tool">
            <TableHeader><TableRow>
              <TableHeaderCell>Thời gian</TableHeaderCell><TableHeaderCell>Tool</TableHeaderCell><TableHeaderCell>User</TableHeaderCell><TableHeaderCell>Trạng thái</TableHeaderCell><TableHeaderCell>Độ trễ</TableHeaderCell><TableHeaderCell>Request ID</TableHeaderCell>
            </TableRow></TableHeader>
            <TableBody>{events.map((event) => (
              <TableRow key={event.id} className="clickable-row" tabIndex={0} onClick={() => setSelected(event)}
                onKeyDown={(key) => { if (key.key === 'Enter' || key.key === ' ') { key.preventDefault(); setSelected(event) } }}>
                <TableCell>{formatDate(event.created_at)}</TableCell>
                <TableCell><code>{event.tool_name}</code></TableCell>
                <TableCell>{event.user_email ?? 'Không rõ'}</TableCell>
                <TableCell><Badge appearance="tint" color={event.status === 'success' ? 'success' : event.status === 'error' || event.status === 'denied' ? 'danger' : 'informative'}>{statusLabel[event.status] ?? event.status}</Badge></TableCell>
                <TableCell className="numeric">{event.latency_ms == null ? '...' : `${event.latency_ms} ms`}</TableCell>
                <TableCell><code className="request-id">{event.request_id.slice(0, 8)}</code></TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        </div>
      ) : null}
      <Dialog open={Boolean(selected)} onOpenChange={(_, data) => !data.open && setSelected(null)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Chi tiết audit</DialogTitle>
            <DialogContent><pre className="audit-json">{selected ? JSON.stringify({ request_id: selected.request_id, tool: selected.tool_name, status: selected.status, arguments: selected.arguments, result: selected.result, error: selected.error_message }, null, 2) : ''}</pre></DialogContent>
            <DialogActions><Button appearance="primary" onClick={() => setSelected(null)}>Đóng</Button></DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
