import { Button } from '@fluentui/react-components'
import { useRef, useState } from 'react'
import { api } from '../api'
import { ErrorState } from './AsyncState'
import { EmailProposal, type EmailProposalData } from './EmailProposal'

type Formula = {function: string; column: number; start_row: number; end_row: number}
type Cell = string | number | boolean | Formula | null
type VisualSpec = {type: string; title: string; subtitle: string; sections: {title: string; body: string; value?: string}[]}
export type Proposal = {id: string} & (
  {kind: 'document'; document: {title: string; blocks: {text: string; style: string}[]}} |
  {kind: 'spreadsheet'; spreadsheet: {title: string; tabs: {
    title: string; headers: string[]; rows: Cell[][];
    chart: {title: string; kind: 'COLUMN' | 'BAR' | 'LINE'; label_column: number; value_column: number} | null
  }[]}} |
  {kind: 'presentation'; presentation: {title: string; slides: {title: string; bullets: string[]; speaker_notes: string; visual: VisualSpec | null}[]}} |
  {kind: 'visual'; visual: VisualSpec} |
  {kind: 'document_edit'; document_edit: {document_id: string; tab_id?: string; old_text: string; new_text: string}} |
  {kind: 'spreadsheet_edit'; spreadsheet_edit: {spreadsheet_id: string; sheet_title: string; range_a1: string; new_values: Cell[][]}} |
  {kind: 'presentation_edit'; presentation_edit: {presentation_id: string; replacements: {old_text: string; new_text: string}[]; add_slides: {title: string; bullets: string[]; speaker_notes?: string; visual?: VisualSpec | null}[]; delete_slide_ids: string[]}} |
  {kind: 'email'; email: EmailProposalData}
)
type Prepared = {operation_id: string; digest: string; state: string}
type Operation = {state: string; resource_id?: string; error_code?: string; result?: {url?: string; verified?: boolean}}

function cellText(cell: Cell): string {
  if (cell === null) return ''
  if (typeof cell !== 'object') return String(cell)
  const column = String.fromCharCode(65 + cell.column)
  return `=${cell.function}(${column}${cell.start_row + 2}:${column}${cell.end_row + 1})`
}

/** A model proposes content; only this explicit user action approves a Google write. */
export function CreationProposal({proposal}: {proposal: Proposal}) {
  if (proposal.kind === 'email') {
    return <EmailProposal email={proposal.email} />
  }

  return <WorkspaceCreationProposal proposal={proposal} />
}

function WorkspaceCreationProposal({proposal}: {proposal: Exclude<Proposal, {kind: 'email'}>}) {
  const [prepared, setPrepared] = useState<Prepared | null>(null)
  const [operation, setOperation] = useState<Operation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [visualResult, setVisualResult] = useState<{png_url: string; svg_url: string} | null>(null)
  const lock = useRef(false)
  const isDocument = proposal.kind === 'document' || proposal.kind === 'document_edit'
  const isSpreadsheet = proposal.kind === 'spreadsheet' || proposal.kind === 'spreadsheet_edit'
  const isEdit = proposal.kind.endsWith('_edit')
  const base = isDocument ? '/api/documents' : isSpreadsheet ? '/api/sheets' : '/api/slides'
  const title = proposal.kind === 'document' ? proposal.document.title
    : proposal.kind === 'spreadsheet' ? proposal.spreadsheet.title
      : proposal.kind === 'presentation' ? proposal.presentation.title
        : proposal.kind === 'visual' ? proposal.visual.title
          : proposal.kind === 'document_edit' ? `Chỉnh sửa Docs ${proposal.document_edit.document_id}`
            : proposal.kind === 'spreadsheet_edit' ? `Chỉnh sửa Sheets ${proposal.spreadsheet_edit.spreadsheet_id}`
              : `Chỉnh sửa Slides ${proposal.presentation_edit.presentation_id}`

  async function refresh(id: string) {
    const current = await api<Operation>(`${base}/operations/${id}`)
    setOperation(current)
  }
  async function act(approve: boolean) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try {
      if (!approve) {
        const response = await api<{data: Prepared & {png_url?: string; svg_url?: string}}>(`/api/creation/proposals/${proposal.id}/prepare`, {method: 'POST'})
        if (proposal.kind === 'visual' && response.data.png_url && response.data.svg_url) {
          setVisualResult({png_url: response.data.png_url, svg_url: response.data.svg_url})
          return
        }
        setPrepared(response.data)
        await refresh(response.data.operation_id)
      } else if (prepared) {
        // Disable approval immediately. If the response is lost, inspect status
        // instead of blindly resending an external write with a new request key.
        setOperation({state: 'running'})
        await api(`${base}/approve`, {method: 'POST', body: JSON.stringify({
          operation_id: prepared.operation_id, approved_digest: prepared.digest,
        })})
        await refresh(prepared.operation_id)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa hoàn tất thao tác.')
      if (prepared) await refresh(prepared.operation_id).catch(() => setOperation({state: 'unknown'}))
    } finally { lock.current = false; setBusy(false) }
  }
  return <section aria-label={`Bản đề xuất: ${title}`} className="artifact-editor">
    <h3>{title}</h3>
    <p>Bản đề xuất {isDocument ? 'Google Docs' : isSpreadsheet ? 'Google Sheets' : proposal.kind === 'visual' ? 'visual local' : 'Google Slides'} — chưa {isEdit ? 'áp dụng thay đổi' : 'tạo đầu ra'} cho đến khi bạn xác nhận.</p>
    <details><summary>{isEdit ? 'Xem chính xác thay đổi sẽ áp dụng' : 'Xem toàn bộ nội dung sẽ tạo'}</summary>
      {proposal.kind === 'document' ? proposal.document.blocks.map((block, i) =>
        <p key={i} style={{whiteSpace: 'pre-wrap'}}>{block.style !== 'NORMAL_TEXT' ? <strong>{block.text}</strong> : block.text}</p>
      ) : proposal.kind === 'spreadsheet' ? proposal.spreadsheet.tabs.map((tab, i) => <section key={i}>
        <h4>{tab.title}</h4>
        <div className="table-scroll" style={{overflowX: 'auto'}} tabIndex={0} aria-label={`Dữ liệu ${tab.title}`}>
          <table><thead><tr>{tab.headers.map((header, c) => <th key={c}>{header}</th>)}</tr></thead>
            <tbody>{tab.rows.map((row, r) => <tr key={r}>{row.map((cell, c) => <td key={c}>{cellText(cell)}</td>)}</tr>)}</tbody>
          </table>
        </div>
        {tab.chart && <p>Biểu đồ {{COLUMN: 'cột', BAR: 'thanh ngang', LINE: 'đường'}[tab.chart.kind] ?? tab.chart.kind}: {tab.chart.title}. Nhãn: {tab.headers[tab.chart.label_column]}; giá trị: {tab.headers[tab.chart.value_column]}.</p>}
      </section>) : proposal.kind === 'presentation' ? proposal.presentation.slides.map((slide, i) => <section key={i} className="proposal-slide">
        <span>Slide {i + 1}</span>
        <h4>{slide.title}</h4>
        <ul>{slide.bullets.map((bullet, j) => <li key={j}>{bullet}</li>)}</ul>
        {slide.speaker_notes && <p><strong>Speaker notes:</strong> {slide.speaker_notes}</p>}
        {slide.visual && <small>Visual: {slide.visual.title}</small>}
      </section>)
        : proposal.kind === 'visual' ? <section><h4>{proposal.visual.title}</h4><p>{proposal.visual.subtitle}</p><ol>{proposal.visual.sections.map((section, i) => <li key={i}><strong>{section.title}</strong> — {section.body}</li>)}</ol></section>
          : proposal.kind === 'document_edit' ? <section className="edit-diff"><del>{proposal.document_edit.old_text}</del><ins>{proposal.document_edit.new_text || '(xóa đoạn này)'}</ins></section>
            : proposal.kind === 'spreadsheet_edit' ? <section><p>Tab <strong>{proposal.spreadsheet_edit.sheet_title}</strong>, range <code>{proposal.spreadsheet_edit.range_a1}</code></p><pre>{proposal.spreadsheet_edit.new_values.map(row => row.map(cellText).join(' | ')).join('\n')}</pre></section>
              : <section>{proposal.presentation_edit.replacements.map((item, index) => <div className="edit-diff" key={index}><del>{item.old_text}</del><ins>{item.new_text || '(xóa đoạn này)'}</ins></div>)}{proposal.presentation_edit.add_slides.length > 0 && <p>Thêm {proposal.presentation_edit.add_slides.length} slide.</p>}{proposal.presentation_edit.delete_slide_ids.length > 0 && <p>Xóa {proposal.presentation_edit.delete_slide_ids.length} slide được chọn.</p>}</section>}
    </details>
    {error && <ErrorState message={error} />}
    {!prepared && !visualResult && <Button disabled={busy} onClick={() => void act(false)}>{busy ? 'Đang chuẩn bị…' : proposal.kind === 'visual' ? 'Tạo PNG + SVG trên máy' : 'Kiểm tra quyền và chuẩn bị'}</Button>}
    {prepared && operation?.state === 'pending' && <Button appearance="primary" disabled={busy} onClick={() => void act(true)}>
      Tôi xác nhận {isEdit ? 'áp dụng đúng bản sửa này' : 'tạo đúng bản này'}
    </Button>}
    {prepared && <Button disabled={busy} onClick={() => void refresh(prepared.operation_id).catch(e => setError(e.message))}>Kiểm tra trạng thái</Button>}
    {operation && <p role="status">{
      operation.state === 'succeeded' ? 'Đã hoàn tất và kiểm tra lại nội dung.'
        : operation.state === 'pending' ? 'Sẵn sàng chờ bạn xác nhận. Bản duyệt có hiệu lực 30 phút.'
          : operation.state === 'running' ? 'Đang thực hiện và đọc lại kết quả để kiểm tra…'
            : operation.state === 'uncertain' ? 'Chưa xác minh được kết quả. Không gửi lại yêu cầu; hãy dùng “Kiểm tra trạng thái”.'
              : operation.state === 'failed' ? 'Không thể hoàn tất thao tác. Xem thông báo lỗi rồi thử lại sau khi xử lý nguyên nhân.'
                : 'Chưa xác định được trạng thái. Hãy dùng “Kiểm tra trạng thái”.'
    }</p>}
    {operation?.result?.verified && operation.result.url && <a href={operation.result.url} target="_blank" rel="noreferrer">Mở file đã kiểm tra nội dung</a>}
    {visualResult && <div className="proposal-visual-result"><img src={visualResult.png_url} alt={`Visual ${title}`} /><a href={visualResult.png_url} download>Tải PNG</a><a href={visualResult.svg_url} download>Tải SVG</a></div>}
    {operation?.resource_id && operation.state !== 'succeeded' && <p>Mã file đã nhận: <code>{operation.resource_id}</code></p>}
    <p className="measurement-note">{proposal.kind === 'visual' ? 'Visual chỉ được render và lưu trên máy này.' : 'Cần quyền tạo file của ứng dụng và kết nối Workspace.'} Không có phí gọi model thêm khi xác nhận.
      {proposal.kind !== 'visual' && <> <a href="/api/auth/google?capability=workspace">Kết nối quyền tạo tài liệu Google</a></>}
    </p>
  </section>
}
