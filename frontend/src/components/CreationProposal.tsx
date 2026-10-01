import { Button } from '@fluentui/react-components'
import { useRef, useState } from 'react'
import { api } from '../api'
import { ErrorState } from './AsyncState'
import { EmailProposal, type EmailProposalData } from './EmailProposal'
import type { DocumentBlock } from '../documentMarkdown.js'

type AggregateFormula = {function: string; column: number; start_row: number; end_row: number}
type RowFormula = {operator: 'SUBTRACT'; left_column: number; right_column: number; row: number}
type Cell = string | number | boolean | AggregateFormula | RowFormula | null
type VisualSpec = {type: string; title: string; subtitle: string; sections: {title: string; body: string; value?: string}[]}
type DocumentProposal = {id: string; kind: 'document'; document: {title: string; blocks: DocumentBlock[]}}
type SpreadsheetProposal = {id: string; kind: 'spreadsheet'; spreadsheet: {title: string; tabs: {
  title: string; headers: string[]; rows: Cell[][];
  chart: {title: string; kind: 'COLUMN' | 'BAR' | 'LINE'; label_column: number; value_column: number} | null
}[]}}
type DocumentEditProposal = {id: string; kind: 'document_edit'; document_edit: {document_id: string; tab_id?: string; old_text: string; new_text: string}}
type SpreadsheetEditProposal = {id: string; kind: 'spreadsheet_edit'; spreadsheet_edit: {spreadsheet_id: string; sheet_title: string; range_a1: string; new_values: Cell[][]}}
type LegacyProposal = {id: string} & (
  {kind: 'presentation'; presentation: {title: string; slides: {title: string; bullets: string[]; speaker_notes: string; visual: VisualSpec | null}[]}} |
  {kind: 'visual'; visual: VisualSpec} |
  {kind: 'presentation_edit'; presentation_edit: {presentation_id: string}}
)
type WorkspaceProposal = DocumentProposal | SpreadsheetProposal | DocumentEditProposal | SpreadsheetEditProposal
export type Proposal = WorkspaceProposal | LegacyProposal | ({id: string; kind: 'email'; email: EmailProposalData})

type Prepared = {operation_id: string; digest: string; state: string}
type Operation = {state: string; resource_id?: string; error_code?: string; result?: {url?: string; verified?: boolean}}

function cellText(cell: Cell): string {
  if (cell === null) return ''
  if (typeof cell === 'number') return cell.toLocaleString('vi-VN')
  if (typeof cell !== 'object') return String(cell)
  if ('operator' in cell) {
    const left = String.fromCharCode(65 + cell.left_column)
    const right = String.fromCharCode(65 + cell.right_column)
    const row = cell.row + 2
    return `=${left}${row}-${right}${row}`
  }
  const column = String.fromCharCode(65 + cell.column)
  return `=${cell.function}(${column}${cell.start_row + 2}:${column}${cell.end_row + 1})`
}

function SheetPreview({proposal}: {proposal: SpreadsheetProposal}) {
  return proposal.spreadsheet.tabs.map((tab, index) => <section key={index}>
    <h4>{tab.title}</h4>
    <div className="table-scroll" tabIndex={0} aria-label={`Dữ liệu ${tab.title}`}>
      <table><thead><tr>{tab.headers.map((header, column) => <th key={column}>{header}</th>)}</tr></thead>
        <tbody>{tab.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, column) => <td key={column}>{cellText(cell)}</td>)}</tr>)}</tbody>
      </table>
    </div>
    {tab.chart ? <p>Biểu đồ {tab.chart.kind}: {tab.chart.title}. Nhãn: {tab.headers[tab.chart.label_column]}; giá trị: {tab.headers[tab.chart.value_column]}.</p> : null}
  </section>)
}

function operationText(state: string) {
  if (state === 'succeeded') return 'Đã hoàn tất và kiểm tra lại nội dung.'
  if (state === 'pending') return 'Sẵn sàng chờ bạn xác nhận. Bản duyệt có hiệu lực 30 phút.'
  if (state === 'running') return 'Đang thực hiện và đọc lại kết quả để kiểm tra.'
  if (state === 'uncertain') return 'Chưa xác minh được kết quả. Không gửi lại; hãy kiểm tra trạng thái.'
  if (state === 'failed') return 'Không thể hoàn tất. Xử lý nguyên nhân trước khi thử lại.'
  return 'Chưa xác định được trạng thái. Hãy kiểm tra lại.'
}

/** Model output is inert. Only the explicit approval below may write to Google. */
export function CreationProposal({proposal}: {proposal: Proposal}) {
  if (proposal.kind === 'email') return <EmailProposal email={proposal.email} />
  if (proposal.kind === 'presentation' || proposal.kind === 'presentation_edit' || proposal.kind === 'visual') {
    return <section className="retired-proposal" role="note">
      <strong>Đầu ra cũ được giữ trong lịch sử</strong>
      <p>Google Slides và Visual Studio đã được rút khỏi sản phẩm để tập trung chất lượng cho Docs, Sheets và Gmail. Bản cũ không thể thực thi lại.</p>
    </section>
  }
  return <WorkspaceCreationProposal proposal={proposal} />
}

function WorkspaceCreationProposal({proposal}: {proposal: WorkspaceProposal}) {
  const [prepared, setPrepared] = useState<Prepared | null>(null)
  const [operation, setOperation] = useState<Operation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const isDocument = proposal.kind === 'document' || proposal.kind === 'document_edit'
  const isEdit = proposal.kind.endsWith('_edit')
  const base = isDocument ? '/api/documents' : '/api/sheets'
  const title = proposal.kind === 'document' ? proposal.document.title
    : proposal.kind === 'spreadsheet' ? proposal.spreadsheet.title
      : proposal.kind === 'document_edit' ? `Chỉnh sửa Docs ${proposal.document_edit.document_id}`
        : `Chỉnh sửa Sheets ${proposal.spreadsheet_edit.spreadsheet_id}`

  async function refresh(id: string) {
    const current = await api<Operation>(`${base}/operations/${id}`)
    if (current.state === 'uncertain' && current.resource_id) {
      try {
        await api(`/api/operations/${id}/reconcile`, {method: 'POST'})
        setOperation(await api<Operation>(`${base}/operations/${id}`))
        return
      } catch {
        // Fall back to displaying current state if reconcile is unavailable
      }
    }
    setOperation(current)
  }

  async function act(approve: boolean) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      if (!approve) {
        const response = await api<{data: Prepared}>(`/api/creation/proposals/${proposal.id}/prepare`, {method: 'POST'})
        setPrepared(response.data)
        await refresh(response.data.operation_id)
      } else if (prepared) {
        setOperation({state: 'running'})
        await api(`${base}/approve`, {method: 'POST', body: JSON.stringify({operation_id: prepared.operation_id, approved_digest: prepared.digest})})
        await refresh(prepared.operation_id)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa hoàn tất thao tác.')
      if (prepared) await refresh(prepared.operation_id).catch(() => setOperation({state: 'unknown'}))
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return <section aria-label={`Bản đề xuất: ${title}`} className="artifact-editor creation-preview">
    <header><div><span>{isDocument ? 'Google Docs' : 'Google Sheets'}</span><h3>{title}</h3></div></header>
    <p>Đây là bản xem trước. Veridra chưa {isEdit ? 'áp dụng thay đổi' : 'tạo file'} cho đến khi bạn xác nhận.</p>
    <details open><summary>{isEdit ? 'Thay đổi sẽ áp dụng' : 'Nội dung sẽ tạo'}</summary>
      {proposal.kind === 'document' ? proposal.document.blocks.map((block, index) => {
        const tableNumber = proposal.document.blocks.slice(0, index + 1).filter(item => item.kind === 'table').length
        return block.kind === 'table'
          ? <div key={index} className="table-scroll document-table-preview" tabIndex={0} aria-label={`Bảng ${tableNumber} trong tài liệu`}>
              <table aria-label={`Bảng ${tableNumber} trong tài liệu`}>
                <thead><tr>{block.rows[0]?.map((cell, column) => <th key={column}>{cell}</th>)}</tr></thead>
                <tbody>{block.rows.slice(1).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>
          : <div key={index} className={`document-preview-block document-preview-block--${block.style.toLowerCase()}`}>{block.text}</div>
      }) : proposal.kind === 'spreadsheet' ? <SheetPreview proposal={proposal} />
        : proposal.kind === 'document_edit' ? <section className="edit-diff"><del>{proposal.document_edit.old_text}</del><ins>{proposal.document_edit.new_text || '(xóa đoạn này)'}</ins></section>
          : <section><p>Tab <strong>{proposal.spreadsheet_edit.sheet_title}</strong>, vùng <code>{proposal.spreadsheet_edit.range_a1}</code></p><pre>{proposal.spreadsheet_edit.new_values.map(row => row.map(cellText).join(' | ')).join('\n')}</pre></section>}
    </details>
    {error ? <ErrorState message={error} /> : null}
    {!prepared ? <Button disabled={busy} onClick={() => void act(false)}>{busy ? 'Đang kiểm tra…' : 'Kiểm tra quyền và chuẩn bị'}</Button> : null}
    {prepared && operation?.state === 'pending' ? <Button appearance="primary" disabled={busy} onClick={() => void act(true)}>Tôi xác nhận {isEdit ? 'áp dụng bản sửa này' : 'tạo đúng nội dung này'}</Button> : null}
    {prepared ? <Button disabled={busy} onClick={() => void refresh(prepared.operation_id).catch(reason => setError(reason.message))}>Kiểm tra trạng thái</Button> : null}
    {operation ? <p role="status">{operationText(operation.state)}</p> : null}
    {operation?.result?.verified && operation.result.url ? <a href={operation.result.url} target="_blank" rel="noreferrer">Mở file đã kiểm tra nội dung</a> : null}
    {operation?.resource_id && operation.state !== 'succeeded' ? <p>Mã file đã nhận: <code>{operation.resource_id}</code></p> : null}
    <p className="measurement-note">
      Google Workspace chỉ được ghi sau bước xác nhận phía trên.{' '}
      <a href="/api/auth/google?capability=workspace">Cập nhật quyền Docs/Sheets</a>
    </p>
  </section>
}
