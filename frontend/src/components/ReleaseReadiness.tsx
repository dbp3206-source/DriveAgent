import { Button } from '@fluentui/react-components'
import { useEffect, useState } from 'react'
import { api, formatDate } from '../api'

type Readiness = {
  verdict: 'PASS' | 'HOLD'; build_id: string; measured_at: string | null
  score: number | null; threshold: number
  gates: Array<{id: string; label: string; group: string; status: string; reason: string}>
}
const groups: Record<string, string> = {
  regression: 'Regression', business: 'Chất lượng nghiệp vụ',
  governance: 'Governance', operations: 'Vận hành', usability: 'UI / khả dụng',
}

export function ReleaseReadiness() {
  const [data, setData] = useState<Readiness | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api<Readiness>('/api/release/readiness', { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) { setData(result); setError('') } })
      .catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Không đọc được readiness.') })
    return () => controller.abort()
  }, [revision])
  return <section className="readiness-panel" aria-labelledby="readiness-title" aria-busy={!data && !error}>
    <header className="readiness-heading">
      <div><h2 id="readiness-title">Kiểm chứng phiên bản phát hành</h2>
        <p>Closed beta · tối đa 4 người được mời. Điểm offline không thay thế gate live.</p></div>
      <strong className="readiness-status" data-verdict={data?.verdict ?? 'HOLD'}>
        {data?.verdict ?? 'HOLD'}<small>{data?.verdict === 'PASS' ? 'Đủ bằng chứng trong phạm vi đo' : 'Chưa đủ điều kiện phát hành'}</small>
      </strong>
    </header>
    {error ? <div role="alert"><p>{error}</p><Button onClick={() => setRevision(value => value + 1)}>Tải lại gate</Button></div> : null}
    {!data && !error ? <p role="status">Đang đối chiếu build và bằng chứng…</p> : null}
    {data ? <>
      <dl className="readiness-provenance">
        <div><dt>Build fingerprint</dt><dd><code title={data.build_id}>{data.build_id.slice(0, 16)}</code></dd></div>
        <div><dt>Đo cùng build</dt><dd>{data.measured_at ? formatDate(data.measured_at) : 'Chưa có bằng chứng hợp lệ'}</dd></div>
        <div><dt>Benchmark tổng /10</dt><dd>{data.score == null ? 'N/A' : data.score.toFixed(2)} · ngưỡng ≥ {data.threshold}</dd></div>
      </dl>
      {Object.entries(groups).map(([key, label]) => {
        const rows = data.gates.filter(gate => gate.group === key)
        return rows.length ? <section className="readiness-group" key={key}>
          <h3>{label}</h3>
          {rows.map(gate => <details key={gate.id} className="readiness-gate">
            <summary><span>{gate.label}</span><strong data-status={gate.status}>{gate.status}</strong></summary>
            <p>{gate.reason}</p><small>Gate bắt buộc · mở chi tiết để đối soát, không quy N/A thành PASS.</small>
          </details>)}
        </section> : null
      })}
    </> : null}
  </section>
}
