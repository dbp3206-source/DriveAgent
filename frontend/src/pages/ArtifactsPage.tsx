import {
  Button,
  Input,
  Select,
  Textarea,
  Tooltip,
  Badge,
} from '@fluentui/react-components'
import {
  Add20Regular,
  Archive20Regular,
  ArrowDownload20Regular,
  Search20Regular,
  Dismiss16Regular,
  TextBold20Regular,
  TextItalic20Regular,
  Code20Regular,
  Table20Regular,
  Link20Regular,
  Eye20Regular,
  Edit20Regular,
  Clock20Regular,
  Checkmark20Regular,
  DocumentBulletList24Regular,
} from '@fluentui/react-icons'
import { useEffect, useState, useRef, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api'
import { ErrorState, LoadingState } from '../components/AsyncState'

interface Artifact {
  id: string
  title: string
  content: string
  kind: string
  revision: number
  is_archived: boolean
}

const kindMeta: Record<string, { label: string; icon: string; color: string; bg: string }> = {
  note: { label: 'Ghi chú', icon: '📝', color: '#60a5fa', bg: 'rgba(37, 99, 235, 0.12)' },
  checklist: { label: 'Checklist', icon: '✅', color: '#34d399', bg: 'rgba(16, 185, 129, 0.12)' },
  quiz: { label: 'Ôn tập', icon: '💡', color: '#f472b6', bg: 'rgba(236, 72, 153, 0.12)' },
  plan: { label: 'Kế hoạch', icon: '🎯', color: '#fbbf24', bg: 'rgba(245, 158, 11, 0.12)' },
  report: { label: 'Báo cáo', icon: '📑', color: '#a78bfa', bg: 'rgba(139, 92, 246, 0.12)' },
}

const TEMPLATES: Record<string, { title: string; kind: string; content: string }> = {
  note: {
    title: 'Ghi chú cuộc họp & Điểm cốt lõi',
    kind: 'note',
    content: `# Ghi chú cuộc họp / Điểm cốt lõi\n\n**Ngày thực hiện**: \${new Date().toLocaleDateString('vi-VN')}\n**Tham gia**: Admin, Team\n\n## 1. Mục tiêu cuộc họp\n- Điểm trọng tâm 1\n- Điểm trọng tâm 2\n\n## 2. Thảo luận chi tiết\n- Ghi nhận ý kiến đóng góp...\n\n## 3. Hành động tiếp theo (Action Items)\n- [ ] Nhiệm vụ 1 (Phụ trách: Nam)\n- [ ] Nhiệm vụ 2 (Hạn: Cuối tuần)\n`,
  },
  checklist: {
    title: 'Checklist nghiệm thu & Kiểm định',
    kind: 'checklist',
    content: `# Checklist kiểm thử & Nghiệm thu\n\n- [ ] Kiểm tra kết nối Google Drive & OAuth token\n- [ ] Kiểm tra tính năng tìm kiếm văn bản RAG\n- [ ] Kiểm tra bộ đọc Gmail & xử lý liên kết\n- [ ] Đánh giá độ trễ và độ sâu câu trả lời\n- [ ] Sao lưu cơ sở dữ liệu local\n`,
  },
  plan: {
    title: 'Kế hoạch hành động tuần',
    kind: 'plan',
    content: `# Kế hoạch hành động tuần\n\n| Ngày | Hạng mục chính | Kết quả mong đợi | Trạng thái |\n|---|---|---|---|\n| Thứ 2 | Rà soát chỉ số RAG | Đạt độ chính xác > 90% | Hoàn thành |\n| Thứ 3 | Nâng cấp giao diện Note | Editor Antigravity style | Đang làm |\n| Thứ 4 | Tinh chỉnh Visual Skills | Flowchart timeline sống động | Chuẩn bị |\n| Thứ 5 | Đánh giá tổng thể | Báo cáo nghiệm thu bàn giao | Kế hoạch |\n`,
  },
  report: {
    title: 'Báo cáo phân tích dữ liệu',
    kind: 'report',
    content: `# Báo cáo phân tích dữ liệu chuyên sâu\n\n> **Tóm lược quản trị**: Tài liệu phân tích hiệu suất và chất lượng hệ thống.\n\n## 1. Bối cảnh & Hiện trạng\nPhân tích dữ liệu thực tế thu thập từ nguồn dữ liệu lưu trữ.\n\n## 2. Bảng chỉ số trọng yếu\n| Chỉ số | Hiện tại | Mục tiêu | Đánh giá |\n|---|---|---|---|\n| Độ chuẩn xác RAG | 92% | > 90% | Đạt |\n| Tốc độ sinh câu | 1.8s | < 2.5s | Tốt |\n\n## 3. Kết luận & Đề xuất\nTiếp tục duy trì tính kỷ luật trong kiểm định và triển khai liên tục.\n`,
  },
}

export function ArtifactsPage() {
  const [items, setItems] = useState<Artifact[]>([])
  const [selected, setSelected] = useState<Artifact | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [kind, setKind] = useState('note')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [viewMode, setViewMode] = useState<'edit' | 'split' | 'preview'>('split')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterKind, setFilterKind] = useState('all')
  const [exportFormat, setExportFormat] = useState<'md' | 'docx' | 'pdf'>('md')

  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const hasUnsavedChanges = Boolean(
    selected && (title !== selected.title || content !== selected.content || kind !== selected.kind)
  )

  async function load() {
    try {
      const result = await api<{ items: Artifact[] }>('/api/artifacts?include_archived=true')
      setItems(result.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không tải được bản lưu.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  function choose(item: Artifact | null) {
    setSelected(item)
    setTitle(item?.title ?? '')
    setContent(item?.content ?? '')
    setKind(item?.kind ?? 'note')
    setKey(crypto.randomUUID())
    setError('')
    setNotice('')
  }

  function applyTemplate(templateKey: string) {
    const t = TEMPLATES[templateKey]
    if (!t) return
    setTitle(t.title)
    setKind(t.kind)
    setContent(t.content)
    setSelected(null)
    setKey(crypto.randomUUID())
    setNotice(`Đã áp dụng mẫu "${t.title}"`)
  }

  async function save(archived = selected?.is_archived ?? false) {
    if (!title.trim() || !content.trim()) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const item = await api<Artifact>('/api/artifacts', {
        method: 'POST',
        body: JSON.stringify({
          title,
          content,
          kind,
          creation_key: key,
          artifact_id: selected?.id ?? null,
          expected_revision: selected?.revision ?? 1,
          is_archived: archived,
        }),
      })
      setSelected(item)
      setNotice(`Đã lưu phiên bản v${item.revision} thành công!`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không lưu được.')
    } finally {
      setBusy(false)
    }
  }

  const saveRef = useRef(save)
  useEffect(() => {
    saveRef.current = save
  })

  // Ctrl+S Keyboard shortcut to quick-save
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        void saveRef.current()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Markdown helper
  function insertMarkdown(prefix: string, suffix = '', defaultText = '') {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selectedText = content.slice(start, end) || defaultText
    const replacement = `${prefix}${selectedText}${suffix}`
    const nextContent = content.slice(0, start) + replacement + content.slice(end)
    setContent(nextContent)
    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length)
    }, 10)
  }

  // Calculated metrics
  const stats = useMemo(() => {
    const trimmed = content.trim()
    const words = trimmed ? trimmed.split(/\s+/).length : 0
    const chars = content.length
    const readTime = Math.max(1, Math.ceil(words / 180))
    const lines = content ? content.split('\n').length : 0
    return { words, chars, readTime, lines }
  }, [content])

  // Filtered artifacts
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch =
        !searchQuery ||
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.content.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesKind = filterKind === 'all' || item.kind === filterKind
      return matchesSearch && matchesKind
    })
  }, [items, searchQuery, filterKind])

  return (
    <section className="stack-page artifact-page-root">
      <div className="page-heading">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="page-icon-badge">
            <DocumentBulletList24Regular style={{ color: 'var(--accent, #3b82f6)' }} />
          </div>
          <div>
            <h2>Không gian Ghi chú & Tài liệu (Artifacts)</h2>
            <p>
              Soạn thảo Markdown chuyên nghiệp với Live Preview, tổ chức ghi chú, checklist, bộ câu hỏi và kế hoạch học tập/làm việc.
            </p>
          </div>
        </div>
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <LoadingState label="Đang tải danh sách bản lưu…" />
      ) : (
        <div className="artifact-workbench-v2">
          {/* Left Rail: Sidebar List */}
          <aside className="artifact-sidebar">
            <div className="artifact-sidebar-header">
              <Button
                appearance="primary"
                icon={<Add20Regular />}
                disabled={busy}
                onClick={() => choose(null)}
                style={{ width: '100%', fontWeight: 600 }}
              >
                Tạo bản mới
              </Button>
            </div>

            {/* Quick Templates */}
            <div className="artifact-quick-templates">
              <span className="quick-templates-label">Mẫu gợi ý:</span>
              <div className="quick-template-chips">
                <button type="button" onClick={() => applyTemplate('note')} className="quick-template-btn" title="Mẫu ghi chú cuộc họp">📝 Họp</button>
                <button type="button" onClick={() => applyTemplate('checklist')} className="quick-template-btn" title="Mẫu checklist nghiệm thu">✅ Checklist</button>
                <button type="button" onClick={() => applyTemplate('plan')} className="quick-template-btn" title="Mẫu kế hoạch tuần">🎯 Kế hoạch</button>
                <button type="button" onClick={() => applyTemplate('report')} className="quick-template-btn" title="Mẫu báo cáo phân tích">📑 Báo cáo</button>
              </div>
            </div>

            {/* Search Box */}
            <div className="artifact-search-box">
              <Input
                contentBefore={<Search20Regular />}
                contentAfter={
                  searchQuery ? (
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Dismiss16Regular />}
                      onClick={() => setSearchQuery('')}
                      aria-label="Xóa tìm kiếm"
                    />
                  ) : undefined
                }
                placeholder="Tìm ghi chú, nội dung..."
                value={searchQuery}
                onChange={(_, d) => setSearchQuery(d.value)}
                className="artifact-search-glass-input"
                style={{ width: '100%' }}
              />
            </div>

            {/* Kind Filters */}
            <div className="artifact-kind-filters">
              <button
                type="button"
                className={`kind-pill glass-filter-pill ${filterKind === 'all' ? 'kind-pill--active glass-filter-pill--active' : ''}`}
                onClick={() => setFilterKind('all')}
              >
                Tất cả ({items.length})
              </button>
              {Object.entries(kindMeta).map(([k, meta]) => {
                const count = items.filter((i) => i.kind === k).length
                if (count === 0 && filterKind !== k) return null
                return (
                  <button
                    key={k}
                    type="button"
                    className={`kind-pill glass-filter-pill ${filterKind === k ? 'kind-pill--active glass-filter-pill--active' : ''}`}
                    onClick={() => setFilterKind(k)}
                  >
                    {meta.icon} {meta.label} ({count})
                  </button>
                )
              })}
            </div>

            {/* Document Cards */}
            <div className="artifact-card-list">
              {!filteredItems.length && (
                <div className="rail-empty">
                  {searchQuery ? 'Không tìm thấy kết quả phù hợp.' : 'Chưa có bản lưu nào. Bạn có thể nhấn Tạo bản mới hoặc lưu trực tiếp từ Trò chuyện.'}
                </div>
              )}
              {filteredItems.map((item) => {
                const meta = kindMeta[item.kind] ?? { label: item.kind, icon: '📄', color: '#94a3b8', bg: 'rgba(255,255,255,0.06)' }
                const isSelected = selected?.id === item.id
                return (
                  <button
                    type="button"
                    className={`artifact-item-card ${isSelected ? 'artifact-item-card--active' : ''}`}
                    key={item.id}
                    disabled={busy}
                    onClick={() => choose(item)}
                    aria-current={isSelected}
                    title={item.title}
                  >
                    <div className="artifact-item-card__header">
                      <span className="artifact-item-card__icon" style={{ backgroundColor: meta.bg, color: meta.color }}>
                        {meta.icon}
                      </span>
                      <span className="artifact-item-card__title">{item.title || '(Chưa đặt tiêu đề)'}</span>
                      <span className="artifact-item-card__badge">v{item.revision}</span>
                    </div>
                    <div className="artifact-item-card__snippet">
                      {item.content ? item.content.slice(0, 90).replace(/[#*`>-]/g, '').trim() : 'Trống...'}
                    </div>
                    <div className="artifact-item-card__footer">
                      <span className="artifact-item-card__kind" style={{ color: meta.color }}>
                        {meta.label}
                      </span>
                      {item.is_archived && <span className="artifact-item-card__archived">Đã lưu trữ</span>}
                    </div>
                  </button>
                )
              })}
            </div>
          </aside>

          {/* Right Area: Antigravity-Level Editor & Preview Workbench */}
          <main className="artifact-editor-container">
            <form
              className="artifact-editor-form"
              onSubmit={(event) => {
                event.preventDefault()
                void save()
              }}
            >
              {/* Header Bar: Meta and View Mode Switch */}
              <div className="editor-top-bar">
                <div className="editor-meta-inputs">
                  <div className="editor-title-field">
                    <Input
                      id="artifact-title"
                      required
                      size="large"
                      maxLength={240}
                      value={title}
                      disabled={busy}
                      placeholder="Nhập tiêu đề tài liệu / ghi chú..."
                      onChange={(_, data) => setTitle(data.value)}
                      className="artifact-title-glass-input"
                      style={{ width: '100%', fontWeight: 600, fontSize: '16px' }}
                    />
                  </div>
                  <div className="editor-kind-field">
                    <Select
                      id="artifact-kind"
                      value={kind}
                      disabled={busy}
                      onChange={(_, data) => setKind(data.value)}
                      className="artifact-kind-glass-select"
                    >
                      <option value="note">📝 Ghi chú</option>
                      <option value="checklist">✅ Checklist</option>
                      <option value="plan">🎯 Kế hoạch</option>
                      <option value="report">📑 Báo cáo</option>
                      <option value="quiz">💡 Ôn tập</option>
                    </Select>
                  </div>
                </div>

                {/* View Mode Switch */}
                <div className="editor-view-modes">
                  <button
                    type="button"
                    className={`view-mode-btn glass-view-mode-btn ${viewMode === 'edit' ? 'view-mode-btn--active glass-view-mode-btn--active' : ''}`}
                    onClick={() => setViewMode('edit')}
                    title="Chế độ soạn thảo toàn màn hình"
                  >
                    <Edit20Regular /> Soạn thảo
                  </button>
                  <button
                    type="button"
                    className={`view-mode-btn glass-view-mode-btn ${viewMode === 'split' ? 'view-mode-btn--active glass-view-mode-btn--active' : ''}`}
                    onClick={() => setViewMode('split')}
                    title="Chế độ chia đôi màn hình: Soạn thảo & Bản xem trực tiếp"
                  >
                    ⚡ Song song
                  </button>
                  <button
                    type="button"
                    className={`view-mode-btn glass-view-mode-btn ${viewMode === 'preview' ? 'view-mode-btn--active glass-view-mode-btn--active' : ''}`}
                    onClick={() => setViewMode('preview')}
                    title="Chế độ đọc bản hoàn thiện"
                  >
                    <Eye20Regular /> Bản đọc
                  </button>
                </div>
              </div>

              {/* Markdown Quick Toolbar */}
              {(viewMode === 'edit' || viewMode === 'split') && (
                <div className="markdown-toolbar glass-markdown-toolbar">
                  <div className="toolbar-group">
                    <Tooltip content="Tiêu đề 1" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('# ', '', 'Tiêu đề lớn')}>
                        H1
                      </button>
                    </Tooltip>
                    <Tooltip content="Tiêu đề 2" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('## ', '', 'Tiêu đề phụ')}>
                        H2
                      </button>
                    </Tooltip>
                    <Tooltip content="Tiêu đề 3" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('### ', '', 'Tiểu mục')}>
                        H3
                      </button>
                    </Tooltip>
                  </div>

                  <div className="toolbar-divider metallic-toolbar-divider" />

                  <div className="toolbar-group">
                    <Tooltip content="Chữ đậm (Bold)" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('**', '**', 'chữ đậm')}>
                        <TextBold20Regular />
                      </button>
                    </Tooltip>
                    <Tooltip content="Chữ nghiêng (Italic)" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('*', '*', 'chữ nghiêng')}>
                        <TextItalic20Regular />
                      </button>
                    </Tooltip>
                  </div>

                  <div className="toolbar-divider metallic-toolbar-divider" />

                  <div className="toolbar-group">
                    <Tooltip content="Danh sách dấu chấm" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('- ', '', 'Mục danh sách')}>
                        • Danh sách
                      </button>
                    </Tooltip>
                    <Tooltip content="Danh sách công việc (Task checklist)" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('- [ ] ', '', 'Công việc cần làm')}>
                        ☑ Task
                      </button>
                    </Tooltip>
                    <Tooltip content="Khối trích dẫn" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('> ', '', 'Nội dung trích dẫn')}>
                        ” Quote
                      </button>
                    </Tooltip>
                  </div>

                  <div className="toolbar-divider metallic-toolbar-divider" />

                  <div className="toolbar-group">
                    <Tooltip content="Khối mã nguồn (Code block)" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('```markdown\n', '\n```', 'code here')}>
                        <Code20Regular /> Code
                      </button>
                    </Tooltip>
                    <Tooltip content="Chèn bảng biểu (Table)" relationship="label">
                      <button
                        type="button"
                        className="toolbar-btn glass-toolbar-btn"
                        onClick={() =>
                          insertMarkdown(
                            '| Cột 1 | Cột 2 | Cột 3 |\n|---|---|---|\n| Dữ liệu 1 | Dữ liệu 2 | Dữ liệu 3 |\n'
                          )
                        }
                      >
                        <Table20Regular /> Bảng
                      </button>
                    </Tooltip>
                    <Tooltip content="Chèn liên kết (Link)" relationship="label">
                      <button type="button" className="toolbar-btn glass-toolbar-btn" onClick={() => insertMarkdown('[', '](https://)', 'Tên liên kết')}>
                        <Link20Regular /> Link
                      </button>
                    </Tooltip>
                  </div>
                </div>
              )}

              {/* Main Content Workspace (Split / Full Editor / Full Preview) */}
              <div className={`editor-body-area editor-body-area--${viewMode}`}>
                {/* Editor Pane */}
                {(viewMode === 'edit' || viewMode === 'split') && (
                  <div className="editor-pane">
                    <Textarea
                      ref={textareaRef}
                      id="artifact-content"
                      className="artifact-textarea-pro"
                      required
                      value={content}
                      maxLength={100000}
                      disabled={busy}
                      rows={22}
                      resize="none"
                      placeholder="# Tiêu đề tài liệu&#10;&#10;Soạn thảo nội dung ghi chú, checklist hoặc báo cáo chi tiết tại đây (hỗ trợ đầy đủ cú pháp Markdown)..."
                      onChange={(_, data) => setContent(data.value)}
                    />
                  </div>
                )}

                {/* Preview Pane */}
                {(viewMode === 'preview' || viewMode === 'split') && (
                  <div className="preview-pane">
                    <div className="preview-pane-header">
                      <span>Bản xem trước trực tiếp (Antigravity Typography)</span>
                      <Badge appearance="tint" color="brand">Markdown Rendered</Badge>
                    </div>
                    <div className="artifact-preview-content markdown-body">
                      {content.trim() ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {content}
                        </ReactMarkdown>
                      ) : (
                        <div className="preview-empty-notice">
                          <p>Bản xem trước sẽ hiển thị tức thì khi bạn nhập nội dung vào khung soạn thảo.</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Document Statistics Bar */}
              <div className="document-stats-bar">
                <div className="stats-group">
                  <span className="stat-chip">📝 {stats.words} từ</span>
                  <span className="stat-chip">🔤 {stats.chars} ký tự</span>
                  <span className="stat-chip">
                    <Clock20Regular style={{ fontSize: '13px', verticalAlign: 'middle', marginRight: '3px' }} />
                    ~{stats.readTime} phút đọc
                  </span>
                  <span className="stat-chip">📑 {stats.lines} dòng</span>
                  {selected && (
                    <span className="stat-chip stat-chip--version">
                      Phiên bản v{selected.revision}
                    </span>
                  )}
                </div>
                <div className="stats-shortcut-hint">
                  Nhấn <kbd>Ctrl</kbd> + <kbd>S</kbd> để lưu nhanh
                </div>
              </div>

              {/* Action Bar */}
              <div className="artifact-bottom-bar">
                <div className="actions-left">
                  <Button
                    type="submit"
                    appearance="primary"
                    disabled={busy || !title.trim() || !content.trim()}
                    icon={busy ? undefined : <Checkmark20Regular />}
                  >
                    {busy ? 'Đang lưu…' : selected ? 'Cập nhật bản này' : 'Lưu bản mới'}
                  </Button>

                  {selected && (
                    <>
                      <Select
                        aria-label="Định dạng xuất bản đã lưu"
                        value={exportFormat}
                        onChange={event => setExportFormat(event.target.value as 'md' | 'docx' | 'pdf')}
                        style={{ minWidth: 130 }}
                      >
                        <option value="md">Markdown (.md)</option>
                        <option value="docx">Word (.docx)</option>
                        <option value="pdf">PDF (.pdf)</option>
                      </Select>
                      {hasUnsavedChanges ? (
                        <Button disabled icon={<ArrowDownload20Regular />} appearance="secondary">
                          Lưu trước khi xuất
                        </Button>
                      ) : (
                        <Button
                          as="a"
                          href={`/api/artifacts/${selected.id}/export?format=${exportFormat}`}
                          download={`${selected.title.replace(/\s+/g, '_') || 'artifact'}.${exportFormat}`}
                          icon={<ArrowDownload20Regular />}
                          appearance="secondary"
                        >
                          Xuất bản đã lưu
                        </Button>
                      )}
                      <Button
                        disabled={busy}
                        icon={<Archive20Regular />}
                        appearance="subtle"
                        onClick={() => void save(!selected.is_archived)}
                      >
                        {selected.is_archived ? 'Khôi phục bản này' : 'Cất bản này'}
                      </Button>
                    </>
                  )}
                </div>

                {notice && (
                  <div className="artifact-success-notice">
                    <Checkmark20Regular style={{ verticalAlign: 'middle', marginRight: '6px' }} />
                    {notice}
                  </div>
                )}
              </div>
            </form>
          </main>
        </div>
      )}
    </section>
  )
}
