import { Button, Spinner } from '@fluentui/react-components'
import { ArrowClockwise20Regular, CheckmarkCircle20Regular, Warning20Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState } from '../components/AsyncState'

interface ToolSummary {
  name: string
  description: string
  available: boolean
  requires_approval: boolean
  permissions: string[]
  oauth_scopes: string[]
  max_attempts: number
  timeout_seconds: number | null
}

interface HarnessOverview {
  runtime: {
    orchestrator: string
    orchestrator_class: string
    primary_model: string
    fallback_model: string
    embedding_model: string
    embedding_dimensions: number
  }
  context: { sessions: number; active_memories: number }
  rag: { indexed_files: number; indexed_chunks: number }
  tools: { total: number; available: number; approval_required: number; items: ToolSummary[] }
  creation: {google_outputs: string[]; visuals: number; skills: number; approval_flow: string; local_visual_formats: string[]}
  orchestration: { stages: string[]; checkpoint: string }
  protocols: {
    mcp: { enabled: boolean; mode: string; tools: string[] }
    a2a: { enabled: boolean; mode: string; tools: string[] }
    multi_agent_runtime: boolean
  }
  evaluation: {
    routing_regression: {
      suite: string
      version: string
      scope: string
      passed: number
      total: number
      pass_rate: number | null
    }
    audit_sample_size: number
    tool_success_rate: number | null
    latency_p50_ms: number | null
    latency_p95_ms: number | null
    feedback_count: number
    helpful_rate: number | null
    usage: { prompt_tokens: number; output_tokens: number; total_tokens: number; measured_runs: number }
    quality_note: string
    quality_audit: {responses: number; nonempty_rate: number | null; trace_integrity_rate: number | null; grounded_citation_rate: number | null}
  }
}

function Metric({ value, label, detail }: { value: string; label: string; detail: string }) {
  return <div className="harness-metric"><strong>{value}</strong><span>{label}</span><small>{detail}</small></div>
}

export function HarnessPage() {
  const [data, setData] = useState<HarnessOverview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true); setError('')
    try { setData(await api<HarnessOverview>('/api/harness/overview')) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Không tải được Harness.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  if (loading && !data) return <div className="harness-loading"><Spinner label="Đang đọc dữ liệu Harness thật" /></div>
  if (error && !data) return <ErrorState message={error} retry={load} />
  if (!data) return null

  const success = data.evaluation.tool_success_rate
  const helpful = data.evaluation.helpful_rate
  return (
    <section className="harness-page">
      <header className="harness-intro">
        <div>
          <p className="home-kicker">Agent Learning Lab</p>
          <h2>Nhìn thấy cách Agent làm việc.</h2>
          <p>Mỗi con số bên dưới được lấy từ tài khoản và runtime hiện tại.</p>
        </div>
        <Button icon={<ArrowClockwise20Regular />} onClick={() => void load()}>Làm mới</Button>
      </header>

      <section className="harness-band" id="context-harness">
        <div className="harness-band__heading"><span>01</span><div><h3>Context Harness</h3><p>Những gì Agent giữ lại để hiểu đúng phiên làm việc của bạn.</p></div></div>
        <div className="harness-metrics">
          <Metric value={String(data.context.sessions)} label="Cuộc trò chuyện" detail="Tách theo tài khoản" />
          <Metric value={String(data.context.active_memories)} label="Bộ nhớ đang dùng" detail="Có thể xem và lưu trữ" />
          <Metric value={data.orchestration.checkpoint} label="Checkpoint" detail="Khôi phục luồng Agent" />
        </div>
      </section>

      <section className="harness-band" id="rag-harness">
        <div className="harness-band__heading"><span>02</span><div><h3>RAG Harness</h3><p>Từ tài liệu gốc đến đoạn bằng chứng và citation trong câu trả lời.</p></div></div>
        <div className="harness-metrics">
          <Metric value={String(data.rag.indexed_files)} label="Tệp đã lập chỉ mục" detail="Kiểm tra quyền và revision" />
          <Metric value={String(data.rag.indexed_chunks)} label="Đoạn có thể truy xuất" detail="Dense + lexical + RRF" />
          <Metric value={`${data.runtime.embedding_dimensions}D`} label={data.runtime.embedding_model} detail="Embedding hiện tại" />
        </div>
      </section>

      <section className="harness-band" id="tool-harness">
        <div className="harness-band__heading"><span>03</span><div><h3>Tool Harness</h3><p>Schema, quyền, OAuth, giới hạn, retry và audit trước khi tool chạy.</p></div></div>
        <div className="harness-metrics">
          <Metric value={`${data.tools.available}/${data.tools.total}`} label="Tool có thể dùng" detail="Theo role hiện tại" />
          <Metric value={String(data.tools.approval_required)} label="Tool cần xác nhận" detail="Không tự ghi ra ngoài" />
          <Metric value={String(data.evaluation.audit_sample_size)} label="Tool run được đo" detail="Tối đa 100 lần gần nhất" />
        </div>
        <details className="tool-catalog"><summary>Xem catalog và chính sách từng tool</summary>
          <div className="tool-catalog__list">{data.tools.items.map(tool => <div key={tool.name} className="tool-row">
            <div>{tool.available ? <CheckmarkCircle20Regular /> : <Warning20Regular />}<strong>{tool.name}</strong></div>
            <p>{tool.description}</p><small>{tool.permissions.join(', ')} · {tool.requires_approval ? 'cần duyệt' : `tối đa ${tool.max_attempts} lần`}</small>
          </div>)}</div>
        </details>
      </section>

      <section className="harness-band" id="orchestration-harness">
        <div className="harness-band__heading"><span>04</span><div><h3>Orchestration Harness</h3><p>Lập kế hoạch, điều hướng, chạy tool, tổng hợp và phục hồi.</p></div></div>
        <div className="orchestration-flow" aria-label="Luồng orchestration">
          {data.orchestration.stages.map((stage, index) => <div key={stage}><span>{index + 1}</span><strong>{stage}</strong></div>)}
        </div>
        <p className="harness-fact">Runtime: <strong>{data.runtime.orchestrator_class}</strong> · model {data.runtime.primary_model} · fallback {data.runtime.fallback_model}</p>
      </section>

      <section className="harness-band" id="creation-harness">
        <div className="harness-band__heading"><span>05</span><div><h3>Creation & Execution Harness</h3><p>Từ một spec đã kiểm tra đến đầu ra thật, có quyền, xác nhận và read-back.</p></div></div>
        <div className="harness-metrics">
          <Metric value={data.creation.google_outputs.join(' · ')} label="Google Workspace" detail="Tạo/sửa theo batch" />
          <Metric value={String(data.creation.visuals)} label="Visual local" detail={data.creation.local_visual_formats.join(' + ')} />
          <Metric value={String(data.creation.skills)} label="Reusable Skills" detail="Procedure có version" />
        </div>
        <p className="harness-fact">Luồng ghi: <strong>{data.creation.approval_flow}</strong></p>
      </section>

      <section className="harness-band" id="protocol-harness">
        <div className="harness-band__heading"><span>06</span><div><h3>Multi-Agent, MCP & A2A</h3><p>Ranh giới kết nối hiện có và mức triển khai thật của hệ thống.</p></div></div>
        <div className="protocol-ledger">
          <div><strong>MCP</strong><span>{data.protocols.mcp.mode}</span><small>{data.protocols.mcp.tools.length} tool đọc</small></div>
          <div><strong>A2A</strong><span>{data.protocols.a2a.mode}</span><small>{data.protocols.a2a.tools.length} tool đọc</small></div>
          <div><strong>Multi-Agent runtime</strong><span>{data.protocols.multi_agent_runtime ? 'Đang chạy' : 'Chưa bật'}</span><small>Hiển thị trung thực theo runtime</small></div>
        </div>
      </section>

      <section className="harness-band" id="evaluation-harness">
        <div className="harness-band__heading"><span>07</span><div><h3>Evaluation Harness</h3><p>Đo khả năng hoàn thành, tốc độ và đánh giá trực tiếp từ người dùng.</p></div></div>
        <div className="harness-metrics">
          <Metric value={`${data.evaluation.routing_regression.passed}/${data.evaluation.routing_regression.total}`} label="Routing regression" detail={`Bộ dữ liệu ${data.evaluation.routing_regression.version}`} />
          <Metric value={success === null ? 'Chưa đủ dữ liệu' : `${Math.round(success * 100)}%`} label="Tool success" detail={`${data.evaluation.audit_sample_size} run gần nhất`} />
          <Metric value={data.evaluation.latency_p95_ms === null ? '—' : `${data.evaluation.latency_p95_ms} ms`} label="P95 latency" detail="Tool run đã hoàn tất" />
          <Metric value={helpful === null ? 'Chưa có' : `${Math.round(helpful * 100)}%`} label="Câu trả lời hữu ích" detail={`${data.evaluation.feedback_count} lượt đánh giá`} />
          <Metric value={data.evaluation.quality_audit.grounded_citation_rate === null ? 'Chưa có nguồn' : `${Math.round(data.evaluation.quality_audit.grounded_citation_rate * 100)}%`} label="Citation integrity" detail={`${data.evaluation.quality_audit.responses} response được audit`} />
        </div>
        <div className="evaluation-scope">
          <strong>Đã đo</strong><span>Điều hướng deterministic, tool success, latency và phản hồi của bạn.</span>
          <strong>Chưa kết luận</strong><span>Độ đúng đáp án, faithfulness và task success live cần golden dataset theo tài liệu thật.</span>
        </div>
        <p className="harness-fact">{data.evaluation.quality_note}</p>
      </section>
    </section>
  )
}
