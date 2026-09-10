import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Textarea,
} from '@fluentui/react-components'
import {
  ArrowReset20Regular,
  ArrowTrendingLines20Regular,
  Chat16Regular,
  Checkmark16Regular,
  ChevronUp16Regular,
  Delete16Regular,
  DocumentBulletList20Regular,
  DocumentLink24Regular,
  Mail20Regular,
  Search20Regular,
  Send24Regular,
  WeatherSunny20Regular,
} from '@fluentui/react-icons'
import { FormEvent, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, ApiError } from '../api'
import { EmptyState, ErrorState } from '../components/AsyncState'
import { ExecutionTrace } from '../components/ExecutionTrace'
import { CreationProposal, type Proposal } from '../components/CreationProposal'
import {
  DocumentExportApproval,
  type PreparedDocumentExport,
} from '../components/DocumentExportApproval'
import { AVAILABLE_MODELS, type ModelOption } from '../modelOptions'

function formatRelativeTime(isoDate: string): string {
  try {
    const now = Date.now()
    const time = new Date(isoDate).getTime()
    if (isNaN(time)) return ''
    const diff = Math.max(0, Math.floor((now - time) / 1000))
    if (diff < 60) return 'Vừa xong'
    if (diff < 3600) return `${Math.floor(diff / 60)}m`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`
    if (diff < 2592000) return `${Math.floor(diff / 86400)}d`
    return `${Math.floor(diff / 2592000)}mo`
  } catch {
    return ''
  }
}
import type { ChatMessage, ChatSession, Citation } from '../types'

interface ChatResult {
  proposals?: Proposal[]
  session_id: string
  message_id: string
  answer: string
  citations: Citation[]
  trace: Array<Record<string, unknown>>
}

const prompts = [
  'Tìm tài liệu học tập trong Drive của tôi',
  'Tóm tắt tệp mới chỉnh sửa gần đây nhất',
  'Quét thư Gmail chưa đọc từ tối qua và tóm tắt',
  'Tôi đã lưu sở thích trình bày nào?',
]

interface ChatPageProps {
  onBusyChange?: (busy: boolean) => void
}

export function ChatPage({ onBusyChange }: ChatPageProps = {}) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [showAllSessions, setShowAllSessions] = useState(false)
  const [sessionId, setSessionIdState] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('drive_agent_active_session') || null
    } catch {
      return null
    }
  })
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInputState] = useState<string>(() => {
    try {
      return sessionStorage.getItem('drive_agent_draft_input') || ''
    } catch {
      return ''
    }
  })
  const [busy, setBusy] = useState(false)
  const [briefingBusy, setBriefingBusy] = useState(false)
  const [error, setError] = useState('')
  const [savedMessages, setSavedMessages] = useState<Set<string>>(new Set())
  const [savingMessage, setSavingMessage] = useState<string | null>(null)
  const [exportingDoc, setExportingDoc] = useState<string | null>(null)
  const [preparedDocs, setPreparedDocs] = useState<Record<string, PreparedDocumentExport>>({})
  const [feedbackByMessage, setFeedbackByMessage] = useState<Record<string, 'helpful' | 'not_helpful'>>({})
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const freshlyCreatedSession = useRef<string | null>(null)
  const [lastUserPrompt, setLastUserPrompt] = useState('')
  const [selectedModel, setSelectedModel] = useState<ModelOption>(AVAILABLE_MODELS[0]!)
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const [usageDialogOpen, setUsageDialogOpen] = useState(false)

  const setInput = (val: string) => {
    setInputState(val)
    try {
      if (val) {
        sessionStorage.setItem('drive_agent_draft_input', val)
      } else {
        sessionStorage.removeItem('drive_agent_draft_input')
      }
    } catch {
      // ignore
    }
  }

  const setSessionId = (id: string | null) => {
    setSessionIdState(id)
    try {
      if (id) {
        sessionStorage.setItem('drive_agent_active_session', id)
      } else {
        sessionStorage.removeItem('drive_agent_active_session')
      }
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    onBusyChange?.(busy || briefingBusy)
  }, [busy, briefingBusy, onBusyChange])

  useEffect(() => {
    api<ChatSession[]>('/api/chat/sessions').then(setSessions)
      .catch(() => setError('Chưa tải được lịch sử. Bạn vẫn có thể bắt đầu cuộc trò chuyện mới.'))
  }, [])

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      return
    }
    if (freshlyCreatedSession.current === sessionId) {
      freshlyCreatedSession.current = null
      return
    }
    let active = true
    api<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`)
      .then((rows) => { if (active) setMessages(rows) })
      .catch((caught: ApiError) => { if (active) setError(caught.message) })
    return () => { active = false }
  }, [sessionId])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'auto', block: 'nearest' })
  }, [messages, busy])

  async function submit(event?: FormEvent, customText?: string) {
    if (event) event.preventDefault()
    const content = (customText !== undefined ? customText : input).trim()
    if (!content || busy) return
    setLastUserPrompt(content)
    setInput('')
    setError('')
    setBusy(true)
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content,
      citations: [],
      trace: [],
      created_at: new Date().toISOString(),
    }
    setMessages((current) => [...current, optimistic])
    try {
      const result = await api<ChatResult>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
          model: selectedModel.id,
        }),
      })
      if (!sessionId) freshlyCreatedSession.current = result.session_id
      setSessionId(result.session_id)
      setMessages((current) => [
        ...current,
        {
          id: result.message_id,
          role: 'assistant',
          content: result.answer,
          citations: result.citations,
          trace: result.trace,
          proposals: result.proposals,
          created_at: new Date().toISOString(),
        },
      ])
      api<ChatSession[]>('/api/chat/sessions').then(setSessions)
        .catch(() => setError('Đã nhận câu trả lời, nhưng chưa cập nhật được danh sách lịch sử.'))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể gửi câu hỏi.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteSession(id: string) {
    if (!window.confirm('Bạn có chắc muốn xóa cuộc trò chuyện này?')) return
    try {
      await api(`/api/chat/sessions/${id}`, { method: 'DELETE' })
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (sessionId === id) {
        setSessionId(null)
        setMessages([])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể xóa phiên trò chuyện.')
    }
  }

  async function fetchMorningBriefing() {
    setBriefingBusy(true)
    setError('')
    try {
      const result = await api<{ session_id: string; title: string; answer: string; message_id: string }>(
        '/api/chat/morning-briefing',
        { method: 'POST' }
      )
      setSessionId(result.session_id)
      setMessages([
        {
          id: result.message_id,
          role: 'assistant',
          content: result.answer,
          citations: [],
          trace: [],
          created_at: new Date().toISOString(),
        },
      ])
      api<ChatSession[]>('/api/chat/sessions').then(setSessions).catch(() => {})
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể tạo bản tin sáng.')
    } finally {
      setBriefingBusy(false)
    }
  }

  async function exportToGoogleDoc(message: ChatMessage) {
    setExportingDoc(message.id)
    setError('')
    try {
      const firstLine = (message.content.split('\n')[0] ?? '').replace(/^#+\s*/, '').slice(0, 50).trim()
      const title = firstLine ? `DriveAgent: ${firstLine}` : `Tài liệu DriveAgent - ${new Date().toLocaleDateString('vi-VN')}`
      const result = await api<{
        data: { operation_id: string; digest: string; state: string }
      }>(
        '/api/documents/prepare',
        {
          method: 'POST',
          body: JSON.stringify({
            request_key: `doc-export-${message.id}`,
            action: 'create',
            document: {
              title,
              blocks: [{ text: message.content, style: 'NORMAL_TEXT' }],
            },
          }),
        }
      )
      setPreparedDocs(prev => ({
        ...prev,
        [message.id]: { ...result.data, title },
      }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể xuất Google Doc.')
    } finally {
      setExportingDoc(null)
    }
  }

  async function saveAnswer(message: ChatMessage) {
    setSavingMessage(message.id); setError('')
    const sources = message.citations.map((citation, index) =>
      `[${index + 1}] ${citation.file_name}: ${citation.web_view_link ?? 'Không có liên kết'}`).join('\n')
    try {
      await api('/api/artifacts', {method:'POST', body:JSON.stringify({
        title:message.content.slice(0, 80).trim(), content:message.content + (sources ? `\n\n## Nguồn\n\n${sources}` : ''),
        kind:'note', creation_key:message.id,
      })})
      setSavedMessages(previous => new Set([...previous, message.id]))
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không lưu được câu trả lời.') }
    finally { setSavingMessage(null) }
  }

  async function rateAnswer(messageId: string, rating: 'helpful' | 'not_helpful') {
    setError('')
    try {
      await api(`/api/harness/feedback/${messageId}`, {
        method: 'POST',
        body: JSON.stringify({rating, reasons: []}),
      })
      setFeedbackByMessage(current => ({...current, [messageId]: rating}))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa lưu được đánh giá.')
    }
  }

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.trim().toLowerCase())
  )
  const displayedSessions = showAllSessions ? filteredSessions : filteredSessions.slice(0, 10)
  const remainingCount = filteredSessions.length - 10

  return (
    <div className="chat-layout">
      <aside className="session-rail" aria-label="Lịch sử trò chuyện">
        <div className="rail-top-actions">
          <p className="rail-heading">Góc làm việc</p>
          <Button
            appearance="primary"
            disabled={busy || briefingBusy}
            onClick={() => { setSessionId(null); setMessages([]); setError('') }}
            style={{ width: '100%', marginBottom: '8px' }}
          >
            Cuộc trò chuyện mới
          </Button>
          <Button
            appearance="outline"
            icon={briefingBusy ? <Spinner size="tiny" /> : <WeatherSunny20Regular />}
            disabled={busy || briefingBusy}
            onClick={() => void fetchMorningBriefing()}
            style={{ width: '100%', marginBottom: '12px' }}
            title="Tự động quét Gmail chưa đọc và tài liệu Drive mới cập nhật tối qua"
          >
            {briefingBusy ? 'Đang tổng hợp…' : 'Bản tin sáng'}
          </Button>
          <Input
            className="session-search-input"
            aria-label="Tìm kiếm trò chuyện"
            placeholder="Tìm kiếm trò chuyện…"
            value={searchQuery}
            onChange={(_, data) => setSearchQuery(data.value)}
            contentBefore={<Search20Regular />}
            style={{ width: '100%' }}
          />
        </div>

        <div className="session-list">
          <div className="rail-caption-row">
            <span className="rail-caption">Trò chuyện gần đây</span>
            <span className="rail-caption-count">{filteredSessions.length}</span>
          </div>

          {filteredSessions.length === 0 ? (
            <p className="rail-empty">
              {searchQuery ? 'Không tìm thấy cuộc trò chuyện nào.' : 'Các cuộc trò chuyện sẽ được lưu ở đây.'}
            </p>
          ) : null}

          {displayedSessions.map((session) => (
            <div
              key={session.id}
              className={`session-card ${sessionId === session.id ? 'session-card--active' : ''}`}
              onClick={() => setSessionId(session.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setSessionId(session.id)
                }
              }}
            >
              <div className="session-card__body">
                <div className="session-card__top">
                  <span className="session-card__title" title={session.title}>
                    {session.title}
                  </span>
                  <span className="session-card__time">
                    {formatRelativeTime(session.updated_at)}
                  </span>
                </div>
                <div className="session-card__bottom">
                  <span className="session-card__tag">
                    <Chat16Regular /> DriveAgent
                  </span>
                  {sessionId === session.id ? (
                    <span className="session-card__active-dot" title="Đang mở" />
                  ) : null}
                </div>
              </div>
              <button
                type="button"
                className="session-card__delete"
                title="Xóa cuộc trò chuyện này"
                aria-label={`Xóa ${session.title}`}
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  void deleteSession(session.id)
                }}
              >
                <Delete16Regular />
              </button>
            </div>
          ))}

          {filteredSessions.length > 10 ? (
            <Button
              appearance="subtle"
              size="small"
              className="session-expand-btn"
              onClick={() => setShowAllSessions((prev) => !prev)}
            >
              {showAllSessions ? 'Thu gọn (chỉ hiện 10 phiên gần nhất)' : `Xem thêm (${remainingCount} cuộc trò chuyện cũ hơn)`}
            </Button>
          ) : null}
        </div>
      </aside>

      <section className="chat-main" aria-label="Nội dung trò chuyện">
        <Select
          className="session-picker"
          aria-label="Chọn cuộc trò chuyện"
          value={sessionId ?? ''}
          disabled={busy}
          onChange={(_, data) => { setSessionId(data.value || null); setMessages([]); setError('') }}
        >
          <option value="">Cuộc trò chuyện mới</option>
          {sessions.map((session) => <option key={session.id} value={session.id}>{session.title}</option>)}
        </Select>

        <div className="message-scroll" aria-live="polite">
          {messages.length === 0 ? (
            <EmptyState
              title="Bạn muốn bắt đầu từ đâu?"
              description="Nêu việc bạn cần hoàn thành hoặc chọn một gợi ý. DriveAgent sẽ tìm nguồn, giải thích và xin bạn duyệt trước mọi thao tác ghi."
              action={
                <div className="prompt-grid">
                  {prompts.map((prompt) => (
                    <button type="button" key={prompt} onClick={() => { setInput(prompt); inputRef.current?.focus() }}>
                      {prompt}
                    </button>
                  ))}
                </div>
              }
            />
          ) : (
            messages.map((message) => (
              <article key={message.id} className={`message message--${message.role}`}>
                <div className="message__meta">
                  {message.role === 'assistant' ? 'DriveAgent' : 'Bạn'}
                </div>
                <div className="message__content">
                  {message.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
                      img: ({ alt }) => <span className="omitted-image">[Hình ảnh: {alt || 'không tải tự động'}]</span>,
                      a: ({ href, children }) => /^https?:\/\//i.test(href ?? '')
                        ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                        : <span>{children}</span>,
                    }}>{message.content}</ReactMarkdown>
                  ) : message.content}
                </div>

                {message.citations.length > 0 ? (
                  <div className="citations" aria-label="Nguồn trích dẫn">
                    {message.citations.map((citation, index) => (
                      <a
                        key={`${citation.file_id}-${citation.chunk_index}`}
                        href={/^https?:\/\//i.test(citation.web_view_link ?? '') ? citation.web_view_link! : undefined}
                        target="_blank"
                        rel="noreferrer"
                        className="citation-link"
                      >
                        <DocumentLink24Regular />
                        <span>[{index + 1}] {citation.file_name}</span>
                      </a>
                    ))}
                  </div>
                ) : null}

                {message.trace.length > 0 ? (
                  <ExecutionTrace trace={message.trace} />
                ) : null}

                {message.proposals?.map(proposal => <CreationProposal key={proposal.id} proposal={proposal} />)}

                {message.role === 'assistant' && (
                  <div className="message-action-toolbar">
                    <Button
                      appearance="subtle"
                      size="small"
                      disabled={savingMessage !== null || savedMessages.has(message.id)}
                      onClick={() => void saveAnswer(message)}
                    >
                      {savedMessages.has(message.id) ? 'Đã lưu ghi chú' : savingMessage === message.id ? 'Đang lưu…' : 'Lưu ghi chú'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<DocumentBulletList20Regular />}
                      disabled={exportingDoc === message.id || Boolean(preparedDocs[message.id])}
                      onClick={() => void exportToGoogleDoc(message)}
                    >
                      {exportingDoc === message.id ? 'Đang chuẩn bị…' : 'Xuất Google Doc'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<Mail20Regular />}
                      onClick={() => {
                        setInput(`Hãy soạn email tóm tắt gửi cho đối tác với nội dung: ${message.content.slice(0, 160)}...`)
                        inputRef.current?.focus()
                      }}
                    >
                      Soạn gửi Gmail
                    </Button>
                    <span className="message-feedback" aria-label="Đánh giá câu trả lời">
                      <button
                        type="button"
                        aria-pressed={feedbackByMessage[message.id] === 'helpful'}
                        onClick={() => void rateAnswer(message.id, 'helpful')}
                      >
                        Hữu ích
                      </button>
                      <button
                        type="button"
                        aria-pressed={feedbackByMessage[message.id] === 'not_helpful'}
                        onClick={() => void rateAnswer(message.id, 'not_helpful')}
                      >
                        Chưa ổn
                      </button>
                    </span>
                  </div>
                )}
                {preparedDocs[message.id] ? (
                  <DocumentExportApproval prepared={preparedDocs[message.id]!} />
                ) : null}
              </article>
            ))
          )}

          {busy ? (
            <div className="agent-working">
              <Spinner size="tiny" /> Agent đang xử lý, kiểm tra nguồn và chuẩn bị câu trả lời…
            </div>
          ) : null}
          <div ref={endRef} />
        </div>

        {error ? (
          <div className="chat-error-banner">
            <ErrorState message={error} />
            {lastUserPrompt && (
              <Button
                appearance="outline"
                size="small"
                icon={<ArrowReset20Regular />}
                onClick={() => void submit(undefined, lastUserPrompt)}
                disabled={busy}
              >
                Thử lại câu hỏi vừa rồi
              </Button>
            )}
          </div>
        ) : null}

        <form className="composer-container" onSubmit={(e) => void submit(e)}>
          <Textarea
            ref={inputRef}
            id="chat-input"
            name="message"
            className="composer-textarea"
            resize="vertical"
            value={input}
            onChange={(_, data) => setInput(data.value)}
            placeholder="Hỏi về tài liệu Drive, tóm tắt Gmail, hoặc yêu cầu soạn thảo tài liệu…"
            aria-label="Nội dung câu hỏi"
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />

          <div className="composer-bottom-bar">
            <div className="model-selector-wrapper">
              <button
                type="button"
                className="model-selector-btn"
                onClick={() => setModelMenuOpen((prev) => !prev)}
                aria-expanded={modelMenuOpen}
                aria-haspopup="true"
                title="Chọn model để trả lời (ngăn cạn quota)"
              >
                <span className="model-plus-icon">+</span>
                <span className="model-btn-name">{selectedModel.name}</span>
                <ChevronUp16Regular className={`model-chevron ${modelMenuOpen ? 'model-chevron--open' : ''}`} />
              </button>

              {modelMenuOpen && (
                <div className="model-selector-popover" role="menu">
                  <div className="model-popover-header">Model</div>
                  <div className="model-popover-list">
                    {AVAILABLE_MODELS.map((m) => (
                      <div
                        key={m.id}
                        className={`model-option-item ${selectedModel.id === m.id ? 'model-option-item--active' : ''}`}
                        onClick={() => {
                          setSelectedModel(m)
                          setModelMenuOpen(false)
                        }}
                        role="menuitem"
                        title={m.description}
                      >
                        <div className="model-option-left">
                          <span className="model-option-name">{m.name}</span>
                          <div className="model-option-badges">
                            <span className="model-badge model-badge--context">{m.availability}</span>
                            <span className="model-badge model-badge--speed">{m.speed}</span>
                          </div>
                        </div>
                        {selectedModel.id === m.id && <Checkmark16Regular className="model-check-icon" />}
                      </div>
                    ))}
                  </div>
                  <div className="model-popover-divider" />
                  <button
                    type="button"
                    className="model-view-usage-btn"
                    onClick={() => {
                      setModelMenuOpen(false)
                      setUsageDialogOpen(true)
                    }}
                  >
                    <ArrowTrendingLines20Regular />
                    <span>Thông tin model</span>
                  </button>
                </div>
              )}
            </div>

            <Button
              type="submit"
              appearance="primary"
              className="composer-send-btn"
              icon={<Send24Regular />}
              disabled={!input.trim() || busy}
            >
              Gửi
            </Button>
          </div>
        </form>

        <Dialog open={usageDialogOpen} onOpenChange={(_, data) => setUsageDialogOpen(data.open)}>
          <DialogSurface>
            <DialogBody>
              <DialogTitle>Model đang dùng</DialogTitle>
              <DialogContent>
                <div className="usage-dialog-content">
                  <p><strong>Model hiện tại:</strong> {selectedModel.name} (<code>{selectedModel.id}</code>)</p>
                  <p>{selectedModel.description}</p>
                  <p className="usage-dialog-note">
                    DriveAgent không suy đoán hạn mức của Google. Quota thực tế phụ thuộc
                    project và được báo bằng lỗi có Request ID khi nhà cung cấp từ chối.
                  </p>
                </div>
              </DialogContent>
              <DialogActions>
                <Button appearance="primary" onClick={() => setUsageDialogOpen(false)}>Đóng</Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>

        <MessageBar intent="info">
          <MessageBarBody>
            Tất cả thao tác ghi và gửi email đều yêu cầu xác nhận 2 pha từ bạn (Human-in-the-Loop).
          </MessageBarBody>
        </MessageBar>
      </section>
    </div>
  )
}
