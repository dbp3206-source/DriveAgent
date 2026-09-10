import { Button } from '@fluentui/react-components'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState } from '../components/AsyncState'

interface Source { id: string; name: string; characters: number }

export function LocalSourcesPage() {
  const [sources, setSources] = useState<Source[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function load() {
    try { setSources(await api<Source[]>('/api/local-sources')) }
    catch(e) { setError(e instanceof Error ? e.message : 'Không tải được tài liệu.') }
  }
  useEffect(() => { void load() }, [])
  async function upload() {
    if (!file) return
    if (file.size > 2000000) { setError('Tệp vượt 2 MB. Hãy chia nhỏ trước khi import.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/local-sources?name=${encodeURIComponent(file.name)}`, {
        method:'POST', body:file, credentials:'include', headers:{'Content-Type':'application/octet-stream'},
      })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Không import được tệp.')
      setNotice(`Đã lưu ${result.name}. Bạn có thể hỏi trong Trò chuyện và nói rõ tên tệp local.`)
      await load()
    } catch(e) { setError(e instanceof Error ? e.message : 'Lỗi import tài liệu.') }
    finally { setBusy(false) }
  }
  return <section className="stack-page">
    <div className="page-heading"><div><h2>Tài liệu ngay trên máy bạn</h2>
      <p>Import TXT, Markdown, CSV hoặc notebook UTF-8. Tối đa 2 MB và 100.000 ký tự mỗi tệp. Không chạy mã trong notebook.</p>
    </div></div>
    <p>File được lưu riêng trên máy. Khi bạn hỏi nội dung, phần văn bản được Agent sử dụng sẽ gửi đến Gemini. Đây không phải chế độ AI offline.</p>
    <label>Chọn tệp<input type="file" accept=".txt,.md,.csv,.ipynb" disabled={busy}
      onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
    <Button appearance="primary" disabled={busy || !file} onClick={() => void upload()}>{busy ? 'Đang import…' : 'Lưu tài liệu trên máy'}</Button>
    {error && <ErrorState message={error} />}<p role="status">{notice}</p>
    <p className="measurement-note">Hiện tìm theo tên và đọc văn bản; chưa phải tìm kiếm vector. PDF/DOCX/XLSX local chưa hỗ trợ ở màn hình này. Bản trùng nội dung không tạo thêm tài liệu.</p>
    {!sources.length ? <p>Chưa có tài liệu local.</p> : <ul>{sources.map(source => <li key={source.id}>
      <a href={`/api/local-sources/${source.id}/text`} target="_blank" rel="noreferrer">{source.name}</a>
      {' · '}{source.characters.toLocaleString('vi-VN')} ký tự
    </li>)}</ul>}
  </section>
}
