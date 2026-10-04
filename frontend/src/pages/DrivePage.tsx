import {
  Badge,
  Button,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components'
import {
  ArrowSync24Regular,
  DatabaseArrowDownRegular,
  Delete24Regular,
  Open24Regular,
  Search24Regular,
} from '@fluentui/react-icons'
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { api, formatDate, humanFileSize } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { driveFileCapability } from '../driveCapabilities.mjs'
import type { DriveFile } from '../types'

type DriveCapability = { readable: boolean; indexable: boolean; previewMode: 'none' | 'source' | 'brief'; reason: string }
const getDriveCapability = (mimeType: string, fileName: string) => driveFileCapability(mimeType, fileName) as DriveCapability

interface FileList { files: DriveFile[]; next_page_token: string | null }
interface IndexResult { chunks: number; skipped: boolean; message: string }
type DriveItemType = 'all' | 'folders' | 'files'
interface DriveFilters { starred: boolean; itemType: DriveItemType }

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
  const [indexing, setIndexing] = useState<string | null>(null)
  const [unindexing, setUnindexing] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [nextPage, setNextPage] = useState<string | null>(null)
  const [activeQuery, setActiveQuery] = useState('')
  const [starredOnly, setStarredOnly] = useState(false)
  const [itemType, setItemType] = useState<DriveItemType>('all')
  const [folderStack, setFolderStack] = useState<Array<{ id: string; name: string }>>([])
  const listRequest = useRef<AbortController | null>(null)
  const filters = useRef<DriveFilters>({ starred: false, itemType: 'all' })
  const currentFolderId = folderStack[folderStack.length - 1]?.id ?? null

  const load = useCallback(async (search = '', pageToken: string | null = null, folderId: string | null = null) => {
    listRequest.current?.abort()
    const controller = new AbortController()
    listRequest.current = controller
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ page_size: '50' })
      if (search.trim()) params.set('query', search.trim())
      if (pageToken) params.set('page_token', pageToken)
      if (folderId && !search.trim()) params.set('folder_id', folderId)
      if (filters.current.starred) params.set('starred', 'true')
      if (filters.current.itemType !== 'all') params.set('item_type', filters.current.itemType)
      const result = await api<FileList>(`/api/drive/files?${params}`, { signal: controller.signal })
      // A previous folder/search response must never replace the latest selection.
      if (controller.signal.aborted) return
      setFiles((current) => pageToken
        ? [...current, ...result.files.filter((file) => !current.some((old) => old.id === file.id))]
        : result.files)
      setNextPage(result.next_page_token)
      setActiveQuery(search)
    } catch (caught) {
      if (controller.signal.aborted) return
      setError(caught instanceof Error ? caught.message : 'Không thể tải tệp Drive.')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    return () => listRequest.current?.abort()
  }, [load])


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
    await load(query, null, currentFolderId)
  }

  function changeItemType(nextType: DriveItemType) {
    filters.current = { ...filters.current, itemType: nextType }
    setItemType(nextType)
    void load(query, null, currentFolderId)
  }

  function toggleStarredOnly() {
    const nextStarred = !filters.current.starred
    filters.current = { ...filters.current, starred: nextStarred }
    setStarredOnly(nextStarred)
    void load(query, null, currentFolderId)
  }


  async function unindex(file: DriveFile) {
    if (!window.confirm(`Hoàn tác lập chỉ mục cho “${file.name}”? Tệp gốc trên Drive sẽ không bị thay đổi.`)) return
    setError('')
    setUnindexing(file.id)
    setNotice('')
    try {
      const result = await api<{message: string}>(`/api/drive/files/${encodeURIComponent(file.id)}/index`, { method: 'DELETE' })
      setNotice(result.message)
      setFiles(current => current.map(item => item.id === file.id
        ? {...item, indexed: false, index_status: 'not_indexed'}
        : item))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể hoàn tác lập chỉ mục.')
    } finally {
      setUnindexing(null)
    }
  }

  async function index(file: DriveFile) {
    setError('')
    setIndexing(file.id)
    setNotice('')
    try {
      const result = await api<IndexResult>(`/api/drive/files/${file.id}/index`, { method: 'POST' })
      setNotice(`${file.name}: ${result.message}`)
      setFiles((current) => current.map((item) => item.id === file.id
        ? { ...item, indexed: true, index_status: 'fresh' }
        : item))
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
          <h2>Drive của bạn</h2>
          <p>Các mục có hoạt động gần đây được xếp lên trước. Chọn bộ lọc để tìm nhanh thư mục và tài liệu.</p>
        </div>
        <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={() => load(query, null, currentFolderId)}>
          Làm mới
        </Button>
      </div>
      <form className="search-row drive-search-form" onSubmit={search}>
        <Input
          id="drive-search"
          name="query"
          value={query}
          onChange={(_, data) => setQuery(data.value)}
          contentBefore={<Search24Regular />}
          placeholder="Tìm theo tên hoặc nội dung"
          aria-label="Tìm tệp Google Drive"
          className="drive-search-capsule"
        />
        <Button appearance="primary" type="submit" disabled={loading} className="drive-search-btn">Tìm kiếm</Button>
      </form>
      <div className="drive-filter-toolbar" aria-label="Bộ lọc Drive">
        <div className="drive-filter-group" role="group" aria-label="Lọc theo loại">
          <span className="drive-filter-label">Loại</span>
          {([
            ['all', 'Tất cả'],
            ['folders', 'Thư mục'],
            ['files', 'Tệp'],
          ] as const).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              appearance="secondary"
              className={`drive-filter-chip ${itemType === value ? 'drive-filter-chip--selected' : ''}`}
              aria-pressed={itemType === value}
              disabled={loading}
              onClick={() => changeItemType(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <Button
          type="button"
          appearance="secondary"
          className={`drive-filter-chip drive-starred-filter ${starredOnly ? 'drive-filter-chip--selected' : ''}`}
          aria-pressed={starredOnly}
          disabled={loading}
          onClick={toggleStarredOnly}
        >
          Đã gắn sao
        </Button>
        <span className="drive-sort-note">Gần đây trước</span>
      </div>
      {notice ? (
        <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>
      ) : null}
      {error ? <ErrorState message={error} retry={() => load(query, null, currentFolderId)} /> : null}
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
          <Table className="drive-file-table" aria-label="Danh sách tệp Google Drive">
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
              {files.map((file) => {
                const capability = getDriveCapability(file.mime_type, file.name)
                const isFolder = file.mime_type.includes('folder')
                return (
                <TableRow key={file.id}>
                  <TableCell>
                    {isFolder ? (
                      <button
                        type="button"
                        className="folder-link-btn"
                        onClick={() => openFolder(file)}
                        title="Mở thư mục này"
                      >
                        📁 <strong
                          className="drive-file-name"
                          style={{
                            display: 'block',
                            minWidth: 0,
                            maxWidth: '100%',
                            overflowWrap: 'anywhere',
                            wordBreak: 'normal',
                            whiteSpace: 'normal',
                          }}
                        >{file.name}</strong>
                      </button>
                    ) : (
                      <span
                        className="drive-file-name"
                        title={file.name}
                        style={{
                          display: 'block',
                          minWidth: 0,
                          maxWidth: '100%',
                          overflowWrap: 'anywhere',
                          wordBreak: 'normal',
                          whiteSpace: 'normal',
                        }}
                      >{file.name}</span>
                    )}
                  </TableCell>
                  <TableCell>{readableType(file.mime_type)}</TableCell>
                  <TableCell>{formatDate(file.modified_time)}</TableCell>
                  <TableCell className="numeric">{humanFileSize(file.size)}</TableCell>
                  <TableCell>
                    <Badge
                      appearance="tint"
                      color={!capability.indexable
                        ? 'informative'
                        : file.index_status === 'fresh'
                        ? 'success'
                        : file.index_status === 'stale' ? 'warning' : 'informative'}
                      title={!capability.indexable ? capability.reason : undefined}
                    >
                      {!capability.indexable
                        ? (isFolder ? '—' : 'Không hỗ trợ')
                        : file.index_status === 'fresh'
                        ? 'Đã index'
                        : file.index_status === 'stale' ? 'Cần index lại' : 'Chưa index'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="row-actions">
                      {capability.indexable ? (
                        <Button
                          appearance="subtle"
                          icon={indexing === file.id ? <Spinner size="tiny" /> : <DatabaseArrowDownRegular />}
                          aria-label={`${file.index_status === 'stale' ? 'Lập lại' : 'Lập'} chỉ mục ${file.name}`}
                          disabled={indexing !== null}
                          onClick={() => index(file)}
                        />
                      ) : null}
                      {capability.indexable && file.index_status !== 'not_indexed' ? (
                        <Button
                          appearance="subtle"
                          icon={unindexing === file.id ? <Spinner size="tiny" /> : <Delete24Regular />}
                          aria-label={`Hoàn tác lập chỉ mục ${file.name}`}
                          disabled={indexing !== null || unindexing !== null}
                          onClick={() => void unindex(file)}
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
                )
              })}
            </TableBody>
          </Table>
        </div>
      ) : null}

      {nextPage ? <Button disabled={loading} onClick={() => load(activeQuery, nextPage, currentFolderId)}>Tải thêm tệp</Button> : null}

    </section>
  )
}
