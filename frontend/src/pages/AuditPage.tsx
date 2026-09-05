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
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components'
import { ArrowSync24Regular } from '@fluentui/react-icons'
import { useCallback, useEffect, useState } from 'react'
import { api, formatDate } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { AuditEvent } from '../types'

const statusLabel: Record<string, string> = {
  started: 'Đang chạy',
  success: 'Thành công',
  warning: 'Cảnh báo',
  error: 'Lỗi',
  denied: 'Bị từ chối',
}

export function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AuditEvent | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const suffix = status === 'all' ? '' : `?status=${encodeURIComponent(status)}`
      setEvents(await api<AuditEvent[]>(`/api/audit${suffix}`))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải audit log.')
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => { void load() }, [load])

  return (
    <section className="stack-page">
      <div className="page-heading">
        <div>
          <h2>Mọi tool call đều để lại dấu vết</h2>
          <p>Arguments và kết quả được rút gọn, secret luôn bị che trước khi ghi.</p>
        </div>
        <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={load}>Làm mới</Button>
      </div>
      <div className="filter-row">
        <Dropdown aria-label="Lọc theo trạng thái" value={status === 'all' ? 'Tất cả trạng thái' : statusLabel[status]} selectedOptions={[status]} onOptionSelect={(_, data) => setStatus(data.optionValue ?? 'all')}>
          <Option value="all">Tất cả trạng thái</Option>
          <Option value="success">Thành công</Option>
          <Option value="error">Lỗi</Option>
          <Option value="denied">Bị từ chối</Option>
          <Option value="started">Đang chạy</Option>
        </Dropdown>
      </div>
      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}
      {!loading && !error && events.length === 0 ? <EmptyState title="Chưa có sự kiện" description="Audit log sẽ xuất hiện sau lần gọi tool đầu tiên." /> : null}
      {!loading && events.length > 0 ? (
        <div className="table-scroll">
          <Table aria-label="Nhật ký tool">
            <TableHeader><TableRow>
              <TableHeaderCell>Thời gian</TableHeaderCell><TableHeaderCell>Tool</TableHeaderCell><TableHeaderCell>User</TableHeaderCell><TableHeaderCell>Trạng thái</TableHeaderCell><TableHeaderCell>Độ trễ</TableHeaderCell><TableHeaderCell>Request ID</TableHeaderCell>
            </TableRow></TableHeader>
            <TableBody>{events.map((event) => (
              <TableRow key={event.id} className="clickable-row" onClick={() => setSelected(event)}>
                <TableCell>{formatDate(event.created_at)}</TableCell>
                <TableCell><code>{event.tool_name}</code></TableCell>
                <TableCell>{event.user_email ?? 'Không rõ'}</TableCell>
                <TableCell><Badge appearance="tint" color={event.status === 'success' ? 'success' : event.status === 'error' || event.status === 'denied' ? 'danger' : 'informative'}>{statusLabel[event.status] ?? event.status}</Badge></TableCell>
                <TableCell className="numeric">{event.latency_ms == null ? '...' : `${event.latency_ms} ms`}</TableCell>
                <TableCell><code className="request-id">{event.request_id.slice(0, 8)}</code></TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        </div>
      ) : null}
      <Dialog open={Boolean(selected)} onOpenChange={(_, data) => !data.open && setSelected(null)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Chi tiết audit</DialogTitle>
            <DialogContent><pre className="audit-json">{selected ? JSON.stringify({ request_id: selected.request_id, tool: selected.tool_name, status: selected.status, arguments: selected.arguments, result: selected.result, error: selected.error_message }, null, 2) : ''}</pre></DialogContent>
            <DialogActions><Button appearance="primary" onClick={() => setSelected(null)}>Đóng</Button></DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
