import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Spinner,
} from '@fluentui/react-components'
import {
  ArrowRight20Regular,
  BrainCircuit20Regular,
  Chat20Regular,
  Checkmark20Regular,
  Copy20Regular,
  Database20Regular,
  Dismiss20Regular,
  DocumentAdd24Regular,
  DocumentText20Regular,
  Folder20Regular,
  Laptop20Regular,
  Open20Regular,
  Sparkle20Regular,
} from '@fluentui/react-icons'
import { DragEvent, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { EmptyState, ErrorState } from '../components/AsyncState'

interface Source {
  id: string
  name: string
  characters: number
}

type PdfJob = {
  id: string; name: string; status: string; stage: string; pages: number
  processed_pages: number; source_id: string | null; error_code: string | null
  page_results: Array<{page: number; status: string; confidence: number | null; error_code: string | null}>
}
const ACCEPTED = ['txt', 'md', 'csv', 'ipynb', 'pdf']

function getFormatInfo(name: string) {
  const ext = name.split('.').pop()?.toUpperCase() ?? 'TXT'
  switch (ext) {
    case 'PDF':
      return { label: '.PDF', badgeClass: 'format-badge--txt' }
    case 'MD':
      return { label: '.MD', badgeClass: 'format-badge--md' }
    case 'CSV':
      return { label: '.CSV', badgeClass: 'format-badge--csv' }
    case 'IPYNB':
      return { label: '.IPYNB', badgeClass: 'format-badge--ipynb' }
    case 'TXT':
    default:
      return { label: '.TXT', badgeClass: 'format-badge--txt' }
  }
}

export function LocalSourcesPage() {
  const [sources, setSources] = useState<Source[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pdfJobs, setPdfJobs] = useState<PdfJob[]>([])
  const picker = useRef<HTMLInputElement>(null)

  // Quick Preview state
  const [previewSource, setPreviewSource] = useState<Source | null>(null)
  const [previewText, setPreviewText] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [previewCopied, setPreviewCopied] = useState(false)

  async function load() {
    try {
      setSources(await api<Source[]>('/api/local-sources'))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được tài liệu.')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let polling = false
    async function poll() {
      if (polling) return
      polling = true
      try {
        const jobs = await api<PdfJob[]>('/api/local-sources/pdf-jobs', { signal: controller.signal })
        if (!controller.signal.aborted) {
          setPdfJobs(jobs)
          if (jobs.some(job => job.source_id)) {
            const updated = await api<Source[]>('/api/local-sources', { signal: controller.signal })
            if (!controller.signal.aborted) setSources(updated)
          }
        }
      } catch (caught) {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Không đọc được tiến độ PDF.')
      } finally { polling = false }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 3000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [])

  async function jobAction(job: PdfJob, action: 'cancel' | 'resume') {
    try {
      const updated = await api<PdfJob>(`/api/local-sources/pdf-jobs/${job.id}/${action}`, { method: 'POST' })
      setPdfJobs(current => current.map(value => value.id === updated.id ? updated : value))
      setError('')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không đổi được trạng thái PDF.') }
  }

  function choose(next: File | null) {
    setError('')
    setNotice('')
    if (!next) {
      setFile(null)
      return
    }
    const extension = next.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ACCEPTED.includes(extension)) {
      setError('Hãy chọn PDF, TXT, Markdown, CSV hoặc notebook IPYNB.')
      setFile(null)
      return
    }
    if (next.size > (extension === 'pdf' ? 25 * 1024 * 1024 : 2_000_000)) {
      setError(extension === 'pdf' ? 'PDF vượt 25 MiB.' : 'Tệp vượt 2 MB. Hãy chia nhỏ trước khi import.')
      setFile(null)
      return
    }
    setFile(next)
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files[0] ?? null)
  }

  async function upload() {
    if (!file) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/local-sources?name=${encodeURIComponent(file.name)}`, {
        method: 'POST',
        body: file,
        credentials: 'include',
        headers: { 'Content-Type': 'application/octet-stream' },
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(typeof result.detail === 'string' ? result.detail : 'Không import được tệp.')
      }
      if (result.kind === 'pdf_job') {
        setPdfJobs(current => [result, ...current.filter(job => job.id !== result.id)])
        setNotice(`Đã nhận “${result.name}”. PDF được xử lý nền theo trang; kiểm tra tiến độ và cảnh báo trước khi hỏi.`)
      } else setNotice(`Đã lưu “${result.name}”. Trong Chat, gõ /local để chỉ tìm trong tài liệu trên máy.`)
      setFile(null)
      if (picker.current) picker.current.value = ''
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Lỗi import tài liệu.')
    } finally {
      setBusy(false)
    }
  }

  function handleChatNow(fileName: string) {
    const prompt = `/local ${fileName} `
    try {
      sessionStorage.setItem('drive_agent_draft_input', prompt)
      sessionStorage.setItem(
        'drive_agent_chat_launch',
        JSON.stringify({ prompt, controls: { domain: 'all', skill: 'general' } })
      )
      window.dispatchEvent(
        new CustomEvent('driveagent:chat-launch', {
          detail: { prompt, controls: { domain: 'all', skill: 'general' } },
        })
      )
    } catch {
      /* storage fallback */
    }
    window.location.hash = '#/chat'
  }

  async function openPreview(source: Source) {
    setPreviewSource(source)
    setPreviewLoading(true)
    setPreviewError('')
    setPreviewCopied(false)
    setPreviewText('')
    try {
      const res = await fetch(`/api/local-sources/${source.id}/text`, {
        credentials: 'include',
      })
      if (!res.ok) throw new Error('Không thể tải nội dung tệp.')
      const text = await res.text()
      setPreviewText(text)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Lỗi tải tệp.')
    } finally {
      setPreviewLoading(false)
    }
  }

  function copyPreviewText() {
    if (!previewText) return
    void navigator.clipboard.writeText(previewText).then(() => {
      setPreviewCopied(true)
      setTimeout(() => setPreviewCopied(false), 2000)
    })
  }

  const totalCharacters = sources.reduce((sum, s) => sum + s.characters, 0)

  return (
    <section className="stack-page local-library local-vault-page">
      {/* Hero Section */}
      <header className="page-heading local-vault-hero">
        <div>
          <div className="local-vault-kicker">
            <span className="kicker-pulse-dot" />
            <span>🔒 LƯU TRÊN MÁY · NỘI DUNG GỬI GEMINI KHI HỎI</span>
          </div>
          <h2>Kho Tri Thức Cục Bộ (Private Knowledge Vault)</h2>
          <p className="local-vault-subtitle">
            Tài liệu được lưu cục bộ trên máy. Khi bạn yêu cầu phân tích tài liệu, nội dung liên quan và câu hỏi được gửi tới Google Gemini để tạo câu trả lời.
          </p>
        </div>

        {/* 3 Dynamic Metric Cards */}
        <div className="local-vault-metrics" aria-label="Thống kê kho tri thức">
          <div className="metric-card">
            <div className="metric-card__header">
              <Folder20Regular className="metric-card__icon metric-card__icon--cyan" />
              <span className="metric-card__label">Tài liệu đã lưu</span>
            </div>
            <strong className="metric-card__value">{sources.length.toLocaleString('vi-VN')}</strong>
            <span className="metric-card__caption">Tệp khả dụng trên máy</span>
          </div>

          <div className="metric-card">
            <div className="metric-card__header">
              <Database20Regular className="metric-card__icon metric-card__icon--purple" />
              <span className="metric-card__label">Tổng ký tự chỉ mục</span>
            </div>
            <strong className="metric-card__value">{totalCharacters.toLocaleString('vi-VN')}</strong>
            <span className="metric-card__caption">Trích xuất văn bản sạch</span>
          </div>

          <div className="metric-card">
            <div className="metric-card__header">
              <BrainCircuit20Regular className="metric-card__icon metric-card__icon--emerald" />
              <span className="metric-card__label">Định dạng hỗ trợ</span>
            </div>
            <div className="metric-card__badges">
              <span className="format-badge format-badge--md">.MD</span>
              <span className="format-badge format-badge--csv">.CSV</span>
              <span className="format-badge format-badge--ipynb">.IPYNB</span>
              <span className="format-badge format-badge--txt">.TXT</span>
              <span className="format-badge format-badge--txt" title="Chỉ PDF có lớp văn bản; không hỗ trợ bản scan">.PDF có văn bản</span>
            </div>
            <span className="metric-card__caption">PDF có văn bản: 25 MiB · tệp văn bản: 2 MB. Không hỗ trợ PDF scan/ảnh.</span>
          </div>
        </div>
      </header>

      {pdfJobs.length ? <section className="readiness-panel" aria-labelledby="pdf-jobs-title">
        <h3 id="pdf-jobs-title">PDF · tiến độ theo trang</h3>
        <p className="measurement-note">Chỉ hỗ trợ PDF có lớp văn bản; OCR/PDF scan nằm ngoài phạm vi. Xử lý tuần tự để giữ Chat nhẹ; checkpoint được lưu khi đóng tab. “Cần kiểm tra” không có nghĩa là toàn bộ PDF đã đọc thành công.</p>
        {pdfJobs.map(job => <details className="readiness-gate" key={job.id}>
          <summary><span>{job.name}</span><strong>{({ queued: 'Đang xếp hàng', running: 'Đang đọc', completed: 'Đã trích xuất', needs_attention: 'Cần kiểm tra', cancelled: 'Đã hủy', failed: 'Lỗi xử lý' } as Record<string, string>)[job.status] ?? job.status}</strong></summary>
          <p>{job.processed_pages}/{job.pages || '?'} trang · {job.stage === 'keyword_ready' ? 'Đã sẵn sàng tìm văn bản; chưa xác nhận chỉ mục semantic.' : 'Đang chuẩn bị/trích xuất nguồn.'}</p>
          <progress aria-label={`Tiến độ ${job.name}`} max={job.pages || 1} value={job.processed_pages} />
          {job.error_code ? <p role="status">Mã chẩn đoán: <code>{job.error_code}</code>. Trang scan không được dùng làm nguồn; hãy chọn bản PDF có lớp văn bản.</p> : null}
          <div className="page-heading__actions">
            {['queued', 'running'].includes(job.status) ? <Button onClick={() => void jobAction(job, 'cancel')}>Hủy xử lý</Button> : null}
            {['failed', 'cancelled', 'needs_attention'].includes(job.status) ? <Button onClick={() => void jobAction(job, 'resume')}>Tiếp tục từ checkpoint</Button> : null}
            {job.source_id ? <Button onClick={() => handleChatNow(job.name)}>Hỏi phần đã đọc</Button> : null}
          </div>
          {job.page_results.map(page => <p key={page.page}>Trang {page.page}: {({ text: 'Có văn bản', ocr: 'OCR lịch sử — ngoài phạm vi hỗ trợ', unsupported_scan: 'Trang scan — không hỗ trợ OCR', needs_ocr: 'Trang scan — ngoài phạm vi', low_confidence: 'OCR lịch sử chưa tin cậy — không dùng làm nguồn', error: 'Lỗi đọc trang' } as Record<string, string>)[page.status] ?? page.status}{page.confidence == null ? '' : ` · confidence ${page.confidence.toFixed(1)}/100`}{page.error_code ? ` · ${page.error_code}` : ''}</p>)}
        </details>)}
      </section> : null}

      {/* Main Content Layout */}
      <div className="local-library__layout local-vault-layout">
        {/* Left Column: Smart Dropzone & File Staging */}
        <section className="local-vault-uploader" aria-labelledby="local-import-title">
          <h3 id="local-import-title">Nạp tài liệu mới</h3>
          <ul className="local-library__privacy">
            <li><strong>Lưu:</strong> riêng theo tài khoản trên máy này.</li>
            <li><strong>Khi hỏi:</strong> đoạn liên quan được gửi tới Gemini; đây không phải AI offline.</li>
          </ul>

          {!file ? (
            <div
              className={`local-dropzone-smart ${dragging ? 'local-dropzone-smart--active' : ''}`}
              onDragEnter={(event) => {
                event.preventDefault()
                setDragging(true)
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <div className="local-dropzone__halo">
                <DocumentAdd24Regular />
              </div>
              <strong>Kéo thả tệp vào đây hoặc duyệt từ máy</strong>
              <span>PDF có lớp văn bản đến 25 MiB · TXT, Markdown, CSV, IPYNB đến 2 MB. Không đọc PDF scan/ảnh.</span>
              <input
                ref={picker}
                className="visually-hidden"
                type="file"
                aria-label="Chọn tài liệu local để import"
                accept=".txt,.md,.csv,.ipynb,.pdf"
                disabled={busy}
                onChange={(event) => choose(event.target.files?.[0] ?? null)}
              />
              <Button
                type="button"
                appearance="secondary"
                className="local-dropzone-browse-btn"
                disabled={busy}
                onClick={() => picker.current?.click()}
              >
                Chọn từ máy
              </Button>
            </div>
          ) : (
            <div className="local-staging-card">
              <div className="staging-header">
                <span className={`format-badge ${getFormatInfo(file.name).badgeClass}`}>
                  {getFormatInfo(file.name).label}
                </span>
                <span className="staging-validity">
                  <Checkmark20Regular /> Hợp lệ để nạp
                </span>
              </div>
              <div className="staging-body">
                <strong className="staging-filename">{file.name}</strong>
                <span className="staging-filesize">
                  {(file.size / 1024).toFixed(1)} KB · sẵn sàng import
                </span>
              </div>
              <div className="staging-actions">
                <Button
                  appearance="primary"
                  className="staging-upload-btn"
                  disabled={busy}
                  onClick={() => void upload()}
                >
                  {busy ? (
                    <>
                      <Spinner size="tiny" /> Đang nạp…
                    </>
                  ) : (
                    '⚡ Nạp vào Agent'
                  )}
                </Button>
                <Button appearance="subtle" disabled={busy} onClick={() => picker.current?.click()}>
                  Đổi tệp
                </Button>
                <Button appearance="subtle" disabled={busy} onClick={() => setFile(null)}>
                  Huỷ
                </Button>
              </div>
              <input
                ref={picker}
                className="visually-hidden"
                type="file"
                aria-label="Chọn tài liệu local để import"
                accept=".txt,.md,.csv,.ipynb,.pdf"
                disabled={busy}
                onChange={(event) => choose(event.target.files?.[0] ?? null)}
              />
            </div>
          )}

          {error && <ErrorState message={error} />}
          {notice && (
            <p className="local-success" role="status">
              {notice}
            </p>
          )}
        </section>

        {/* Right Column: Knowledge Bento Cards Grid */}
        <section className="local-source-ledger local-vault-ledger" aria-labelledby="local-sources-title">
          <header className="ledger-header">
            <div>
              <span className="ledger-count-pill">{sources.length.toLocaleString('vi-VN')}</span>
              <h3 id="local-sources-title">Tài liệu đã trích xuất</h3>
            </div>
            <small>
              Dùng <code>/local &lt;tên_tệp&gt;</code> trong Chat để chỉ định nguồn
            </small>
          </header>

          {!sources.length ? (
            <EmptyState
              title="Chưa có tài liệu local"
              description="Kéo thả hoặc chọn một tệp văn bản nhỏ để bắt đầu khám phá."
            />
          ) : (
            <div className="local-sources-grid">
              {sources.map((source) => {
                const fmt = getFormatInfo(source.name)
                return (
                  <article key={source.id} className="local-source-card">
                    <div className="source-card__top">
                      <span className={`format-badge ${fmt.badgeClass}`}>{fmt.label}</span>
                      <span className="source-card__chars">
                        {source.characters.toLocaleString('vi-VN')} ký tự
                      </span>
                    </div>
                    <div className="source-card__title" title={source.name}>
                      <DocumentText20Regular className="source-card__icon" />
                      <strong>{source.name}</strong>
                    </div>
                    <div className="source-card__actions">
                      <button
                        type="button"
                        className="source-card-btn source-card-btn--preview"
                        onClick={() => void openPreview(source)}
                        title="Xem trước nội dung"
                      >
                        <DocumentText20Regular /> Xem nhanh
                      </button>
                      <button
                        type="button"
                        className="source-card-btn source-card-btn--chat"
                        onClick={() => handleChatNow(source.name)}
                        title="Mở trong Chat với lệnh /local"
                      >
                        <Chat20Regular /> Chat ngay
                      </button>
                      <a
                        href={`/api/local-sources/${source.id}/text`}
                        target="_blank"
                        rel="noreferrer"
                        className="source-card-btn source-card-btn--external"
                        title="Mở tab riêng"
                      >
                        <Open20Regular />
                      </a>
                    </div>
                  </article>
                )
              })}
            </div>
          )}

          <p className="measurement-note">
            PDF có lớp văn bản giữ vị trí trang để đối chiếu nguồn. Không hỗ trợ đọc chữ trong ảnh, PDF scan hoặc bảng chỉ có dạng ảnh. DOCX và XLSX có thể đọc qua Drive.
          </p>
        </section>
      </div>

      {/* Mini Workflow Diagram Footer */}
      <footer className="local-workflow-footer" aria-label="Quy trình xử lý Private Knowledge Vault">
        <div className="workflow-title">Quy trình xử lý Private Knowledge Vault</div>
        <div className="workflow-steps">
          <div className="workflow-step">
            <div className="workflow-step__badge">1</div>
            <Laptop20Regular className="workflow-step__icon" />
            <div className="workflow-step__info">
              <strong>Tệp máy</strong>
              <span>PDF có văn bản ≤ 25 MiB; TXT, MD, CSV, IPYNB ≤ 2 MB</span>
            </div>
          </div>

          <ArrowRight20Regular className="workflow-arrow" />

          <div className="workflow-step">
            <div className="workflow-step__badge">2</div>
            <BrainCircuit20Regular className="workflow-step__icon" />
            <div className="workflow-step__info">
              <strong>Trích xuất Text</strong>
              <span>Bóc tách text thô & notebook cells</span>
            </div>
          </div>

          <ArrowRight20Regular className="workflow-arrow" />

          <div className="workflow-step">
            <div className="workflow-step__badge">3</div>
            <Database20Regular className="workflow-step__icon" />
            <div className="workflow-step__info">
              <strong>Bộ nhớ tạm</strong>
              <span>Lưu chỉ mục riêng tư, Zero-Cloud</span>
            </div>
          </div>

          <ArrowRight20Regular className="workflow-arrow" />

          <div className="workflow-step">
            <div className="workflow-step__badge">4</div>
            <Sparkle20Regular className="workflow-step__icon" />
            <div className="workflow-step__info">
              <strong>Gemini đọc khi /local</strong>
              <span>Nạp ngữ cảnh liên quan khi truy vấn</span>
            </div>
          </div>
        </div>
      </footer>

      {/* Quick Preview Dialog */}
      <Dialog
        open={Boolean(previewSource)}
        onOpenChange={(_, data) => !data.open && setPreviewSource(null)}
      >
        <DialogSurface className="local-preview-dialog-surface">
          <DialogBody>
            <DialogTitle
              action={
                <Button
                  appearance="subtle"
                  icon={<Dismiss20Regular />}
                  onClick={() => setPreviewSource(null)}
                  aria-label="Đóng"
                />
              }
            >
              <div className="preview-dialog-header">
                <strong>{previewSource?.name}</strong>
                {previewSource && (
                  <span className={`format-badge ${getFormatInfo(previewSource.name).badgeClass}`}>
                    {getFormatInfo(previewSource.name).label}
                  </span>
                )}
                {previewSource && (
                  <span className="preview-dialog-chars">
                    {previewSource.characters.toLocaleString('vi-VN')} ký tự
                  </span>
                )}
              </div>
            </DialogTitle>
            <DialogContent className="preview-dialog-content">
              {previewLoading && (
                <div className="preview-dialog-loading">
                  <Spinner label="Đang tải nội dung tệp..." />
                </div>
              )}
              {previewError && <ErrorState message={previewError} />}
              {!previewLoading && !previewError && (
                <pre className="preview-dialog-pre">
                  <code>{previewText}</code>
                </pre>
              )}
            </DialogContent>
            <DialogActions className="preview-dialog-actions">
              <Button
                appearance="secondary"
                icon={previewCopied ? <Checkmark20Regular /> : <Copy20Regular />}
                onClick={copyPreviewText}
              >
                {previewCopied ? 'Đã chép!' : 'Sao chép'}
              </Button>
              <Button
                appearance="primary"
                icon={<Chat20Regular />}
                onClick={() => previewSource && handleChatNow(previewSource.name)}
              >
                Chat với tệp này
              </Button>
              <Button appearance="subtle" onClick={() => setPreviewSource(null)}>
                Đóng
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
