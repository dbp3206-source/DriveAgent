import { Button, Input, Select, Textarea } from '@fluentui/react-components'
import { Add20Regular, Archive20Regular, ArrowDownload20Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
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

const kindLabels: Record<string, string> = {
  note: 'Ghi chú',
  checklist: 'Checklist',
  quiz: 'Ôn tập',
  plan: 'Kế hoạch',
  report: 'Báo cáo',
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

  async function save(archived = selected?.is_archived ?? false) {
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
      setNotice(`Đã lưu phiên bản ${item.revision} thành công.`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không lưu được.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="stack-page">
      <div className="page-heading">
        <div>
          <h2>Kết quả của bạn, dùng lại được</h2>
          <p>Lưu và chỉnh sửa ghi chú, checklist, bộ câu hỏi hay kế hoạch. Dữ liệu được bảo vệ an toàn trên tài khoản của bạn.</p>
        </div>
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <LoadingState label="Đang tải bản lưu…" />
      ) : (
        <div className="artifact-workbench">
          <aside className="artifact-list">
            <Button
              appearance="primary"
              icon={<Add20Regular />}
              disabled={busy}
              onClick={() => choose(null)}
              style={{ width: '100%', marginBottom: '12px' }}
            >
              Tạo bản mới
            </Button>
            <p className="rail-caption">Danh sách bản lưu</p>
            {!items.length && (
              <p className="rail-empty">Chưa có bản lưu nào. Bạn cũng có thể lưu câu trả lời từ Trò chuyện.</p>
            )}
            <div className="artifact-card-list">
              {items.map((item) => (
                <button
                  type="button"
                  className={`artifact-item-card ${selected?.id === item.id ? 'artifact-item-card--active' : ''}`}
                  key={item.id}
                  disabled={busy}
                  onClick={() => choose(item)}
                  aria-current={selected?.id === item.id}
                  title={item.title}
                >
                  <div className="artifact-item-card__header">
                    <span className="artifact-item-card__title">{item.title}</span>
                    <span className="artifact-item-card__badge">v{item.revision}</span>
                  </div>
                  <div className="artifact-item-card__footer">
                    <span className="artifact-item-card__kind">{kindLabels[item.kind] ?? item.kind}</span>
                    {item.is_archived && <span className="artifact-item-card__archived">Đã cất</span>}
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <form className="artifact-editor" onSubmit={(event) => { event.preventDefault(); void save() }}>
            <div className="artifact-form-grid">
              <div className="artifact-field">
                <label htmlFor="artifact-title" className="artifact-label">Tiêu đề bản lưu</label>
                <Input
                  id="artifact-title"
                  required
                  maxLength={240}
                  value={title}
                  disabled={busy}
                  placeholder="Nhập tiêu đề ghi chú, kế hoạch..."
                  onChange={(_, data) => setTitle(data.value)}
                />
              </div>
              <div className="artifact-field artifact-field--kind">
                <label htmlFor="artifact-kind" className="artifact-label">Loại kết quả</label>
                <Select
                  id="artifact-kind"
                  value={kind}
                  disabled={busy}
                  onChange={(_, data) => setKind(data.value)}
                >
                  <option value="note">Ghi chú</option>
                  <option value="checklist">Checklist</option>
                  <option value="quiz">Ôn tập</option>
                  <option value="plan">Kế hoạch</option>
                  <option value="report">Báo cáo</option>
                </Select>
              </div>
            </div>

            <div className="artifact-field">
              <label htmlFor="artifact-content" className="artifact-label">
                Nội dung (hỗ trợ cú pháp Markdown)
              </label>
              <Textarea
                id="artifact-content"
                className="artifact-textarea"
                required
                value={content}
                maxLength={100000}
                disabled={busy}
                rows={18}
                resize="vertical"
                placeholder="# Tiêu đề tài liệu&#10;&#10;Nội dung chi tiết..."
                onChange={(_, data) => setContent(data.value)}
              />
            </div>

            <div className="artifact-actions">
              <Button
                type="submit"
                appearance="primary"
                disabled={busy || !title.trim() || !content.trim()}
              >
                {busy ? 'Đang lưu…' : 'Lưu bản này'}
              </Button>
              {selected && (
                <>
                  <Button
                    as="a"
                    href={`/api/artifacts/${selected.id}/export`}
                    download
                    icon={<ArrowDownload20Regular />}
                  >
                    Tải Markdown
                  </Button>
                  <Button
                    disabled={busy}
                    icon={<Archive20Regular />}
                    onClick={() => void save(!selected.is_archived)}
                  >
                    {selected.is_archived ? 'Khôi phục bản này' : 'Cất bản này'}
                  </Button>
                </>
              )}
            </div>
            {notice && <p className="artifact-notice" role="status">✓ {notice}</p>}
            <p className="measurement-note">
              Bản lưu được bảo vệ phiên bản và chống ghi đè không mong muốn. Tải xuống là tệp markdown hoàn chỉnh.
            </p>
          </form>
        </div>
      )}
    </section>
  )
}
