import { Button } from '@fluentui/react-components'
import { CheckmarkCircle20Regular, DocumentBulletList20Regular } from '@fluentui/react-icons'
import { useRef, useState } from 'react'
import { api } from '../api'
import { ErrorState } from './AsyncState'

export interface PreparedDocumentExport {
  operation_id: string
  digest: string
  state: string
  title: string
}

interface OperationStatus {
  state: string
  resource_id?: string
  error_code?: string
  result?: { url?: string; verified?: boolean }
}

/** Finishes the explicit approval phase for a prepared Google Doc. */
export function DocumentExportApproval({ prepared }: { prepared: PreparedDocumentExport }) {
  const [operation, setOperation] = useState<OperationStatus>({ state: prepared.state })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)

  async function refresh() {
    const current = await api<OperationStatus>(
      `/api/documents/operations/${prepared.operation_id}`,
    )
    setOperation(current)
  }

  async function approve() {
    if (lock.current || operation.state !== 'pending') return
    lock.current = true
    setBusy(true)
    setError('')
    setOperation({ state: 'running' })
    try {
      await api('/api/documents/approve', {
        method: 'POST',
        body: JSON.stringify({
          operation_id: prepared.operation_id,
          approved_digest: prepared.digest,
        }),
      })
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa tạo được Google Doc.')
      await refresh().catch(() => setOperation({ state: 'unknown' }))
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  const succeeded = operation.state === 'succeeded' && operation.result?.verified
  return (
    <section className="inline-approval" aria-label={`Xác nhận xuất Google Doc: ${prepared.title}`}>
      <div className="inline-approval__copy">
        <DocumentBulletList20Regular aria-hidden="true" />
        <div>
          <strong>{prepared.title}</strong>
          <span>
            {succeeded
              ? 'Google Doc đã được tạo và đọc lại thành công.'
              : 'Bản nội dung đã khóa. File chỉ được tạo sau khi bạn xác nhận.'}
          </span>
        </div>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <div className="inline-approval__actions">
        {operation.state === 'pending' ? (
          <Button appearance="primary" disabled={busy} onClick={() => void approve()}>
            {busy ? 'Đang tạo và kiểm tra…' : 'Xác nhận tạo Google Doc'}
          </Button>
        ) : null}
        {!succeeded ? (
          <Button disabled={busy} onClick={() => void refresh().catch((reason: Error) => setError(reason.message))}>
            Kiểm tra trạng thái
          </Button>
        ) : null}
        {succeeded && operation.result?.url ? (
          <a className="inline-approval__success" href={operation.result.url} target="_blank" rel="noreferrer">
            <CheckmarkCircle20Regular aria-hidden="true" /> Mở tài liệu đã xác minh
          </a>
        ) : null}
      </div>
      {operation.state !== 'pending' && !succeeded ? (
        <p className="inline-approval__status" role="status">
          Trạng thái: {operation.state}{operation.error_code ? ` · ${operation.error_code}` : ''}
        </p>
      ) : null}
    </section>
  )
}
