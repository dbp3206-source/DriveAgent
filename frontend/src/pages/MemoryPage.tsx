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

export function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải bộ nhớ.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function search(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return load()
    try {
      const result = await api<{ memories: MemoryItem[] }>(`/api/memories/search?q=${encodeURIComponent(query)}`)
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
        <EmptyState title="Chưa có bộ nhớ" description="Bạn có thể tự lưu một fact hoặc để agent ghi nhớ trong khi trò chuyện." />
      ) : null}
      <div className="memory-list">
        {items.map((item) => (
          <article key={item.id} className="memory-row">
            <div className="memory-row__type"><Badge appearance="tint">{kindLabels[item.kind]}</Badge></div>
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
