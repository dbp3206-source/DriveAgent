import { Button, Input, Select, Textarea } from '@fluentui/react-components'
import { ArrowDownload20Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState, LoadingState } from '../components/AsyncState'

type Section = {title: string; body: string; value?: string}
type Visual = {id: string; title: string; kind: string; png_url: string; svg_url: string; spec: unknown}

export function VisualsPage() {
  const [items, setItems] = useState<Visual[]>([])
  const [title, setTitle] = useState('Lộ trình học tập')
  const [subtitle, setSubtitle] = useState('Một visual gọn để dùng lại trong báo cáo và slide')
  const [kind, setKind] = useState('timeline')
  const [sections, setSections] = useState('Khám phá | Xác định mục tiêu\nThực hành | Làm một ví dụ nhỏ\nĐánh giá | Kiểm tra và cải thiện')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    try { setItems((await api<{items: Visual[]}>('/api/visuals')).items) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Không tải được visual.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  async function render() {
    const parsed: Section[] = sections.split('\n').map(line => {
      const [heading, ...rest] = line.split('|')
      return {title: (heading ?? '').trim(), body: rest.join('|').trim()}
    }).filter(item => item.title)
    if (!parsed.length) { setError('Cần ít nhất một mục nội dung.'); return }
    setBusy(true); setError('')
    try {
      await api('/api/visuals', {method: 'POST', body: JSON.stringify({visual: {
        type: kind, title, subtitle, sections: parsed, connections: [], accent: '#4f6df5',
      }})})
      await load()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không tạo được visual.') }
    finally { setBusy(false) }
  }

  return <section className="stack-page visual-studio">
    <header className="page-heading"><div><p className="home-kicker">Local Visual Creator</p><h2>Biến ý tưởng thành visual dùng được.</h2><p>Tạo PNG và SVG ngay trên máy, không dùng API ảnh trả phí. Mỗi visual chỉ thuộc tài khoản của bạn.</p></div></header>
    {error && <ErrorState message={error} />}
    <div className="visual-studio__layout">
      <form className="artifact-editor" onSubmit={event => {event.preventDefault(); void render()}}>
        <label className="artifact-label" htmlFor="visual-title">Tiêu đề</label>
        <Input id="visual-title" value={title} maxLength={120} onChange={(_, d) => setTitle(d.value)} />
        <label className="artifact-label" htmlFor="visual-subtitle">Dòng giải thích</label>
        <Input id="visual-subtitle" value={subtitle} maxLength={240} onChange={(_, d) => setSubtitle(d.value)} />
        <label className="artifact-label" htmlFor="visual-kind">Kiểu trình bày</label>
        <Select id="visual-kind" value={kind} onChange={(_, d) => setKind(d.value)}>
          <option value="timeline">Dòng thời gian</option><option value="flowchart">Luồng công việc</option>
          <option value="architecture">Kiến trúc</option><option value="comparison">So sánh</option>
          <option value="infographic">Infographic</option><option value="chart">Chart card</option><option value="card">Visual card</option>
        </Select>
        <label className="artifact-label" htmlFor="visual-sections">Các mục — mỗi dòng theo dạng “Tiêu đề | Nội dung”</label>
        <Textarea id="visual-sections" rows={8} value={sections} onChange={(_, d) => setSections(d.value)} />
        <Button appearance="primary" type="submit" disabled={busy || !title.trim()}>{busy ? 'Đang dựng…' : 'Tạo PNG + SVG'}</Button>
        <p className="measurement-note">Renderer quyết định, không gọi Gemini. Tệp được kiểm tra tồn tại trước khi ghi nhận hoàn tất.</p>
      </form>
      <section className="visual-library" aria-label="Thư viện visual">
        <h3>Thư viện của bạn</h3>
        {loading ? <LoadingState label="Đang tải visual…" /> : !items.length ? <p className="rail-empty">Chưa có visual. Tạo bản đầu tiên ở bên trái.</p> :
          <div className="visual-grid">{items.map(item => <article className="visual-tile" key={item.id}>
            <img src={item.png_url} alt={`Visual ${item.title}`} loading="lazy" />
            <div><span>{item.kind}</span><h4>{item.title}</h4><nav aria-label={`Tải ${item.title}`}><Button as="a" href={item.png_url} download icon={<ArrowDownload20Regular />}>PNG</Button><Button as="a" href={item.svg_url} download>SVG</Button></nav></div>
          </article>)}</div>}
      </section>
    </div>
  </section>
}
