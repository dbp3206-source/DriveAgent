import {
  Badge,
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableCellLayout,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components'
import {
  ArrowSync24Regular,
  DatabaseArrowDownRegular,
  Dismiss24Regular,
  Eye24Regular,
  Open24Regular,
  Search24Regular,
} from '@fluentui/react-icons'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, formatDate, humanFileSize } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { DriveFile } from '../types'

interface FileList { files: DriveFile[]; next_page_token: string | null }
interface FileContent { file: DriveFile; text: string; truncated: boolean }
interface IndexResult { chunks: number; skipped: boolean; message: string }

function readableType(mime: string) {
  if (mime.includes('document')) return 'Tài liệu'
  if (mime.includes('spreadsheet') || mime.includes('csv')) return 'Bảng tính'
  if (mime.includes('presentation')) return 'Trình chiếu'
  if (mime.includes('pdf')) return 'PDF'
  if (mime.includes('folder')) return 'Thư mục'
  return 'Tệp'
}

export function DrivePage() {
  const [files, setFiles] = useState<DriveFile[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<FileContent | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [indexing, setIndexing] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [nextPage, setNextPage] = useState<string | null>(null)
  const [activeQuery, setActiveQuery] = useState('')
  const [folderStack, setFolderStack] = useState<Array<{ id: string; name: string }>>([])

  const load = useCallback(async (search = '', pageToken: string | null = null, folderId: string | null = null) => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ page_size: '50' })
      if (search.trim()) params.set('query', search.trim())
      if (pageToken) params.set('page_token', pageToken)
      const lastInStack = folderStack[folderStack.length - 1]
      const targetFolderId = folderId !== undefined ? folderId : (lastInStack ? lastInStack.id : null)
      if (targetFolderId && !search.trim()) params.set('folder_id', targetFolderId)
      const result = await api<FileList>(`/api/drive/files?${params}`)
      setFiles((current) => pageToken
        ? [...current, ...result.files.filter((file) => !current.some((old) => old.id === file.id))]
        : result.files)
      setNextPage(result.next_page_token)
      setActiveQuery(search)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải tệp Drive.')
    } finally {
      setLoading(false)
    }
  }, [folderStack])

  useEffect(() => { void load() }, [load])

  function openFolder(folder: DriveFile) {
    const nextStack = [...folderStack, { id: folder.id, name: folder.name }]
    setFolderStack(nextStack)
    setQuery('')
    void load('', null, folder.id)
  }

  function navigateBreadcrumb(index: number) {
    if (index === -1) {
      setFolderStack([])
      setQuery('')
      void load('', null, null)
    } else {
      const nextStack = folderStack.slice(0, index + 1)
      setFolderStack(nextStack)
      setQuery('')
      const lastTarget = nextStack[nextStack.length - 1]
      void load('', null, lastTarget ? lastTarget.id : null)
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault()
    await load(query)
  }

  async function read(file: DriveFile) {
    setError('')
    setPreviewBusy(true)
    setPreview({ file, text: '', truncated: false })
    try {
      setPreview(await api<FileContent>(`/api/drive/files/${file.id}/content`))
    } catch (caught) {
      setPreview(null)
      setError(caught instanceof Error ? caught.message : 'Không thể đọc tệp.')
    } finally {
      setPreviewBusy(false)
    }
  }

  async function index(file: DriveFile) {
    setError('')
    setIndexing(file.id)
    setNotice('')
    try {
      const result = await api<IndexResult>(`/api/drive/files/${file.id}/index`, { method: 'POST' })
      setNotice(`${file.name}: ${result.message}`)
      setFiles((current) => current.map((item) => item.id === file.id ? { ...item, indexed: true } : item))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lập chỉ mục.')
    } finally {
      setIndexing(null)
    }
  }

  return (
    <section className="stack-page">
      <div className="page-heading">
        <div>
          <h2>Tệp bạn đã cấp quyền</h2>
          <p>Danh sách đến trực tiếp từ Drive API. Lập chỉ mục để hỏi đáp có trích dẫn.</p>
        </div>
        <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={() => load(query)}>
          Làm mới
        </Button>
      </div>
      <form className="search-row" onSubmit={search}>
        <Input
          id="drive-search"
          name="query"
          value={query}
          onChange={(_, data) => setQuery(data.value)}
          contentBefore={<Search24Regular />}
          placeholder="Tìm theo tên hoặc nội dung"
          aria-label="Tìm tệp Google Drive"
        />
        <Button appearance="primary" type="submit" disabled={loading}>Tìm kiếm</Button>
      </form>
      {notice ? (
        <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>
      ) : null}
      {error ? <ErrorState message={error} retry={() => load(query)} /> : null}
      {loading ? <LoadingState label="Đang lấy danh sách từ Google Drive" /> : null}
      {!loading && !error && files.length === 0 ? (
        <EmptyState title="Không tìm thấy tệp" description="Hãy đổi từ khóa hoặc kiểm tra quyền Google Drive." />
      ) : null}
      <div className="drive-navigation-bar">
        <div className="drive-breadcrumbs">
          <button
            type="button"
            className={`breadcrumb-btn ${folderStack.length === 0 ? 'breadcrumb-btn--active' : ''}`}
            onClick={() => navigateBreadcrumb(-1)}
          >
            Drive của tôi
          </button>
          {folderStack.map((f, i) => (
            <span key={f.id} className="breadcrumb-segment">
              <span className="breadcrumb-sep">/</span>
              <button
                type="button"
                className={`breadcrumb-btn ${i === folderStack.length - 1 ? 'breadcrumb-btn--active' : ''}`}
                onClick={() => navigateBreadcrumb(i)}
              >
                {f.name}
              </button>
            </span>
          ))}
        </div>
      </div>
      {!loading && files.length > 0 ? (
        <div className="table-scroll">
          <Table aria-label="Danh sách tệp Google Drive">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Tên tệp</TableHeaderCell>
                <TableHeaderCell>Loại</TableHeaderCell>
                <TableHeaderCell>Sửa lần cuối</TableHeaderCell>
                <TableHeaderCell>Kích thước</TableHeaderCell>
                <TableHeaderCell>RAG</TableHeaderCell>
                <TableHeaderCell>Thao tác</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {files.map((file) => (
                <TableRow key={file.id}>
                  <TableCell>
                    {file.mime_type.includes('folder') ? (
                      <button
                        type="button"
                        className="folder-link-btn"
                        onClick={() => openFolder(file)}
                        title="Mở thư mục này"
                      >
                        📁 <strong>{file.name}</strong>
                      </button>
                    ) : (
                      <TableCellLayout>{file.name}</TableCellLayout>
                    )}
                  </TableCell>
                  <TableCell>{readableType(file.mime_type)}</TableCell>
                  <TableCell>{formatDate(file.modified_time)}</TableCell>
                  <TableCell className="numeric">{humanFileSize(file.size)}</TableCell>
                  <TableCell>
                    <Badge appearance="tint" color={file.indexed ? 'success' : 'informative'}>
                      {file.indexed ? 'Đã index' : 'Chưa index'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="row-actions">
                      {!file.mime_type.includes('folder') ? (
                        <Button
                          appearance="subtle"
                          icon={<Eye24Regular />}
                          aria-label={`Đọc ${file.name}`}
                          onClick={() => read(file)}
                        />
                      ) : null}
                      {!file.mime_type.includes('folder') ? (
                        <Button
                          appearance="subtle"
                          icon={indexing === file.id ? <Spinner size="tiny" /> : <DatabaseArrowDownRegular />}
                          aria-label={`Lập chỉ mục ${file.name}`}
                          disabled={indexing !== null}
                          onClick={() => index(file)}
                        />
                      ) : null}
                      {file.web_view_link ? (
                        <Button
                          as="a"
                          href={file.web_view_link}
                          target="_blank"
                          appearance="subtle"
                          icon={<Open24Regular />}
                          aria-label={`Mở ${file.name} trên Google Drive`}
                        />
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}

      {nextPage ? <Button disabled={loading} onClick={() => load(activeQuery, nextPage)}>Tải thêm tệp</Button> : null}

      <Dialog open={Boolean(preview)} onOpenChange={(_, data) => !data.open && setPreview(null)}>
        <DialogSurface className="preview-dialog">
          <DialogBody>
            <DialogTitle action={<Button aria-label="Đóng xem trước" appearance="subtle" icon={<Dismiss24Regular />} onClick={() => setPreview(null)} />}>
              {preview?.file.name}
            </DialogTitle>
            <DialogContent>
              {previewBusy ? <LoadingState label="Đang đọc và chuyển đổi tệp" /> : <pre className="file-preview">{preview?.text}</pre>}
              {preview?.truncated ? <p className="muted">Preview đã được rút gọn để bảo vệ trình duyệt.</p> : null}
            </DialogContent>
            <DialogActions>
              <Button appearance="primary" onClick={() => setPreview(null)}>Đóng</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
