import {
  Button,
  MessageBar,
  MessageBarBody,
  Spinner,
  Select,
  Textarea,
} from '@fluentui/react-components'
import { DocumentLink24Regular, Send24Regular } from '@fluentui/react-icons'
import { FormEvent, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { EmptyState, ErrorState } from '../components/AsyncState'
import type { ChatMessage, ChatSession, Citation } from '../types'

interface ChatResult {
  session_id: string
  message_id: string
  answer: string
  citations: Citation[]
  trace: Array<Record<string, unknown>>
}

const prompts = [
  'Tìm các tài liệu nói về kế hoạch quý này',
  'Tóm tắt tệp mới chỉnh sửa gần đây nhất',
  'Tôi đã lưu sở thích trình bày nào?',
]

export function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api<ChatSession[]>('/api/chat/sessions').then(setSessions).catch(() => setSessions([]))
  }, [])

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      return
    }
    let active = true
    api<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`)
      .then((rows) => { if (active) setMessages(rows) })
      .catch((caught: ApiError) => { if (active) setError(caught.message) })
    return () => { active = false }
  }, [sessionId])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function submit(event: FormEvent) {
    event.preventDefault()
    const content = input.trim()
    if (!content || busy) return
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
        body: JSON.stringify({ message: content, session_id: sessionId }),
      })
      setSessionId(result.session_id)
      setMessages((current) => [
        ...current,
        {
          id: result.message_id,
          role: 'assistant',
          content: result.answer,
          citations: result.citations,
          trace: result.trace,
          created_at: new Date().toISOString(),
        },
      ])
      const fresh = await api<ChatSession[]>('/api/chat/sessions')
      setSessions(fresh)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể gửi câu hỏi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat-layout">
      <aside className="session-rail" aria-label="Lịch sử trò chuyện">
        <Button appearance="primary" disabled={busy} onClick={() => { setSessionId(null); setMessages([]); setError('') }}>
          Cuộc trò chuyện mới
        </Button>
        <div className="session-list">
          {sessions.map((session) => (
            <button
              type="button"
              disabled={busy}
              key={session.id}
              className={`session-item ${sessionId === session.id ? 'session-item--active' : ''}`}
              onClick={() => setSessionId(session.id)}
            >
              <strong>{session.title}</strong>
              <span>{new Date(session.updated_at).toLocaleDateString('vi-VN')}</span>
            </button>
          ))}
        </div>
      </aside>
      <section className="chat-main" aria-label="Nội dung trò chuyện">
        <Select className="session-picker" aria-label="Chọn cuộc trò chuyện" value={sessionId ?? ''} disabled={busy}
          onChange={(_, data) => { setSessionId(data.value || null); setMessages([]); setError('') }}>
          <option value="">Cuộc trò chuyện mới</option>
          {sessions.map((session) => <option key={session.id} value={session.id}>{session.title}</option>)}
        </Select>
        <div className="message-scroll" aria-live="polite">
          {messages.length === 0 ? (
            <EmptyState
              title="Bắt đầu từ tài liệu thật"
              description="DriveAgent có thể tìm tệp, đọc nội dung đã cấp quyền và trả lời kèm nguồn."
              action={
                <div className="prompt-grid">
                  {prompts.map((prompt) => (
                    <button type="button" key={prompt} onClick={() => setInput(prompt)}>
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
                <div className="message__content">{message.content}</div>
                {message.citations.length > 0 ? (
                  <div className="citations" aria-label="Nguồn trích dẫn">
                    {message.citations.map((citation, index) => (
                      <a
                        key={`${citation.file_id}-${citation.chunk_index}`}
                        href={citation.web_view_link ?? '#'}
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
                  <details className="trace-panel">
                    <summary>Xem quá trình xử lý</summary>
                    <pre>{JSON.stringify(message.trace, null, 2)}</pre>
                  </details>
                ) : null}
              </article>
            ))
          )}
          {busy ? (
            <div className="agent-working">
              <Spinner size="tiny" /> Agent đang lập kế hoạch và kiểm tra nguồn
            </div>
          ) : null}
          <div ref={endRef} />
        </div>
        {error ? <ErrorState message={error} /> : null}
        <form className="composer" onSubmit={submit}>
          <Textarea
            id="chat-input"
            name="message"
            resize="vertical"
            value={input}
            onChange={(_, data) => setInput(data.value)}
            placeholder="Hỏi về tệp Drive hoặc bộ nhớ của bạn"
            aria-label="Nội dung câu hỏi"
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />
          <Button
            type="submit"
            appearance="primary"
            icon={<Send24Regular />}
            disabled={!input.trim() || busy}
          >
            Gửi
          </Button>
        </form>
        <MessageBar intent="info">
          <MessageBarBody>
            Agent có thể sai. Hãy mở nguồn trích dẫn khi thông tin quan trọng.
          </MessageBarBody>
        </MessageBar>
      </section>
    </div>
  )
}
