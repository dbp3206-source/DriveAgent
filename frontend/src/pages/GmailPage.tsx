import { Button, Input, Spinner, Textarea } from '@fluentui/react-components'
import {
  Attach20Regular,
  ArrowClockwise20Regular,
  Open20Regular,
  Send20Regular,
} from '@fluentui/react-icons'
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, formatDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { EmailProposal, type EmailProposalData } from '../components/EmailProposal'
import { MailBodyViewer, SenderAvatar } from '../components/MailBodyViewer'
import { emailActionConfig, type EmailAction } from '../emailWorkflow.mjs'
import { classifyReplyNeed } from '../gmailTriage.mjs'
import { buildGmailQuery } from '../gmailQuery'

const GMAIL_STATUSES: Array<{id: string; label: string}> = [
  {id: 'all', label: 'Tất cả'}, {id: 'unread', label: 'Chưa đọc'}, {id: 'read', label: 'Đã đọc'},
]
const GMAIL_PERIODS: Array<{id: string; label: string}> = [
  {id: '1d', label: '1 ngày'}, {id: '3d', label: '3 ngày'}, {id: '7d', label: '1 tuần'}, {id: '30d', label: '1 tháng'}, {id: 'all', label: 'Mọi thời điểm'},
]
const GMAIL_SCOPES: Array<{id: string; label: string}> = [
  {id: 'inbox', label: 'Hộp thư đến'}, {id: 'sent', label: 'Đã gửi'}, {id: 'everywhere', label: 'Toàn bộ thư'},
]

type MailSummary = {
  id: string
  thread_id: string
  sender: string
  subject: string
  date: string
  snippet: string
  unread: boolean
  has_attachment: boolean
}

type MailList = { messages: MailSummary[]; total_found: number; total_is_estimate?: boolean; next_page_token?: string | null }
type ThreadMessage = {
  id: string
  sender: string
  recipient: string
  date: string
  subject: string
  body: string
  plain_body?: string
  html_body?: string
  external_image_sources?: Record<string, string>
  presentation_mode: 'faithful_text' | 'readable_text' | 'safe_html' | 'calendar_text' | 'unsupported'
  reply_to: string
  message_id_header: string
  references: string
  unread: boolean
  attachments: Array<{
    filename: string; mime_type: string; size: number; attachment_id?: string | null
    content_id?: string | null; inline?: boolean; data_base64?: string
  }>
}
type MailThread = { thread_id: string; subject: string; messages: ThreadMessage[] }
type PreparedMail = {
  data: {
    operation_id: string
    digest: string
    preview: { draft: {
      recipient: string; subject: string; body: string; cc: string; bcc: string; thread_id?: string
    } }
  }
}

const DEFAULT_QUERY = buildGmailQuery({status: 'all', period: '7d', scope: 'inbox'})

export function GmailPage({canCreateDraft, canSend}: {canCreateDraft: boolean; canSend: boolean}) {
  const [userQuery, setUserQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [periodFilter, setPeriodFilter] = useState('7d')
  const [scopeFilter, setScopeFilter] = useState('inbox')
  const [attachmentsOnly, setAttachmentsOnly] = useState(false)
  const [result, setResult] = useState<MailList | null>(null)
  const [selected, setSelected] = useState<MailThread | null>(null)
  const [loading, setLoading] = useState(false)
  const [threadLoading, setThreadLoading] = useState(false)
  const [slowLoading, setSlowLoading] = useState(false)
  const [error, setError] = useState('')
  const [composeOpen, setComposeOpen] = useState(false)
  const [recipient, setRecipient] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [cc, setCc] = useState('')
  const [bcc, setBcc] = useState('')
  const [replyContext, setReplyContext] = useState<{thread_id: string; in_reply_to: string; references: string} | null>(null)
  const [prepared, setPrepared] = useState<EmailProposalData | null>(null)
  const searchRequest = useRef<AbortController | null>(null)
  const threadRequest = useRef<AbortController | null>(null)

  const buildQuery = useCallback((filterId: string, customQuery?: string, overrides: Partial<{status: string; period: string; scope: string; attachments: boolean}> = {}) => {
    const base = buildGmailQuery({
      status: overrides.status ?? statusFilter,
      period: overrides.period ?? periodFilter,
      scope: overrides.scope ?? scopeFilter,
      attachments: overrides.attachments ?? attachmentsOnly,
      userQuery: customQuery !== undefined ? customQuery : userQuery,
    })
    return filterId === 'needs-reply'
      ? `${base} -from:me -category:promotions -category:social`
      : base
  }, [attachmentsOnly, periodFilter, scopeFilter, statusFilter, userQuery])

  const search = useCallback(async (nextQuery: string, pageToken?: string, append = false) => {
    searchRequest.current?.abort()
    const controller = new AbortController()
    searchRequest.current = controller
    setLoading(true)
    setSlowLoading(false)
    setError('')
    const slowTimer = window.setTimeout(() => {
      if (searchRequest.current === controller && !controller.signal.aborted) setSlowLoading(true)
    }, 8000)
    try {
      const suffix = pageToken ? `&page_token=${encodeURIComponent(pageToken)}` : ''
      const next = await api<MailList>(`/api/gmail/messages?query=${encodeURIComponent(nextQuery)}&max_results=20${suffix}`, {
        signal: controller.signal,
      })
      if (controller.signal.aborted) return
      setResult(current => append && current ? {...next, messages: [...current.messages, ...next.messages]} : next)
      if (!append) setSelected(null)
    } catch (caught) {
      if (controller.signal.aborted) return
      if (!append) {
        setResult(null)
        setSelected(null)
      }
      setError(caught instanceof Error ? caught.message : 'Không tải được Gmail.')
    } finally {
      window.clearTimeout(slowTimer)
      if (searchRequest.current === controller) {
        setLoading(false)
        setSlowLoading(false)
      }
    }
  }, [])

  async function openThread(threadId: string) {
    threadRequest.current?.abort()
    const controller = new AbortController()
    threadRequest.current = controller
    setThreadLoading(true)
    setError('')
    try {
      const thread = await api<MailThread>(`/api/gmail/threads/${threadId}`, {
        signal: controller.signal,
      })
      if (controller.signal.aborted) return
      setSelected(thread)
    } catch (caught) {
      if (controller.signal.aborted) return
      setError(caught instanceof Error ? caught.message : 'Không đọc được chuỗi email.')
    } finally {
      if (threadRequest.current === controller) setThreadLoading(false)
    }
  }

  useEffect(() => {
    void search(DEFAULT_QUERY)
    return () => {
      searchRequest.current?.abort()
      threadRequest.current?.abort()
    }
  }, [search])

  const visibleMessages = useMemo(() => {
    const messages = result?.messages ?? []
    return activeFilter === 'needs-reply'
      ? messages.filter(message => classifyReplyNeed(message).needsReply)
      : messages
  }, [activeFilter, result])

  function replyToSelected() {
    if (!selected) return
    const last = selected.messages[selected.messages.length - 1]
    // The API removes the authenticated user's own address from reply_to.
    // Do not silently turn a self-sent message into a self-reply.
    setRecipient(last?.reply_to || '')
    setSubject(selected.subject.toLowerCase().startsWith('re:') ? selected.subject : `Re: ${selected.subject}`)
    setBody('')
    setCc('')
    setBcc('')
    setReplyContext(last ? {
      thread_id: selected.thread_id,
      in_reply_to: last.message_id_header,
      references: [last.references, last.message_id_header].filter(Boolean).join(' ').trim(),
    } : null)
    setPrepared(null)
    setComposeOpen(true)
  }

  async function prepareEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null
    const action: EmailAction = submitter?.value === 'send' ? 'send' : 'draft'
    const actionConfig = emailActionConfig(action)
    setError('')
    setPrepared(null)
    setLoading(true)
    try {
      const response = await api<PreparedMail>(actionConfig.prepareEndpoint, {
        method: 'POST',
        body: JSON.stringify({
          request_key: `mail_${crypto.randomUUID().replaceAll('-', '')}`,
          draft: {
            recipient: recipient.trim(), subject: subject.trim(), body: body.trim(),
            cc: cc.trim(), bcc: bcc.trim(), drive_file_ids: [],
            thread_id: replyContext?.thread_id,
            in_reply_to: replyContext?.in_reply_to ?? '',
            references: replyContext?.references ?? '',
          },
        }),
      })
      const preview = response.data.preview.draft ?? response.data.preview
      setPrepared({
        operation_id: response.data.operation_id,
        digest: response.data.digest,
        recipient: preview.recipient,
        subject: preview.subject,
        body_snippet: preview.body,
        cc: preview.cc,
        bcc: preview.bcc,
        thread_id: preview.thread_id,
        action,
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không chuẩn bị được email.')
    } finally {
      setLoading(false)
    }
  }

  return <section className="mail-page">
    <header className="page-heading mail-heading">
      <div>
        <h2>Hộp thư cần xử lý</h2>
        <p>Tìm và đọc email trước. Mọi thư gửi đi đều có bản xem trước riêng để bạn xác nhận.</p>
      </div>
      {canCreateDraft ? <Button icon={<Send20Regular />} appearance="primary" onClick={() => {
        setComposeOpen(true); setPrepared(null); setReplyContext(null); setRecipient(''); setSubject(''); setBody(''); setCc(''); setBcc('')
      }}>
        Soạn thư
      </Button> : <p className="mail-readonly-note">Vai trò hiện tại chỉ được đọc Gmail.</p>}
    </header>

    <form className="mail-search" onSubmit={(event) => { event.preventDefault(); void search(buildQuery(activeFilter, userQuery)) }}>
      <Input
        aria-label="Tìm Gmail"
        value={userQuery}
        onChange={(_, data) => setUserQuery(data.value)}
        placeholder={activeFilter === 'needs-reply' ? "Tìm trong thư cần phản hồi..." : "Tìm email theo người gửi, chủ đề, từ khóa..."}
        className="mail-search-capsule"
      />
      <Button type="submit" disabled={loading} className="mail-search-submit-btn">Tìm email</Button>
      <Button type="button" icon={<ArrowClockwise20Regular />} appearance="subtle" disabled={loading} onClick={() => void search(buildQuery(activeFilter))} className="mail-search-refresh-btn">
        Làm mới
      </Button>
    </form>
    <div className="mail-filter-row" aria-label="Bộ lọc Gmail">
      <select aria-label="Trạng thái thư" className={`mail-filter-select ${statusFilter !== 'all' ? 'mail-filter-select--active' : ''}`} value={statusFilter} onChange={event => { const next = event.target.value; setStatusFilter(next); void search(buildQuery(activeFilter, undefined, {status: next})) }}>
        {GMAIL_STATUSES.map(filter => <option key={filter.id} value={filter.id}>{filter.label}</option>)}
      </select>
      <select aria-label="Khoảng thời gian" className={`mail-filter-select ${periodFilter !== '7d' ? 'mail-filter-select--active' : ''}`} value={periodFilter} onChange={event => { const next = event.target.value; setPeriodFilter(next); void search(buildQuery(activeFilter, undefined, {period: next})) }}>
        {GMAIL_PERIODS.map(filter => <option key={filter.id} value={filter.id}>{filter.label}</option>)}
      </select>
      <select aria-label="Phạm vi thư" className={`mail-filter-select ${scopeFilter !== 'inbox' ? 'mail-filter-select--active' : ''}`} value={scopeFilter} onChange={event => { const next = event.target.value; setScopeFilter(next); void search(buildQuery(activeFilter, undefined, {scope: next})) }}>
        {GMAIL_SCOPES.map(filter => <option key={filter.id} value={filter.id}>{filter.label}</option>)}
      </select>
      <button type="button" className={`smart-filter-chip smart-filter-chip--attachment ${attachmentsOnly ? 'smart-filter-chip--active' : ''}`} aria-pressed={attachmentsOnly} onClick={() => { const next = !attachmentsOnly; setAttachmentsOnly(next); void search(buildQuery(activeFilter, undefined, {attachments: next})) }}>Có tệp</button>
      <button type="button" className={`smart-filter-chip smart-filter-chip--reply ${activeFilter === 'needs-reply' ? 'smart-filter-chip--active' : ''}`} aria-pressed={activeFilter === 'needs-reply'} onClick={() => { const next = activeFilter === 'needs-reply' ? 'all' : 'needs-reply'; setActiveFilter(next); void search(buildQuery(next)) }}>Cần trả lời</button>
    </div>
    {error ? <ErrorState message={error} retry={() => search(buildQuery(activeFilter))} /> : null}

    <div className="mail-workbench">
      <section className="mail-list" aria-label="Danh sách email">
        <div className="mail-list__header"><strong>{activeFilter === 'needs-reply' ? 'Email có yêu cầu phản hồi rõ ràng' : `Email tìm được${result?.total_is_estimate ? ' (ước tính)' : ''}`}</strong><span>{error ? '—' : activeFilter === 'needs-reply' ? visibleMessages.length : result?.total_found ?? 0}</span></div>
        {activeFilter === 'needs-reply' ? <p className="mail-triage-note">Bộ lọc ưu tiên độ chính xác: loại email tự động/bản tin và chỉ giữ thư có câu hỏi hoặc yêu cầu hành động rõ ràng.</p> : null}
        {loading && !result ? <LoadingState label="Đang tải Gmail" /> : null}
        {loading && slowLoading ? <p className="mail-triage-note" role="status">Gmail đang phản hồi chậm. Yêu cầu vẫn đang chạy; bạn có thể chuyển sang phần khác và quay lại sau.</p> : null}
        {!loading && !error && visibleMessages.length === 0 ? (
          <EmptyState
            title="Không có email phù hợp"
            description={userQuery.trim() ? `Không tìm thấy email nào khớp với "${userQuery}". Thử từ khóa khác.` : "Không có email nào trong mục này gần đây. Hãy chọn bộ lọc khác hoặc nhập từ khóa tìm kiếm."}
            icon={<span style={{ fontSize: '28px' }}>📬</span>}
          />
        ) : null}
        {visibleMessages.map(item => <button type="button" key={item.id}
          className={selected?.thread_id === item.thread_id ? 'mail-row mail-row--active' : 'mail-row'}
          aria-label={`Mở email “${item.subject || 'Không có tiêu đề'}” từ ${item.sender || 'người gửi không rõ'}, ${formatDate(item.date)}${item.unread ? ', chưa đọc' : ''}${item.has_attachment ? ', có tệp đính kèm' : ''}`}
          onClick={() => void openThread(item.thread_id)}>
          <span className="mail-row__sender">{item.unread ? <i aria-label="Chưa đọc" /> : null}{item.sender}</span>
          <strong>{item.subject}</strong>
          <span className="mail-row__snippet">{item.snippet ? (item.snippet.length > 85 ? item.snippet.slice(0, 85).trimEnd() + '…' : item.snippet) : ''}</span>
          {activeFilter === 'needs-reply' ? <span className="mail-row__triage">{classifyReplyNeed(item).reason}</span> : null}
          <time dateTime={item.date} title={item.date}>{item.has_attachment ? <Attach20Regular aria-label="Có tệp đính kèm" /> : null}{formatDate(item.date)}</time>
        </button>)}
        {result?.next_page_token ? <Button className="mail-load-more" disabled={loading} onClick={() => void search(buildQuery(activeFilter), result.next_page_token ?? undefined, true)}>
          {loading ? 'Đang tải…' : 'Tải thêm email'}
        </Button> : null}
      </section>

      <section className="mail-reader" aria-label="Nội dung email">
        {threadLoading ? <Spinner label="Đang mở chuỗi email" /> : selected ? <>
          <header className="mail-reader__header">
            <div style={{ flex: '1 1 auto', minWidth: 0 }}>
              <span>{selected.messages.length} thư trong chuỗi</span>
              <h3 style={{ lineHeight: 1.35, wordBreak: 'break-word', marginTop: '6px' }}>{selected.subject}</h3>
            </div>
            <div className="mail-reader__actions">
              <Button as="a" href={`https://mail.google.com/mail/u/0/#all/${selected.thread_id}`} target="_blank" rel="noopener noreferrer" icon={<Open20Regular />} appearance="subtle">Mở trong Gmail</Button>
              {canCreateDraft ? <Button icon={<Open20Regular />} onClick={replyToSelected} style={{ flexShrink: 0, whiteSpace: 'nowrap' }}>Soạn phản hồi</Button> : null}
            </div>
          </header>
          <div className="mail-thread">
            {selected.messages.map(message => <article key={message.id} className="mail-message-card">
              <header className="mail-card-header">
                <div className="mail-sender-row">
                  <SenderAvatar sender={message.sender} />
                  <div className="mail-sender-meta">
                    <strong className="mail-sender-name">{message.sender}</strong>
                    <span className="mail-sender-addr">đến {message.recipient}</span>
                  </div>
                </div>
                <div className="mail-card-actions">
                  <time className="mail-date" dateTime={message.date} title={message.date}>
                    {formatDate(message.date)}
                  </time>
                </div>
              </header>
              <MailBodyViewer
                body={message.body}
                plainBody={message.plain_body}
                htmlBody={message.html_body}
                externalImageSources={message.external_image_sources}
                mode={message.presentation_mode}
                messageId={message.id}
                attachments={message.attachments}
              />
            </article>)}
          </div>
        </> : <EmptyState title="Chọn một email để đọc" description="Veridra chỉ tải toàn bộ nội dung sau khi bạn chọn đúng chuỗi." />}
      </section>
    </div>

    {composeOpen ? <section className="mail-composer" aria-label="Soạn email">
      <header><div><span>Bản nháp mới</span><h3>Soạn email có kiểm soát</h3></div><Button appearance="subtle" onClick={() => setComposeOpen(false)}>Đóng</Button></header>
      {!prepared ? <form onSubmit={prepareEmail}>
        <label htmlFor="mail-recipient">Người nhận</label>
        <Input id="mail-recipient" type="email" required value={recipient} onChange={(_, data) => setRecipient(data.value)} />
        <label htmlFor="mail-subject">Tiêu đề</label>
        <Input id="mail-subject" required value={subject} onChange={(_, data) => setSubject(data.value)} />
        <div className="mail-recipient-options">
          <div><label htmlFor="mail-cc">CC <span>(không bắt buộc)</span></label><Input id="mail-cc" value={cc} onChange={(_, data) => setCc(data.value)} /></div>
          <div><label htmlFor="mail-bcc">BCC <span>(không bắt buộc)</span></label><Input id="mail-bcc" value={bcc} onChange={(_, data) => setBcc(data.value)} /></div>
        </div>
        <label htmlFor="mail-body">Nội dung</label>
        <Textarea id="mail-body" required rows={10} value={body} onChange={(_, data) => setBody(data.value)} />
        <p>Tiếp theo là bản xem trước. Chọn lưu nháp để Gmail chỉ ghi vào Drafts; gửi email luôn cần một xác nhận riêng.</p>
        <div className="mail-composer__actions">
          <Button type="submit" name="email-action" value="draft" appearance="primary" disabled={loading || !recipient.trim() || !subject.trim() || !body.trim()}>
            Xem lại & lưu nháp
          </Button>
          {canSend ? <Button type="submit" name="email-action" value="send" disabled={loading || !recipient.trim() || !subject.trim() || !body.trim()}>
            Xem lại trước khi gửi
          </Button> : null}
        </div>
      </form> : <EmailProposal email={prepared} onEdit={() => setPrepared(null)} />}
    </section> : null}
  </section>
}
