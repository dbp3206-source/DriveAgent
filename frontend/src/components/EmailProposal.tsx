import { Badge, Button } from '@fluentui/react-components'
import { Mail24Regular, Save24Regular, Send24Regular, CheckmarkCircle24Regular } from '@fluentui/react-icons'
import { useRef, useState } from 'react'
import { api } from '../api'
import { ErrorState } from './AsyncState'
import { emailActionConfig, type EmailAction } from '../emailWorkflow.mjs'

export interface EmailProposalData {
  operation_id: string
  digest: string
  recipient: string
  subject: string
  body_snippet: string
  attachment_names?: string[]
  cc?: string
  bcc?: string
  thread_id?: string
  action?: EmailAction
}

interface OperationStatus {
  state: string
  resource_id?: string
  error_code?: string
  result?: { url?: string; message_id?: string }
}

export function EmailProposal({ email, onEdit }: { email: EmailProposalData; onEdit?: () => void }) {
  const [operation, setOperation] = useState<OperationStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(false)
  const lock = useRef(false)
  const action = email.action ?? 'send'
  const actionConfig = emailActionConfig(action)

  async function checkStatus() {
    try {
      const status = await api<OperationStatus>(`/api/gmail/operations/${email.operation_id}`)
      setOperation(status)
      if (status.state === 'succeeded') setCompleted(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không kiểm tra được trạng thái email.')
    }
  }

  async function confirmAction() {
    if (lock.current || completed) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      setOperation({ state: 'running' })
      const result = await api<{draft_id?: string; gmail_draft_url?: string}>(actionConfig.approveEndpoint, {
        method: 'POST',
        body: JSON.stringify({
          operation_id: email.operation_id,
          approved_digest: email.digest,
        }),
      })
      setCompleted(true)
      setOperation({
        state: 'succeeded',
        resource_id: result.draft_id,
        result: result.gmail_draft_url ? {url: result.gmail_draft_url} : undefined,
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : action === 'draft' ? 'Chưa lưu được bản nháp.' : 'Chưa gửi được email.')
      await checkStatus()
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return (
    <section aria-label={`Bản đề xuất gửi email: ${email.subject}`} className="email-proposal-card">
      <div className="email-proposal__header">
        <div className="email-proposal__title-row">
          <Mail24Regular primaryFill="var(--colorBrandForeground1)" />
          <span className="email-proposal__title">{action === 'draft' ? 'Bản nháp Gmail chờ lưu' : 'Email chờ duyệt gửi'}</span>
          <Badge appearance="tint" color={completed ? 'success' : 'informative'}>
            {completed ? (action === 'draft' ? 'Đã lưu nháp' : 'Đã gửi') : actionConfig.pendingLabel}
          </Badge>
        </div>
      </div>

      <div className="email-proposal__details">
        <div className="email-proposal__row">
          <span className="email-proposal__label">Người nhận:</span>
          <strong className="email-proposal__value">{email.recipient}</strong>
        </div>
        {email.cc ? <div className="email-proposal__row">
          <span className="email-proposal__label">CC:</span>
          <strong className="email-proposal__value">{email.cc}</strong>
        </div> : null}
        {email.bcc ? <div className="email-proposal__row">
          <span className="email-proposal__label">BCC:</span>
          <strong className="email-proposal__value">{email.bcc}</strong>
        </div> : null}
        {email.thread_id ? <p className="email-security-note">Thư này sẽ được gửi trong đúng chuỗi hội thoại đang mở.</p> : null}
        <div className="email-proposal__row">
          <span className="email-proposal__label">Tiêu đề:</span>
          <strong className="email-proposal__value">{email.subject}</strong>
        </div>
        {email.attachment_names && email.attachment_names.length > 0 && (
          <div className="email-proposal__row">
            <span className="email-proposal__label">Tệp Drive đính kèm:</span>
            <div className="email-proposal__chips">
              {email.attachment_names.map((name, idx) => (
                <span key={idx} className="email-proposal__chip">
                  📎 {name}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="email-proposal__body-preview">
          <p className="email-proposal__label">Nội dung thư xem trước:</p>
          <div className="email-proposal__body-content">{email.body_snippet}</div>
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {operation?.state && !completed && (
        <p className="email-security-note" role="status">
          Trạng thái thao tác: {operation.state}
          {operation.error_code ? ` · ${operation.error_code}` : ''}
        </p>
      )}

      <div className="email-proposal__actions">
        {!completed ? (
          <>
            <Button
              appearance="primary"
              icon={action === 'draft' ? <Save24Regular /> : <Send24Regular />}
              disabled={busy}
              onClick={() => void confirmAction()}
            >
              {busy ? actionConfig.busyLabel : actionConfig.actionLabel}
            </Button>
            {onEdit ? <Button disabled={busy} onClick={onEdit}>Chỉnh sửa nội dung</Button> : null}
            <Button disabled={busy} onClick={() => void checkStatus()}>
              Kiểm tra trạng thái
            </Button>
          </>
        ) : (
          <div className="email-proposal__success">
            <CheckmarkCircle24Regular primaryFill="var(--colorPaletteGreenForeground1)" />
            <span>{actionConfig.successLabel}</span>
          </div>
        )}
      </div>

      <div className="email-proposal__footer">
        <span className="email-digest-code">
          Mã an toàn (SHA-256): <code>{email.digest.slice(0, 16)}…</code>
        </span>
        <span className="email-security-note">
          {action === 'draft'
            ? 'Human-in-the-Loop: Bấm xác nhận chỉ lưu vào Drafts; ứng dụng không gửi email.'
            : 'Human-in-the-Loop: Chỉ gửi sau khi bạn bấm xác nhận.'}
        </span>
      </div>
    </section>
  )
}
