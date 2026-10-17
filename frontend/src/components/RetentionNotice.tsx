import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  MessageBar,
  MessageBarBody,
  Spinner,
} from '@fluentui/react-components'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, formatDate } from '../api'

type CleanupPreview = {
  approval_id: string | null
  token: string | null
  selected_count: number
  due_count: number
  active_due_count: number
  upcoming_count: number
  next_due_at: string | null
  has_more: boolean
  counts: Record<string, number>
  expires_at: string | null
  cutoff: string
  retention_days: number
  reset_context_count: number
}

type CleanupJob = {
  id: string
  status: 'queued' | 'running' | 'purging' | 'needs_attention' | 'succeeded' | 'cancelled'
  automatic: boolean
  attempts: number
  selected_count: number
  remaining_count: number
  completed_count: number
  sql_completed: boolean
  error_code: string | null
  can_cancel: boolean
}

const OPEN_STATES = new Set<CleanupJob['status']>(['queued', 'running', 'purging', 'needs_attention'])
const categoryLabels: Record<string, string> = {
  chat: 'hội thoại', memory: 'mục ghi nhớ', source: 'tài liệu đã nhập', index: 'mục tìm kiếm',
  artifact: 'kết quả đã lưu', skill: 'mẫu công việc', company: 'hồ sơ công ty', job: 'tác vụ',
  operation: 'thao tác', audit: 'mục nhật ký', framework: 'bản lưu ngữ cảnh trợ lý',
}

function checkKey(ownerId: string) { return `veridra-retention-check:${ownerId}` }
function seenKey(ownerId: string) { return `veridra-retention-seen:${ownerId}` }
function todayKey() { return new Date().toISOString().slice(0, 10) }
function statusLabel(status: CleanupJob['status']) {
  return ({ queued: 'Đang chờ', running: 'Đang chuẩn bị', purging: 'Đang dọn',
    needs_attention: 'Cần kiểm tra', succeeded: 'Đã hoàn tất', cancelled: 'Đã hủy' })[status]
}
function errorLabel(code: string | null) {
  return ({ owner_busy: 'Một số thao tác đang chạy. Hãy thử lại sau.',
    approval_changed: 'Dữ liệu đã thay đổi. Hãy kiểm tra lại danh sách trước khi tiếp tục.',
    storage_unavailable: 'Chưa xóa và kiểm chứng được tệp. Bạn có thể thử lại cùng phạm vi đã duyệt.',
    vector_unavailable: 'Chưa xóa và kiểm chứng được chỉ mục. Bạn có thể thử lại cùng phạm vi đã duyệt.',
    framework_unavailable: 'Chưa thể kiểm tra đủ bản lưu ngữ cảnh. Hãy thử lại sau.',
    worker_interrupted: 'Việc dọn bị gián đoạn và có thể tiếp tục từ trạng thái đã lưu.',
    retry_limit: 'Đã chạm giới hạn thử lại. Cần kiểm tra máy chủ trước khi tiếp tục.',
    checkpoint_invalid: 'Sổ tiến độ không hợp lệ. Cần kiểm tra máy chủ trước khi tiếp tục.',
  } as Record<string, string>)[code ?? ''] ?? 'Chưa hoàn tất. Hãy kiểm tra trạng thái rồi thử lại.'
}

function announceCompletion(ownerId: string, jobId: string) {
  const detail = { ownerId, jobId }
  window.dispatchEvent(new CustomEvent('veridra:retention-completed', { detail }))
  try {
    const channel = new BroadcastChannel('veridra-retention')
    channel.postMessage({ type: 'completed', ...detail })
    channel.close()
  } catch { /* This tab still receives the local event. */ }
}

export function RetentionNotice({ ownerId }: { ownerId: string }) {
  const [open, setOpen] = useState(false)
  const [manual, setManual] = useState(false)
  const [preview, setPreview] = useState<CleanupPreview | null>(null)
  const [job, setJob] = useState<CleanupJob | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const started = useRef(false)
  const jobRef = useRef<CleanupJob | null>(null)
  const announcedJob = useRef('')

  const updateJob = useCallback((next: CleanupJob | null) => {
    jobRef.current = next
    setJob(next)
    if (next?.status === 'succeeded') {
      let alreadySeen = false
      try { alreadySeen = sessionStorage.getItem(seenKey(ownerId)) === next.id } catch { /* Optional */ }
      if (!alreadySeen && announcedJob.current !== next.id) {
        announcedJob.current = next.id
        try { sessionStorage.setItem(seenKey(ownerId), next.id) } catch { /* Optional */ }
        announceCompletion(ownerId, next.id)
        setOpen(true)
      }
    }
  }, [ownerId])

  const refreshStatus = useCallback(async () => {
    const result = await api<{ job: CleanupJob | null }>('/api/retention/status')
    updateJob(result.job)
    if (result.job && OPEN_STATES.has(result.job.status)) setOpen(true)
    return result.job
  }, [updateJob])

  const loadPreview = useCallback(async (showNoData: boolean) => {
    setBusy(true)
    setError('')
    setManual(showNoData)
    setJob(null)
    jobRef.current = null
    try {
      const result = await api<CleanupPreview>('/api/retention/preview', { timeoutMs: 90_000 })
      setPreview(result)
      setConfirmed(false)
      try { localStorage.setItem(checkKey(ownerId), todayKey()) } catch { /* Optional */ }
      if (showNoData || result.due_count > 0 || result.upcoming_count > 0) setOpen(true)
    } catch (caught) {
      if (showNoData) {
        setPreview(null)
        setOpen(true)
        setError(caught instanceof Error ? caught.message : 'Chưa kiểm tra được dữ liệu. Hãy thử lại.')
      }
    } finally {
      setBusy(false)
    }
  }, [ownerId])

  const checkNow = useCallback(async (showNoData: boolean) => {
    try {
      const current = await refreshStatus()
      if (current && OPEN_STATES.has(current.status)) return
      await loadPreview(showNoData)
    } catch (caught) {
      if (showNoData) {
        setPreview(null)
        setOpen(true)
        setError(caught instanceof Error ? caught.message : 'Chưa đọc được trạng thái. Hãy thử lại.')
      }
    }
  }, [loadPreview, refreshStatus])

  useEffect(() => {
    if (started.current) return
    started.current = true
    let stopped = false
    void (async () => {
      let current: CleanupJob | null = null
      try { current = await refreshStatus() } catch { /* The app remains usable. */ }
      if (stopped || current && OPEN_STATES.has(current.status)) return
      let checkedToday = false
      try { checkedToday = localStorage.getItem(checkKey(ownerId)) === todayKey() } catch { /* Optional */ }
      if (!checkedToday) await loadPreview(false)
    })()
    const listenForManualCheck = () => { void checkNow(true) }
    const channel = (() => {
      try { return new BroadcastChannel('veridra-retention') } catch { return null }
    })()
    if (channel) channel.onmessage = (event) => {
      if (event.data?.type === 'completed' && event.data?.ownerId === ownerId) {
        void refreshStatus().catch(() => {})
      }
    }
    window.addEventListener('veridra:retention-open', listenForManualCheck)
    const poll = window.setInterval(() => {
      if (jobRef.current && OPEN_STATES.has(jobRef.current.status)) {
        void refreshStatus().catch(() => {})
      }
    }, 4000)
    return () => {
      stopped = true
      window.clearInterval(poll)
      window.removeEventListener('veridra:retention-open', listenForManualCheck)
      channel?.close()
    }
  }, [checkNow, loadPreview, ownerId, refreshStatus])

  async function confirmCleanup() {
    if (!preview?.token || !confirmed || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await api<{ id: string; status: CleanupJob['status'] }>('/api/retention/confirm', {
        method: 'POST', body: JSON.stringify({ token: preview.token, confirmed: true }),
      })
      setPreview(null)
      setConfirmed(false)
      await refreshStatus()
      if (!jobRef.current || jobRef.current.id !== result.id) {
        // The worker may not have committed its first status read yet.
        const pending = { id: result.id, status: 'queued', automatic: false, attempts: 0, selected_count: preview.selected_count,
          completed_count: 0, remaining_count: preview.selected_count, sql_completed: false,
          error_code: null, can_cancel: true } as CleanupJob
        updateJob(pending)
        setOpen(true)
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Chưa gửi được yêu cầu dọn dữ liệu.'
      setError(message)
      const current = await refreshStatus().catch(() => null)
      if (current && OPEN_STATES.has(current.status)) {
        setPreview(null)
        setOpen(true)
      } else if ((caught as { status?: number })?.status === 409 || !preview) {
        // A stale or ambiguous approval is shown again as a fresh, unchecked preview.
        await loadPreview(true)
        setError(message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function retryCleanup() {
    if (!job || busy) return
    setBusy(true)
    setError('')
    try {
      await api(`/api/retention/jobs/${job.id}/retry`, { method: 'POST' })
      await refreshStatus()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa thể tiếp tục lần dọn này.')
    } finally { setBusy(false) }
  }

  async function cancelCleanup() {
    if (!job || busy) return
    setBusy(true)
    setError('')
    try {
      await api(`/api/retention/jobs/${job.id}/cancel`, { method: 'POST' })
      updateJob({ ...job, status: 'cancelled', can_cancel: false })
      await loadPreview(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Lần dọn đã bắt đầu nên không thể hủy.')
      await refreshStatus().catch(() => {})
    } finally { setBusy(false) }
  }

  const activeJob = job && OPEN_STATES.has(job.status) ? job : null
  const counts = Object.entries(preview?.counts ?? {}).filter(([, count]) => count > 0)

  return <Dialog open={open} onOpenChange={(_, data) => { if (!busy) setOpen(data.open) }}>
      <DialogSurface className="retention-dialog">
      <DialogBody>
        <DialogTitle>{activeJob ? 'Trạng thái dọn dữ liệu' : job?.status === 'succeeded' ? (job.automatic ? 'Đã tự dọn dữ liệu Veridra' : 'Đã dọn dữ liệu Veridra') : preview?.upcoming_count ? 'Sắp đến hạn lưu dữ liệu' : 'Dữ liệu Veridra đã đủ 30 ngày'}</DialogTitle>
        <DialogContent className="retention-dialog__content">
          {busy && !preview && !job && <Spinner label="Đang kiểm tra dữ liệu đã lưu…" />}
          {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
          {activeJob && <>
            <div className="retention-job-status"><Badge appearance="tint" color={activeJob.status === 'needs_attention' ? 'warning' : 'informative'}>{statusLabel(activeJob.status)}</Badge>
              <span>Đã xử lý {activeJob.completed_count}/{activeJob.selected_count} mục · còn {activeJob.remaining_count}</span></div>
            {activeJob.status === 'needs_attention'
              ? <MessageBar intent="warning"><MessageBarBody>{errorLabel(activeJob.error_code)} {activeJob.automatic ? 'Hệ thống sẽ tự thử lại; bạn cũng có thể yêu cầu tiếp tục ngay.' : 'Thử lại sẽ tiếp tục đúng danh sách đã duyệt.'}</MessageBarBody></MessageBar>
              : <p role="status">Veridra đang xử lý. Bạn có thể tiếp tục dùng các phần khác của sản phẩm.</p>}
            {activeJob.can_cancel && <Button appearance="subtle" disabled={busy} onClick={() => void cancelCleanup()}>Hủy lần dọn</Button>}
            {activeJob.status === 'needs_attention' && <Button appearance="primary" disabled={busy} onClick={() => void retryCleanup()}>Tiếp tục lần dọn đã duyệt</Button>}
          </>}
          {!activeJob && job?.status === 'succeeded' && <MessageBar intent="success"><MessageBarBody>{job.automatic ? 'Tự động dọn xong' : 'Đã dọn'} {job.selected_count} mục Veridra. Các bản gốc trong Google vẫn được giữ nguyên.</MessageBarBody></MessageBar>}
          {!activeJob && job?.status === 'cancelled' && <p>Lần dọn đã được hủy trước khi bắt đầu.</p>}
          {!activeJob && !job && preview && <>
            {preview.upcoming_count > 0 && <MessageBar intent="info"><MessageBarBody>
              Có {preview.upcoming_count} mục sắp đủ 30 ngày lưu{preview.next_due_at ? `; đợt đầu dự kiến từ ${formatDate(preview.next_due_at)}` : ''}. Theo chính sách, hệ thống sẽ tự dọn sau khi lịch tự động được bật; bạn không cần mở lại để xác nhận.
            </MessageBarBody></MessageBar>}
            {preview.selected_count > 0 ? <>
              <p>Có <strong>{preview.due_count}</strong> mục đã đủ thời gian lưu 30 ngày. Đợt này có thể dọn <strong>{preview.selected_count}</strong> mục đã kiểm tra.</p>
              {counts.length > 0 && <ul className="retention-counts">{counts.map(([kind, count]) => <li key={kind}><span>{categoryLabels[kind] ?? kind}</span><strong>{count}</strong></li>)}</ul>}
              {preview.reset_context_count > 0 && <MessageBar intent="warning"><MessageBarBody>Thao tác này cũng đặt lại {preview.reset_context_count} mục ngữ cảnh làm việc của trợ lý. Lịch sử hội thoại còn hạn vẫn được giữ.</MessageBarBody></MessageBar>}
              {preview.has_more && <p>Các mục còn lại sẽ được dọn theo từng đợt tự động.</p>}
              {preview.active_due_count > 0 && <p>{preview.active_due_count} mục đang được dùng sẽ được hoãn để tránh làm gián đoạn tác vụ; hệ thống sẽ kiểm tra lại.</p>}
              <MessageBar intent="info"><MessageBarBody>Chỉ dọn dữ liệu do Veridra lưu. Bản gốc Gmail, Drive, Lịch, Docs, bản tải về và bản sao ngoài Veridra không bị xóa. Theo chính sách, hệ thống sẽ tự dọn khi đủ hạn sau khi lịch tự động được bật.</MessageBarBody></MessageBar>
              <Checkbox checked={confirmed} onChange={(_, data) => setConfirmed(data.checked === true)}
                label="Tôi xác nhận dọn ngay danh sách đã kiểm tra." />
            </> : preview.due_count > 0
              ? <p>Hiện chưa có mục nào có thể dọn. Có {preview.active_due_count} mục đang được dùng; hệ thống sẽ kiểm tra lại và xử lý sau khi tác vụ kết thúc.</p>
              : preview.upcoming_count === 0 && <p>Hiện chưa có dữ liệu đủ 30 ngày cần dọn.</p>}
          </>}
          {manual && !preview && !job && !busy && !error && <p>Chưa có lần dọn nào cần xử lý.</p>}
        </DialogContent>
        <DialogActions>
          {activeJob ? <Button appearance="secondary" disabled={busy} onClick={() => setOpen(false)}>Ẩn thông báo</Button> : <Button appearance="secondary" disabled={busy} onClick={() => setOpen(false)}>{preview?.selected_count ? 'Để sau' : 'Đóng'}</Button>}
          {!activeJob && preview?.selected_count ? <Button appearance="primary" disabled={!confirmed || busy || !preview.token} onClick={() => void confirmCleanup()}>{busy ? 'Đang gửi…' : 'Dọn ngay'}</Button> : null}
          {manual && error && !busy ? <Button appearance="primary" onClick={() => void checkNow(true)}>Thử lại kiểm tra</Button> : null}
        </DialogActions>
      </DialogBody>
    </DialogSurface>
  </Dialog>
}
