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
  Field,
  Input,
  Option,
  Textarea,
} from '@fluentui/react-components'
import { Add24Regular, Archive24Regular, Delete24Regular, Search24Regular } from '@fluentui/react-icons'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, formatDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { MemoryItem, MemoryKind } from '../types'

const kindLabels: Record<MemoryKind, string> = {
  fact: 'Sự thật',
  preference: 'Sở thích',
  context: 'Ngữ cảnh',
  episodic: 'Sự kiện',
  procedural: 'Quy trình',
  summary: 'Tóm tắt',
}

const kindBadgeColor: Record<MemoryKind, 'brand' | 'important' | 'success' | 'warning' | 'informative' | 'subtle'> = {
  fact: 'brand',
  preference: 'important',
  context: 'success',
  episodic: 'warning',
  procedural: 'informative',
  summary: 'subtle',
}

const kindColors: Record<MemoryKind, string> = {
  fact: '#2563eb',
  preference: '#8b5cf6',
  context: '#10b981',
  episodic: '#f59e0b',
  procedural: '#0ea5e9',
  summary: '#64748b',
}

interface DonutSlice {
  key: string
  label: string
  count: number
  color: string
}

function SvgDonutChart({
  title,
  subtitle,
  slices,
  total,
  centerLabel,
}: {
  title: string
  subtitle: string
  slices: DonutSlice[]
  total: number
  centerLabel: string
}) {
  const radius = 38
  const circ = 2 * Math.PI * radius
  let accumulated = 0

  return (
    <div className="donut-chart-card">
      <div className="donut-chart-header">
        <span className="donut-chart-title">{title}</span>
        <span className="donut-chart-subtitle">{subtitle}</span>
      </div>
      <div className="donut-chart-body">
        <div className="donut-svg-wrapper">
          <svg viewBox="0 0 100 100" className="donut-svg">
            <circle
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke="var(--surface-muted)"
              strokeWidth="12"
            />
            {total > 0 &&
              slices.map((slice) => {
                const len = (slice.count / total) * circ
                const offset = accumulated
                accumulated += len
                if (slice.count === 0) return null
                return (
                  <circle
                    key={slice.key}
                    cx="50"
                    cy="50"
                    r={radius}
                    fill="none"
                    stroke={slice.color}
                    strokeWidth="12"
                    strokeDasharray={`${len} ${circ}`}
                    strokeDashoffset={-offset}
                    transform="rotate(-90 50 50)"
                    style={{ transition: 'stroke-dasharray 0.4s ease' }}
                  />
                )
              })}
            <text x="50" y="48" textAnchor="middle" className="donut-center-val">
              {centerLabel}
            </text>
            <text x="50" y="60" textAnchor="middle" className="donut-center-lbl">
              mục
            </text>
          </svg>
        </div>
        <div className="donut-legend">
          {slices.map((slice) => {
            const pct = total ? Math.round((slice.count / total) * 100) : 0
            return (
              <div key={slice.key} className="donut-legend-row">
                <span className="donut-legend-dot" style={{ background: slice.color }} />
                <span className="donut-legend-label">{slice.label}</span>
                <span className="donut-legend-val">
                  {slice.count} ({pct}%)
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function MemoryVisualizationDashboard({ items }: { items: MemoryItem[] }) {
  const [activeTab, setActiveTab] = useState<'pies' | 'line'>('pies')

  const kindCounts = items.reduce<Record<string, number>>((acc, item) => {
    acc[item.kind] = (acc[item.kind] || 0) + 1
    return acc
  }, {})
  const kindSlices: DonutSlice[] = (Object.keys(kindLabels) as MemoryKind[])
    .map((k) => ({
      key: k,
      label: kindLabels[k],
      count: kindCounts[k] || 0,
      color: kindColors[k] || '#3b82f6',
    }))
    .filter((s) => s.count > 0)

  const archivedCount = items.filter((i) => i.is_archived).length
  const activeCount = items.length - archivedCount
  const statusSlices: DonutSlice[] = [
    { key: 'active', label: 'Đang dùng', count: activeCount, color: '#10b981' },
    { key: 'archived', label: 'Đã cất', count: archivedCount, color: '#94a3b8' },
  ]

  const highConf = items.filter((i) => i.confidence >= 0.9).length
  const normalConf = items.length - highConf
  const confSlices: DonutSlice[] = [
    { key: 'high', label: 'Xác thực cao (≥90%)', count: highConf, color: '#3b82f6' },
    { key: 'review', label: 'Đang theo dõi (<90%)', count: normalConf, color: '#f59e0b' },
  ]

  const sortedByDate = [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  )
  const timelineMap: Record<string, number> = {}
  sortedByDate.forEach((item) => {
    const d = new Date(item.created_at).toLocaleDateString('vi-VN')
    timelineMap[d] = (timelineMap[d] || 0) + 1
  })
  const timelineEntries = Object.entries(timelineMap)
  let runningTotal = 0
  const timelinePoints = timelineEntries.map(([date, count]) => {
    runningTotal += count
    return { date, count: runningTotal }
  })

  const svgW = 680
  const svgH = 190
  const padL = 40
  const padR = 24
  const padT = 20
  const padB = 30
  const chartW = svgW - padL - padR
  const chartH = svgH - padT - padB
  const maxVal = Math.max(...timelinePoints.map((p) => p.count), 5)
  const stepX = timelinePoints.length > 1 ? chartW / (timelinePoints.length - 1) : chartW / 2

  const pts = timelinePoints.map((p, i) => ({
    x: padL + i * stepX,
    y: padT + chartH - (p.count / maxVal) * chartH,
    date: p.date,
    count: p.count,
  }))

  const linePath = pts.reduce(
    (acc, pt, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)},${pt.y.toFixed(1)}`,
    ''
  )
  const firstP = pts[0]
  const lastP = pts[pts.length - 1]
  const areaPath =
    firstP && lastP
      ? `${linePath} L ${lastP.x.toFixed(1)},${(padT + chartH).toFixed(1)} L ${firstP.x.toFixed(1)},${(padT + chartH).toFixed(1)} Z`
      : ''

  return (
    <section className="memory-analytics-card" aria-label="Trực quan hóa dữ liệu bộ nhớ">
      <div className="memory-analytics-header">
        <div>
          <h3>Trực quan hóa cấu trúc bộ nhớ</h3>
          <p>Phân tích đa chiều trên tổng số {items.length} mục bộ nhớ của tài khoản.</p>
        </div>
        <div className="analytics-tabs">
          <Button
            size="small"
            appearance={activeTab === 'pies' ? 'primary' : 'subtle'}
            onClick={() => setActiveTab('pies')}
          >
            Đa biểu đồ tròn (Pie Charts)
          </Button>
          <Button
            size="small"
            appearance={activeTab === 'line' ? 'primary' : 'subtle'}
            onClick={() => setActiveTab('line')}
          >
            Tiến trình tích lũy (Line Chart)
          </Button>
        </div>
      </div>

      {activeTab === 'pies' ? (
        <div className="donut-grid">
          <SvgDonutChart
            title="1. Theo Thể loại"
            subtitle="Phân bố chức năng bộ nhớ"
            slices={kindSlices}
            total={items.length}
            centerLabel={`${items.length}`}
          />
          <SvgDonutChart
            title="2. Theo Vòng đời"
            subtitle="Tình trạng sử dụng"
            slices={statusSlices}
            total={items.length}
            centerLabel={`${activeCount}`}
          />
          <SvgDonutChart
            title="3. Theo Độ tin cậy"
            subtitle="Mức độ kiểm chứng"
            slices={confSlices}
            total={items.length}
            centerLabel={`${highConf}`}
          />
        </div>
      ) : (
        <div className="memory-line-wrapper">
          <svg viewBox={`0 0 ${svgW} ${svgH}`} className="memory-line-svg">
            <defs>
              <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <line x1={padL} y1={padT} x2={svgW - padR} y2={padT} stroke="var(--border)" strokeDasharray="3 3" />
            <line x1={padL} y1={padT + chartH / 2} x2={svgW - padR} y2={padT + chartH / 2} stroke="var(--border)" strokeDasharray="3 3" />
            <line x1={padL} y1={padT + chartH} x2={svgW - padR} y2={padT + chartH} stroke="var(--border)" />

            <text x={padL - 8} y={padT + 4} textAnchor="end" className="chart-axis-text">{maxVal}</text>
            <text x={padL - 8} y={padT + chartH / 2 + 4} textAnchor="end" className="chart-axis-text">{Math.round(maxVal / 2)}</text>
            <text x={padL - 8} y={padT + chartH + 4} textAnchor="end" className="chart-axis-text">0</text>

            <path d={areaPath} fill="url(#memGrad)" />
            <path d={linePath} fill="none" stroke="#8b5cf6" strokeWidth="2.5" strokeLinecap="round" />

            {pts.map((p, idx) => (
              <circle
                key={idx}
                cx={p.x}
                cy={p.y}
                r="4"
                fill="#8b5cf6"
                stroke="var(--surface-raised)"
                strokeWidth="2"
              >
                <title>{`${p.date}: ${p.count} mục tích lũy`}</title>
              </circle>
            ))}
          </svg>
          <div className="chart-legend">
            <span className="legend-item">
              <span className="legend-dot" style={{ background: '#8b5cf6' }} />
              Đường tích lũy kiến thức bộ nhớ theo ngày
            </span>
          </div>
        </div>
      )}
    </section>
  )
}

export function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [kind, setKind] = useState<MemoryKind>('fact')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await api<{ memories: MemoryItem[] }>('/api/memories')
      setItems(result.memories)
      setActiveQuery('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải bộ nhớ.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function search(event: FormEvent) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return load()
    if (trimmed.length < 2) {
      setError('Vui lòng nhập ít nhất 2 ký tự để tìm kiếm.')
      return
    }
    setError('')
    try {
      const result = await api<{ memories: MemoryItem[] }>(`/api/memories/search?q=${encodeURIComponent(trimmed)}`)
      setItems(result.memories)
      setActiveQuery(trimmed)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tìm bộ nhớ.')
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    try {
      await api<MemoryItem>('/api/memories', {
        method: 'POST',
        body: JSON.stringify({
          kind,
          content,
          tags: tags.split(',').map((item) => item.trim()).filter(Boolean),
          confidence: 1,
        }),
      })
      setDialogOpen(false)
      setContent('')
      setTags('')
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu bộ nhớ.')
    }
  }

  async function archive(item: MemoryItem) {
    await api(`/api/memories/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_archived: true }),
    })
    await load()
  }

  async function remove(item: MemoryItem) {
    if (!window.confirm('Xóa vĩnh viễn bộ nhớ này?')) return
    await api(`/api/memories/${item.id}`, { method: 'DELETE' })
    await load()
  }

  return (
    <section className="stack-page">
      <div className="page-heading">
        <div>
          <h2>Những điều agent ghi nhớ</h2>
          <p>Mỗi bộ nhớ thuộc riêng tài khoản của bạn và có thể được xem, lưu trữ hoặc xóa.</p>
        </div>
        <Button appearance="primary" icon={<Add24Regular />} onClick={() => setDialogOpen(true)}>
          Thêm bộ nhớ
        </Button>
      </div>
      <form className="search-row" onSubmit={search}>
        <Input id="memory-search" name="query" aria-label="Tìm bộ nhớ" value={query} onChange={(_, data) => setQuery(data.value)} contentBefore={<Search24Regular />} placeholder="Tìm theo ý nghĩa hoặc từ khóa" />
        <Button type="submit">Tìm</Button>
      </form>
      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyState
          title={activeQuery ? 'Không tìm thấy bộ nhớ phù hợp' : 'Chưa có bộ nhớ'}
          description={activeQuery
            ? 'Thử một từ khóa gần với nội dung đã lưu, hoặc xóa ô tìm kiếm để xem tất cả.'
            : 'Bạn có thể tự lưu một fact hoặc để agent ghi nhớ trong khi trò chuyện.'}
        />
      ) : null}
      {!loading && !error && items.length > 0 ? (
        <MemoryVisualizationDashboard items={items} />
      ) : null}
      <div className="memory-list">
        {items.map((item) => (
          <article key={item.id} className="memory-row">
            <div className="memory-row__type"><Badge appearance="tint" color={kindBadgeColor[item.kind] ?? 'informative'}>{kindLabels[item.kind]}</Badge></div>
            <div className="memory-row__content">
              <p>{item.content}</p>
              <div className="memory-meta">
                <span>Cập nhật {formatDate(item.updated_at)}</span>
                {item.tags.map((tag) => <span key={tag}>#{tag}</span>)}
              </div>
            </div>
            <div className="row-actions">
              <Button appearance="subtle" icon={<Archive24Regular />} aria-label="Lưu trữ" onClick={() => archive(item)} />
              <Button appearance="subtle" icon={<Delete24Regular />} aria-label="Xóa" onClick={() => remove(item)} />
            </div>
          </article>
        ))}
      </div>

      <Dialog open={dialogOpen} onOpenChange={(_, data) => setDialogOpen(data.open)}>
        <DialogSurface>
          <form onSubmit={save}>
            <DialogBody>
              <DialogTitle>Thêm bộ nhớ có kiểm soát</DialogTitle>
              <DialogContent className="dialog-form">
                <Field label="Loại bộ nhớ" required>
                  <Dropdown id="memory-kind" name="kind" value={kindLabels[kind]} selectedOptions={[kind]} onOptionSelect={(_, data) => setKind(data.optionValue as MemoryKind)}>
                    {Object.entries(kindLabels).map(([value, label]) => <Option key={value} value={value}>{label}</Option>)}
                  </Dropdown>
                </Field>
                <Field label="Nội dung" hint="Không nhập API key, token hoặc mật khẩu." required>
                  <Textarea id="memory-content" name="content" value={content} onChange={(_, data) => setContent(data.value)} resize="vertical" />
                </Field>
                <Field label="Nhãn" hint="Phân tách bằng dấu phẩy">
                  <Input id="memory-tags" name="tags" value={tags} onChange={(_, data) => setTags(data.value)} />
                </Field>
              </DialogContent>
              <DialogActions>
                <Button appearance="secondary" onClick={() => setDialogOpen(false)}>Hủy</Button>
                <Button appearance="primary" type="submit" disabled={!content.trim()}>Lưu</Button>
              </DialogActions>
            </DialogBody>
          </form>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
