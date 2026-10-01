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
  Tooltip,
} from '@fluentui/react-components'
import {
  Add24Regular,
  Archive24Regular,
  Delete24Regular,
  Search24Regular,
  Dismiss16Regular,
  Copy16Regular,
  Checkmark16Regular,
  BrainCircuit20Regular,
  Sparkle20Regular,
  Flash20Regular,
} from '@fluentui/react-icons'
import { FormEvent, useCallback, useEffect, useState, useMemo } from 'react'
import { api, formatDate } from '../api'
import { ErrorState, LoadingState } from '../components/AsyncState'
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

const kindIcons: Record<MemoryKind, string> = {
  fact: '🏢',
  preference: '🎯',
  context: '📌',
  episodic: '📅',
  procedural: '💡',
  summary: '📑',
}

const kindColors: Record<MemoryKind, string> = {
  fact: '#2563eb',
  preference: '#8b5cf6',
  context: '#10b981',
  episodic: '#f59e0b',
  procedural: '#0ea5e9',
  summary: '#64748b',
}

const STARTER_PRESETS = [
  {
    kind: 'preference' as MemoryKind,
    icon: '🎯',
    title: 'Phong cách trả lời Antigravity',
    content: 'Tôi muốn các câu trả lời ngắn gọn, có cấu trúc phân tích chuyên sâu, kèm trích dẫn số liệu rõ ràng và không dùng lời chào rườm rà.',
    tags: ['phong_cach', 'antigravity'],
  },
  {
    kind: 'context' as MemoryKind,
    icon: '📌',
    title: 'Dự án Veridra Local Production',
    content: 'Tôi đang vận hành Veridra phiên bản local single-admin, kết nối Google Drive & Gmail thật, sử dụng gemini-3.5-flash-lite và Qdrant RAG.',
    tags: ['du_an', 'veridra', 'local'],
  },
  {
    kind: 'procedural' as MemoryKind,
    icon: '💡',
    title: 'Quy trình xử lý thư quan trọng',
    content: 'Khi đọc email từ các hệ thống bảo mật hoặc đối tác, luôn trích xuất tóm tắt các action items chính, deadline và người liên quan lên đầu.',
    tags: ['quy_trinh', 'gmail'],
  },
  {
    kind: 'fact' as MemoryKind,
    icon: '🏢',
    title: 'Múi giờ & Ngôn ngữ hệ thống',
    content: 'Thời gian làm việc theo múi giờ GMT+7 (Asia/Ho_Chi_Minh), ngôn ngữ giao tiếp chính của hệ thống là Tiếng Việt.',
    tags: ['thong_tin', 'timezone', 'vietnam'],
  },
]

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

  return (
    <section className="memory-viz-section" aria-label="Trực quan hóa bộ nhớ">
      <div className="donut-charts-grid">
        <SvgDonutChart
          title="Phân bố theo loại"
          subtitle="Tỉ lệ các mục theo phân loại"
          slices={kindSlices}
          total={items.length}
          centerLabel={String(items.length)}
        />
        <SvgDonutChart
          title="Trạng thái lưu trữ"
          subtitle="Tỉ lệ mục đang dùng vs đã cất"
          slices={statusSlices}
          total={items.length}
          centerLabel={String(activeCount)}
        />
      </div>
    </section>
  )
}

function MemorySummaryBar({ items }: { items: MemoryItem[] }) {
  const activeCount = items.filter((item) => !item.is_archived).length
  const kinds = new Set(items.map((item) => item.kind)).size
  const highConf = items.filter((item) => (item.confidence ?? 1) >= 0.8).length

  return (
    <div
      className="memory-summary-bar"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        margin: '14px 0 18px',
      }}
    >
      <span className="memory-stat-pill">
        <strong>{items.length}</strong> mục bộ nhớ
      </span>
      <span className="memory-stat-pill">
        <strong>{activeCount}</strong> đang sử dụng
      </span>
      <span className="memory-stat-pill">
        <strong>{kinds}</strong> phân loại
      </span>
      <span className="memory-stat-pill">
        <strong>{highConf}</strong> tin cậy cao
      </span>
    </div>
  )
}

export function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [filterKind, setFilterKind] = useState<string>('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [kind, setKind] = useState<MemoryKind>('fact')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [addingPreset, setAddingPreset] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await api<{ memories: MemoryItem[] }>('/api/memories')
      setItems(result.memories)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải bộ nhớ.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

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
      const result = await api<{ memories: MemoryItem[] }>(
        `/api/memories/search?q=${encodeURIComponent(trimmed)}`
      )
      setItems(result.memories)
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
      setNotice('Đã lưu mục bộ nhớ mới thành công!')
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu bộ nhớ.')
    }
  }

  async function addQuickStarter(preset: typeof STARTER_PRESETS[0]) {
    setAddingPreset(preset.title)
    setError('')
    setNotice('')
    try {
      await api<MemoryItem>('/api/memories', {
        method: 'POST',
        body: JSON.stringify({
          kind: preset.kind,
          content: preset.content,
          tags: preset.tags,
          confidence: 0.95,
        }),
      })
      setNotice(`Đã thêm mục bộ nhớ "${preset.title}" thành công!`)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể thêm bộ nhớ mẫu.')
    } finally {
      setAddingPreset(null)
    }
  }

  async function archive(item: MemoryItem) {
    await api(`/api/memories/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_archived: !item.is_archived }),
    })
    setNotice(item.is_archived ? 'Đã khôi phục bộ nhớ.' : 'Đã cất bộ nhớ.')
    await load()
  }

  async function remove(item: MemoryItem) {
    if (!window.confirm('Xóa vĩnh viễn bộ nhớ này?')) return
    await api(`/api/memories/${item.id}`, { method: 'DELETE' })
    setNotice('Đã xóa bộ nhớ.')
    await load()
  }

  function copyMemory(item: MemoryItem) {
    void navigator.clipboard.writeText(item.content)
    setCopiedId(item.id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Filtered by search & kind
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchKind = filterKind === 'all' || item.kind === filterKind
      return matchKind
    })
  }, [items, filterKind])

  return (
    <section className="stack-page memory-page-v2">
      {/* Header */}
      <div className="page-heading">
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div className="page-icon-badge" style={{ background: 'rgba(139, 92, 246, 0.1)', borderColor: 'rgba(139, 92, 246, 0.25)' }}>
            <BrainCircuit20Regular style={{ fontSize: '24px', color: '#a78bfa' }} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <p className="home-kicker">Long-term Memory</p>
              <Badge appearance="filled" color="brand">Persistent Knowledge</Badge>
            </div>
            <h2>Bộ nhớ dài hạn & Phong cách cá nhân</h2>
            <ul className="page-summary-points">
              <li>Lưu sự thật, sở thích, ngữ cảnh và quy trình.</li>
              <li>Agent dùng lại khi phù hợp với yêu cầu của bạn.</li>
              <li>Có thể thêm thủ công hoặc nói trong chat: “Ghi nhớ rằng …”.</li>
            </ul>
          </div>
        </div>
        <Button appearance="primary" icon={<Add24Regular />} onClick={() => setDialogOpen(true)}>
          Thêm bộ nhớ mới
        </Button>
      </div>

      {notice && (
        <div className="artifact-success-notice" style={{ margin: '10px 0' }}>
          <span>✓ {notice}</span>
        </div>
      )}

      {error ? <ErrorState message={error} retry={load} /> : null}

      {/* Quick Starters Section */}
      <section className="memory-starters-section" aria-label="Gợi ý bộ nhớ khởi đầu">
        <div className="starters-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkle20Regular style={{ color: '#fbbf24' }} />
            <strong>Khởi tạo bộ nhớ 1-Click (Quick Starters)</strong>
          </div>
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
            Nhấn thêm để nạp ngay các quy chuẩn phản hồi & ngữ cảnh dự án vào Agent
          </span>
        </div>

        <div className="starters-grid">
          {STARTER_PRESETS.map((p) => {
            const isAdded = items.some((i) => i.content === p.content)
            return (
              <div key={p.title} className="starter-card">
                <div className="starter-card__top">
                  <span className="starter-card__icon">{p.icon}</span>
                  <Badge appearance="tint" color={kindBadgeColor[p.kind]}>
                    {kindLabels[p.kind]}
                  </Badge>
                </div>
                <strong className="starter-card__title">{p.title}</strong>
                <p className="starter-card__content">{p.content}</p>
                <div className="starter-card__bottom">
                  <div className="starter-tags">
                    {p.tags.map((t) => (
                      <span key={t} className="starter-tag">
                        #{t}
                      </span>
                    ))}
                  </div>
                  <Button
                    size="small"
                    appearance={isAdded ? 'subtle' : 'primary'}
                    disabled={isAdded || addingPreset === p.title}
                    icon={isAdded ? <Checkmark16Regular /> : <Flash20Regular />}
                    onClick={() => void addQuickStarter(p)}
                  >
                    {isAdded ? 'Đã có' : addingPreset === p.title ? 'Đang lưu…' : 'Nạp vào'}
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Search and Category Filter Toolbar */}
      <div className="memory-toolbar-card">
        <form className="search-row" onSubmit={search} style={{ margin: 0, flex: 1 }}>
          <Input
            id="memory-search"
            name="query"
            aria-label="Tìm bộ nhớ"
            value={query}
            onChange={(_, data) => setQuery(data.value)}
            contentBefore={<Search24Regular />}
            contentAfter={
              query ? (
                <Button
                  size="small"
                  appearance="subtle"
                  icon={<Dismiss16Regular />}
                  onClick={() => {
                    setQuery('')
                    void load()
                  }}
                  aria-label="Xóa tìm kiếm"
                />
              ) : undefined
            }
            placeholder="Tìm theo ý nghĩa hoặc từ khóa (ví dụ: phong cách, email, drive)..."
            style={{ width: '100%' }}
          />
          <Button type="submit">Tìm kiếm</Button>
        </form>

        {/* Category Pills */}
        <div className="memory-category-pills">
          <button
            type="button"
            className={`kind-pill ${filterKind === 'all' ? 'kind-pill--active' : ''}`}
            onClick={() => setFilterKind('all')}
          >
            Tất cả ({items.length})
          </button>
          {(Object.keys(kindLabels) as MemoryKind[]).map((k) => {
            const count = items.filter((i) => i.kind === k).length
            return (
              <button
                key={k}
                type="button"
                className={`kind-pill ${filterKind === k ? 'kind-pill--active' : ''}`}
                onClick={() => setFilterKind(k)}
              >
                {kindIcons[k]} {kindLabels[k]} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {loading ? <LoadingState /> : null}

      {!loading && items.length > 0 ? (
        items.length >= 6 ? (
          <MemoryVisualizationDashboard items={items} />
        ) : (
          <MemorySummaryBar items={items} />
        )
      ) : null}

      {/* Memory List Cards */}
      <div className="memory-cards-grid">
        {!loading && filteredItems.length === 0 && (
          <div className="empty-state" style={{ gridColumn: '1 / -1', padding: '36px' }}>
            <p className="rail-empty">
              {query
                ? `Không tìm thấy bộ nhớ phù hợp với từ khóa "${query}".`
                : 'Chưa có bộ nhớ nào thuộc phân loại này. Bạn có thể nạp từ các mẫu phía trên.'}
            </p>
          </div>
        )}

        {filteredItems.map((item) => {
          const conf = Math.round((item.confidence ?? 1) * 100)
          return (
            <article
              key={item.id}
              className={`memory-card-v2 ${item.is_archived ? 'memory-card-v2--archived' : ''}`}
            >
              <div className="memory-card-v2__top">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="memory-card-v2__icon">{kindIcons[item.kind] ?? '📝'}</span>
                  <Badge appearance="tint" color={kindBadgeColor[item.kind] ?? 'informative'}>
                    {kindLabels[item.kind]}
                  </Badge>
                  {item.is_archived && (
                    <Badge appearance="filled" color="subtle">
                      Đã cất
                    </Badge>
                  )}
                </div>

                {/* Confidence Meter */}
                <div className="confidence-meter" title={`Độ tin cậy của bộ nhớ: ${conf}%`}>
                  <div className="confidence-track">
                    <div
                      className="confidence-fill"
                      style={{
                        width: `${conf}%`,
                        background: conf >= 80 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444',
                      }}
                    />
                  </div>
                  <span className="confidence-label">{conf}%</span>
                </div>
              </div>

              <div className="memory-card-v2__body">
                <p className="memory-card-v2__text">{item.content}</p>
              </div>

              <div className="memory-card-v2__bottom">
                <div className="memory-card-v2__tags">
                  {item.tags.map((tag) => (
                    <span key={tag} className="memory-tag-chip">
                      #{tag}
                    </span>
                  ))}
                </div>

                <div className="memory-card-v2__actions">
                  <span className="memory-date-text">{formatDate(item.updated_at)}</span>
                  <Tooltip content={copiedId === item.id ? 'Đã sao chép!' : 'Sao chép nội dung'} relationship="label">
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={copiedId === item.id ? <Checkmark16Regular /> : <Copy16Regular />}
                      onClick={() => copyMemory(item)}
                      aria-label="Sao chép"
                    />
                  </Tooltip>
                  <Tooltip content={item.is_archived ? 'Khôi phục' : 'Lưu trữ / Cất'} relationship="label">
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Archive24Regular style={{ fontSize: '16px' }} />}
                      onClick={() => void archive(item)}
                      aria-label="Lưu trữ"
                    />
                  </Tooltip>
                  <Tooltip content="Xóa vĩnh viễn" relationship="label">
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Delete24Regular style={{ fontSize: '16px' }} />}
                      onClick={() => void remove(item)}
                      aria-label="Xóa"
                    />
                  </Tooltip>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {/* Manual Add Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(_, data) => setDialogOpen(data.open)}>
        <DialogSurface>
          <form onSubmit={save}>
            <DialogBody>
              <DialogTitle>Thêm bộ nhớ có kiểm soát</DialogTitle>
              <DialogContent className="dialog-form">
                <Field label="Loại bộ nhớ" required>
                  <Dropdown
                    id="memory-kind"
                    name="kind"
                    value={kindLabels[kind]}
                    selectedOptions={[kind]}
                    onOptionSelect={(_, data) => setKind(data.optionValue as MemoryKind)}
                  >
                    {Object.entries(kindLabels).map(([value, label]) => (
                      <Option
                        key={value}
                        value={value}
                        text={`${kindIcons[value as MemoryKind]} ${label}`}
                      >
                        {kindIcons[value as MemoryKind]} {label}
                      </Option>
                    ))}
                  </Dropdown>
                </Field>
                <Field label="Nội dung cần nhớ" hint="Không nhập API key, token hoặc mật khẩu nhạy cảm." required>
                  <Textarea
                    id="memory-content"
                    name="content"
                    value={content}
                    placeholder="Ví dụ: Tôi thích tóm tắt bằng bảng và trích dẫn chuẩn Antigravity..."
                    onChange={(_, data) => setContent(data.value)}
                    resize="vertical"
                    rows={4}
                  />
                </Field>
                <Field label="Nhãn phân loại (Tags)" hint="Phân tách bằng dấu phẩy, ví dụ: cong_viec, email, phong_cach">
                  <Input
                    id="memory-tags"
                    name="tags"
                    value={tags}
                    placeholder="cong_viec, email"
                    onChange={(_, data) => setTags(data.value)}
                  />
                </Field>
              </DialogContent>
              <DialogActions>
                <Button appearance="secondary" onClick={() => setDialogOpen(false)}>
                  Hủy
                </Button>
                <Button appearance="primary" type="submit" disabled={!content.trim()}>
                  Lưu vào bộ nhớ
                </Button>
              </DialogActions>
            </DialogBody>
          </form>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
