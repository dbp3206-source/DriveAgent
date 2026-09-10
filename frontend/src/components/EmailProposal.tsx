import { Badge, Button } from '@fluentui/react-components'
import { Mail24Regular, Send24Regular, CheckmarkCircle24Regular } from '@fluentui/react-icons'
import { useRef, useState } from 'react'
import { api } from '../api'
import { ErrorState } from './AsyncState'

export interface EmailProposalData {
  operation_id: string
  digest: string
  recipient: string
  subject: string
  body_snippet: string
  attachment_names?: string[]
}

interface OperationStatus {
  state: string
  resource_id?: string
  error_code?: string
  result?: { url?: string; message_id?: string }
}

export function EmailProposal({ email }: { email: EmailProposalData }) {
  const [operation, setOperation] = useState<OperationStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const lock = useRef(false)

  async function checkStatus() {
    try {
      const status = await api<OperationStatus>(`/api/gmail/operations/${email.operation_id}`)
      setOperation(status)
      if (status.state === 'succeeded') setSent(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không kiểm tra được trạng thái email.')
    }
  }

  async function confirmSend() {
    if (lock.current || sent) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      setOperation({ state: 'running' })
      await api('/api/gmail/approve', {
        method: 'POST',
        body: JSON.stringify({
          operation_id: email.operation_id,
          approved_digest: email.digest,
        }),
      })
      setSent(true)
      setOperation({ state: 'succeeded' })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa gửi được email.')
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
          <span className="email-proposal__title">Bản nháp Gmail chờ duyệt</span>
          <Badge appearance="tint" color={sent ? 'success' : 'informative'}>
            {sent ? 'Đã gửi' : 'Chờ xác nhận (2-Phase)'}
          </Badge>
        </div>
      </div>

      <div className="email-proposal__details">
        <div className="email-proposal__row">
          <span className="email-proposal__label">Người nhận:</span>
          <strong className="email-proposal__value">{email.recipient}</strong>
        </div>
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
      {operation?.state && !sent && (
        <p className="email-security-note" role="status">
          Trạng thái thao tác: {operation.state}
          {operation.error_code ? ` · ${operation.error_code}` : ''}
        </p>
      )}

      <div className="email-proposal__actions">
        {!sent ? (
          <>
            <Button
              appearance="primary"
              icon={<Send24Regular />}
              disabled={busy}
              onClick={() => void confirmSend()}
            >
              {busy ? 'Đang gửi email…' : 'Xác nhận gửi email này'}
            </Button>
            <Button disabled={busy} onClick={() => void checkStatus()}>
              Kiểm tra trạng thái
            </Button>
          </>
        ) : (
          <div className="email-proposal__success">
            <CheckmarkCircle24Regular primaryFill="var(--colorPaletteGreenForeground1)" />
            <span>Email đã được gửi thành công qua tài khoản Gmail của bạn.</span>
          </div>
        )}
      </div>

      <div className="email-proposal__footer">
        <span className="email-digest-code">
          Mã an toàn (SHA-256): <code>{email.digest.slice(0, 16)}…</code>
        </span>
        <span className="email-security-note">
          Tuân thủ nguyên tắc Human-in-the-Loop: Chỉ gửi sau khi bạn bấm xác nhận.
        </span>
      </div>
    </section>
  )
}
