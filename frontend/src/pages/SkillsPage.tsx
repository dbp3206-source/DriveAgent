import { Button, Input, Textarea } from '@fluentui/react-components'
import { Add20Regular, Archive20Regular, Play20Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState, LoadingState } from '../components/AsyncState'

type Skill = {id: string; name: string; title: string; description: string; goal: string; procedure: string[]; constraints: string[]; preferred_capabilities: string[]; output_format: string; revision: number; active: boolean}
type SkillRunResult = {goal: string; procedure: string[]; constraints: string[]; output_format: string; preferred_capabilities: string[]}

const emptySkill = (): Skill => ({id: '', name: '', title: '', description: '', goal: '', procedure: [''], constraints: [], preferred_capabilities: [], output_format: 'markdown', revision: 0, active: true})

export function SkillsPage() {
  const [items, setItems] = useState<Skill[]>([])
  const [selected, setSelected] = useState<Skill>(emptySkill)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [runResult, setRunResult] = useState<SkillRunResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    try { setItems((await api<{data: {items: Skill[]}}>('/api/skills')).data.items) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Không tải được Skills.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  async function save() {
    setBusy(true); setError('')
    try {
      const payload = {skill: {name: selected.name, title: selected.title, description: selected.description, goal: selected.goal, procedure: selected.procedure.filter(Boolean), constraints: selected.constraints.filter(Boolean), preferred_capabilities: selected.preferred_capabilities, output_format: selected.output_format}, expected_revision: selected.revision || null}
      const result = await api<{data: Skill}>('/api/skills', {method: 'POST', body: JSON.stringify(payload)})
      setSelected(result.data); await load()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không lưu được skill.') }
    finally { setBusy(false) }
  }
  async function run() {
    setBusy(true); setError(''); setRunResult(null)
    try {
      const result = await api<{data: SkillRunResult}>('/api/skills/run', {method: 'POST', body: JSON.stringify({name: selected.name, inputs})})
      setRunResult(result.data)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không chạy được skill.') }
    finally { setBusy(false) }
  }
  async function archive() {
    setBusy(true); setError('')
    try { await api('/api/skills/archive', {method: 'POST', body: JSON.stringify({skill_id: selected.id})}); setSelected(emptySkill()); await load() }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Không cất được skill.') }
    finally { setBusy(false) }
  }

  const setLines = (key: 'procedure' | 'constraints', text: string) => setSelected({...selected, [key]: text.split('\n')})
  const placeholders = [...new Set(
    [selected.goal, ...selected.procedure, ...selected.constraints, selected.output_format]
      .flatMap(value => [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map(match => match[1]!)),
  )]
  return <section className="stack-page skills-page">
    <header className="page-heading"><div><p className="home-kicker">Reusable Skills</p><h2>Dạy Agent cách bạn muốn làm việc?</h2><p>Lưu mục tiêu, trình tự và nguyên tắc — không ghi lại cứng một chuỗi tool. Mỗi lần chạy sẽ lấy dữ liệu mới.</p></div></header>
    {error && <ErrorState message={error} />}
    <div className="artifact-workbench">
      <aside className="artifact-list">
        <Button appearance="primary" icon={<Add20Regular />} onClick={() => setSelected(emptySkill())}>Tạo skill mới</Button>
        <p className="rail-caption">Skill đang dùng</p>
        {loading ? <LoadingState label="Đang tải…" /> : items.map(item => <button type="button" key={item.id} className={`artifact-item-card ${selected.id === item.id ? 'artifact-item-card--active' : ''}`} onClick={() => {setSelected(item); setRunResult(null)}}><strong>{item.title}</strong><small>{item.name} · v{item.revision}</small></button>)}
      </aside>
      <form className="artifact-editor" onSubmit={event => {event.preventDefault(); void save()}}>
        <div className="skill-field-row"><div><label className="artifact-label" htmlFor="skill-name">Tên kỹ thuật</label><Input id="skill-name" disabled={Boolean(selected.id)} value={selected.name} placeholder="project_presentation" onChange={(_, d) => setSelected({...selected, name: d.value.toLowerCase().replace(/[^a-z0-9_]/g, '_')})} /></div><div><label className="artifact-label" htmlFor="skill-title">Tên dễ nhớ</label><Input id="skill-title" value={selected.title} placeholder="Tạo bộ slide môn học" onChange={(_, d) => setSelected({...selected, title: d.value})} /></div></div>
        <label className="artifact-label" htmlFor="skill-description">Mô tả</label><Input id="skill-description" value={selected.description} onChange={(_, d) => setSelected({...selected, description: d.value})} />
        <label className="artifact-label" htmlFor="skill-goal">Kết quả cần đạt</label><Textarea id="skill-goal" value={selected.goal} onChange={(_, d) => setSelected({...selected, goal: d.value})} />
        <label className="artifact-label" htmlFor="skill-steps">Các bước — mỗi dòng một bước; dùng {'{project}'} cho đầu vào</label><Textarea id="skill-steps" rows={7} value={selected.procedure.join('\n')} onChange={(_, d) => setLines('procedure', d.value)} />
        <label className="artifact-label" htmlFor="skill-rules">Nguyên tắc — mỗi dòng một điều</label><Textarea id="skill-rules" rows={4} value={selected.constraints.join('\n')} onChange={(_, d) => setLines('constraints', d.value)} />
        <label className="artifact-label" htmlFor="skill-output">Định dạng đầu ra</label><Input id="skill-output" value={selected.output_format} onChange={(_, d) => setSelected({...selected, output_format: d.value})} />
        <div className="artifact-actions"><Button type="submit" appearance="primary" disabled={busy}>Lưu skill</Button>{selected.id && <Button icon={<Archive20Regular />} disabled={busy} onClick={() => void archive()}>Cất skill</Button>}</div>
        {selected.id && <section className="skill-runner"><h3>Chạy thử procedure</h3><p>Điền thông tin của lần làm việc này. Agent sẽ không dùng lại dữ liệu cũ.</p>
          {placeholders.map(name => <div key={name}><label className="artifact-label" htmlFor={`skill-input-${name}`}>{name}</label><Input id={`skill-input-${name}`} value={inputs[name] ?? ''} onChange={(_, d) => setInputs({...inputs, [name]: d.value})} /></div>)}
          <Button icon={<Play20Regular />} disabled={busy || placeholders.some(name => !inputs[name]?.trim())} onClick={() => void run()}>Nạp procedure</Button>
          {runResult && <div className="skill-run-result"><strong>Mục tiêu</strong><p>{runResult.goal}</p><strong>Các bước sẽ làm</strong><ol>{runResult.procedure.map((step, index) => <li key={index}>{step}</li>)}</ol><strong>Đầu ra</strong><p>{runResult.output_format}</p></div>}
        </section>}
      </form>
    </div>
  </section>
}
