import {
  ArrowClockwise20Regular,
  BookOpen20Regular,
  CheckmarkCircle20Regular,
  ChevronRight20Regular,
  Database20Regular,
  Flash20Regular,
  Info20Regular,
  ShieldCheckmark20Regular,
  Sparkle20Regular,
  Timer20Regular,
  Wrench20Regular,
} from '@fluentui/react-icons'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'
import type { HarnessOverviewData } from '../../harnessScenarios'

export interface LiveTrustCockpitProps {
  onRefresh?: () => void
}

interface CheatsheetTerm {
  id: string
  name: string
  tabLabel: string
  tag: string
  icon: typeof Database20Regular
  metaphor: string
  architectureRole: string
  anatomy: [string, string, string] // [Trigger, Control, Output]
}

const CHEATSHEET_TERMS: CheatsheetTerm[] = [
  {
    id: 'qdrant',
    name: 'Kho tìm kiếm theo ý nghĩa',
    tabLabel: 'Tìm tài liệu',
    tag: 'TẦNG 03 · KHO LƯU TRỮ',
    icon: Database20Regular,
    metaphor: 'Như "Ngăn kéo tài liệu thông minh" tìm kiếm bài theo ý nghĩa ngữ cảnh thay vì từ khóa rời rạc.',
    architectureRole: 'Tài liệu được tìm theo ý nghĩa, lưu trên máy khi chạy tại máy hoặc trong cơ sở dữ liệu khi chạy trực tuyến. Các đoạn liên quan có thể được gửi tới Google để trả lời câu hỏi.',
    anatomy: [
      'Kích hoạt: Khi người dùng đặt câu hỏi cần tìm điều khoản, số liệu trong kho tài liệu.',
      'Kiểm soát: Lọc kết quả theo phạm vi nguồn người dùng và thông tin nguồn đã lưu.',
      'Xuất kết quả: Trả các đoạn có thông tin nguồn vị trí nếu bộ đọc nguồn cung cấp được.',
    ],
  },
  {
    id: 'sqlite_wal',
    name: 'Nhật ký dữ liệu',
    tabLabel: 'Lưu nhật ký',
    tag: 'TẦNG 03 · NHẬT KÝ KIỂM TOÁN',
    icon: ShieldCheckmark20Regular,
    metaphor: 'Như nhật ký ghi lại các lần gọi công cụ để có thể tra cứu và đối soát.',
    architectureRole: 'Lưu thời gian và kết quả thao tác trên máy hoặc trong cơ sở dữ liệu trực tuyến. Nhật ký hỗ trợ đối soát, không phải chứng thư pháp lý.',
    anatomy: [
      'Kích hoạt: Bất kỳ công cụ hay tác tử nào bắt đầu tiếp nhận hoặc xử lý công việc.',
      'Kiểm soát: Gắn thời gian và trạng thái thao tác theo nhật ký thực thi hiện có.',
      'Xuất kết quả: Tra cứu sự kiện thực thi theo quyền tài khoản.',
    ],
  },
  {
    id: 'python_sandbox',
    name: 'Bộ tính toán giới hạn',
    tabLabel: 'Tính toán',
    tag: 'TẦNG 04 · CÔNG CỤ TÍNH TOÁN',
    icon: Wrench20Regular,
    metaphor: 'Như "Phòng thí nghiệm cách ly" để trợ lý tính toán số học mà không chạm vào máy tính bạn.',
    architectureRole: 'Bộ tính toán giới hạn biểu thức cho các phép toán được hỗ trợ; không chạy mã Python tổng quát.',
    anatomy: [
      'Kích hoạt: Khi cần tính toán chênh lệch số dư, tỷ lệ tồn kho hoặc trung bình điểm số.',
      'Kiểm soát: Chỉ chấp nhận các toán tử và đầu vào nằm trong hợp đồng của bộ tính toán.',
      'Xuất kết quả: Trả kết quả phép tính để đối chiếu với đầu vào và công thức.',
    ],
  },
  {
    id: 'dag_orchestrator',
    name: 'Bộ điều phối trợ lý',
    tabLabel: 'Điều phối',
    tag: 'TẦNG 05 · ĐIỀU PHỐI TÁC TỬ',
    icon: Sparkle20Regular,
    metaphor: 'Như "Trợ lý trưởng phân chia việc cho cấp dưới" theo đúng sở trường chuyên môn.',
    architectureRole: 'Bộ điều phối định tuyến và bàn giao giữa các trợ lý chuyên trách theo cấu hình hiện tại.',
    anatomy: [
      'Kích hoạt: Tiếp nhận yêu cầu nghiệp vụ phức tạp đòi hỏi nhiều bước xử lý tuần tự.',
      'Kiểm soát: Có giới hạn số lần gọi và lỗi công cụ; không khẳng định đã đo mọi dạng vòng lặp.',
      'Xuất kết quả: Nhật ký có thể ghi nhận việc chuyển trợ lý và trạng thái của một số bước.',
    ],
  },
  {
    id: 'citation_readback',
    name: 'Kiểm tra nguồn và kết quả',
    tabLabel: 'Nguồn và đọc lại',
    tag: 'TẦNG 06 · KIỂM DUYỆT CHẤT LƯỢNG',
    icon: CheckmarkCircle20Regular,
    metaphor: 'Như "Thẩm định viên đối chiếu lại văn bản gốc trước khi đóng dấu trình sếp".',
    architectureRole: 'Một số luồng kiểm tra cấu trúc đầu ra, liên kết nguồn và đọc lại sau khi ghi; chưa chứng minh ngữ nghĩa mọi nhận định.',
    anatomy: [
      'Kích hoạt: Trước khi xuất câu trả lời hoặc tạo văn bản Google Docs/Sheets.',
      'Kiểm soát: Kết quả phụ thuộc loại tác vụ; thông tin liên kết nguồn không đồng nghĩa nhận định đã được chứng minh.',
      'Xuất kết quả: Hiển thị trạng thái kiểm tra thực tế nếu bước đó đã chạy.',
    ],
  },
  {
    id: 'telemetry_latency',
    name: 'Thời gian xử lý',
    tabLabel: 'Thời gian xử lý',
    tag: 'GIÁM SÁT · HIỆU NĂNG THỰC',
    icon: Timer20Regular,
    metaphor: 'Như đồng hồ bấm giờ: một mốc cho biết một nửa số lượt đã hoàn tất, mốc còn lại cho biết 95% số lượt đã hoàn tất.',
    architectureRole: 'Hai mốc 50% và 95% mô tả thời gian xử lý trên mẫu đã thu thập; chỉ hiển thị khi có mẫu và phạm vi đo rõ.',
    anatomy: [
      'Kích hoạt: Ghi nhận khi một yêu cầu hoặc thao tác bắt đầu.',
      'Kiểm soát: Tách loại độ trễ, cỡ mẫu và khoảng thời gian quan sát.',
      'Xuất kết quả: Hiển thị số liệu đã ghi nhận cùng nguồn và thời điểm tổng hợp.',
    ],
  },
]

const STAGE_LABELS: Record<string, string> = {
  context: 'Nạp ngữ cảnh',
  context_load: 'Nạp ngữ cảnh',
  retrieval: 'Truy xuất nguồn',
  tool: 'Gọi công cụ',
  agent_handoff: 'Chuyển tác tử',
  model: 'Gọi mô hình',
  usage: 'Mức sử dụng',
  output_contract: 'Kiểm tra hợp đồng đầu ra',
  output_guard: 'Kiểm tra đầu ra',
  presentation: 'Định dạng câu trả lời',
  control_resolution: 'Phân loại yêu cầu',
  deterministic_analysis: 'Phân tích xác định',
  agent_task: 'Lần chạy trợ lý',
}

function stageLabel(stage?: string) {
  if (!stage) return 'Sự kiện xử lý'
  return STAGE_LABELS[stage] ?? stage.replaceAll('_', ' ')
}

function eventStatusLabel(status?: string) {
  if (!status) return 'Đã ghi nhận'
  const labels: Record<string, string> = {
    success: 'Thành công ở bước này',
    verified: 'Đã kiểm tra ở bước này',
    passed: 'Bước này đạt',
    failed: 'Bước này lỗi',
    blocked: 'Bị chặn',
    corrected: 'Đã hiệu chỉnh',
    degraded: 'Đã giảm khả năng',
    running: 'Đang chạy',
    error: 'Lần chạy lỗi',
    denied: 'Bị từ chối theo quyền',
    cancelled: 'Đã dừng',
  }
  return labels[status] ?? status
}

function formatRate(rate?: number | null) {
  if (rate == null || !Number.isFinite(rate)) return 'Chưa đo'
  const percent = rate <= 1 ? rate * 100 : rate
  return `${percent.toFixed(1)}%`
}

export function LiveTrustCockpit({ onRefresh }: LiveTrustCockpitProps) {
  const [data, setData] = useState<HarnessOverviewData | null>(null)
  const [telemetryState, setTelemetryState] = useState<'loading' | 'live' | 'unavailable'>('loading')
  const [loading, setLoading] = useState<boolean>(false)
  const [lastFetched, setLastFetched] = useState<string | null>(null)
  const [activeTermId, setActiveTermId] = useState<string>('qdrant')

  const onRefreshRef = useRef(onRefresh)
  useEffect(() => {
    onRefreshRef.current = onRefresh
  }, [onRefresh])

  const fetchTelemetry = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api<HarnessOverviewData>('/api/harness/overview')
      if (result && (result.runtime || result.evaluation || result.recent_runs)) {
        setData(result)
        setTelemetryState('live')
        setLastFetched(result.evaluation?.evaluated_at_utc ?? new Date().toISOString())
      } else {
        setData(null)
        setTelemetryState('unavailable')
        setLastFetched(null)
      }
    } catch {
      setData(null)
      setTelemetryState('unavailable')
      setLastFetched(null)
    } finally {
      setLoading(false)
      onRefreshRef.current?.()
    }
  }, [])

  useEffect(() => {
    void fetchTelemetry()
  }, [fetchTelemetry])

  const evaluation = data?.evaluation
  const p50 = evaluation?.current_runtime?.latency_p50_ms ?? evaluation?.latency_p50_ms ?? null
  const p95 = evaluation?.current_runtime?.latency_p95_ms ?? evaluation?.latency_p95_ms ?? null
  const latencySampleSize = evaluation?.current_runtime?.latency_sample_size ?? 0
  const auditSampleSize = evaluation?.audit_sample_size ?? 0
  const rawToolSuccess = evaluation?.tool_success_rate ?? null
  const toolSuccessRate = rawToolSuccess == null ? null : rawToolSuccess <= 1 ? rawToolSuccess * 100 : rawToolSuccess
  const citationIntegrity = evaluation?.quality_audit?.grounded_citation_rate
  const citationSampleSize = evaluation?.quality_audit?.grounded_responses ?? 0

  // Dynamically bridge live events if available from telemetry
  const checkpoints = useMemo(() => {
    const recentEvents = data?.recent_runs?.[0]?.events
    return recentEvents?.slice(0, 5) ?? []
  }, [data])

  const activeTerm = CHEATSHEET_TERMS.find((t) => t.id === activeTermId) || CHEATSHEET_TERMS[0]!

  return (
    <section className="live-trust-cockpit" aria-labelledby="cockpit-title">
      {/* ================================================================== */}
      {/* 0. INTERACTIVE CHEATSHEET / DICTIONARY SECTION                     */}
      {/* ================================================================== */}
      <div className="cockpit-dictionary-section" aria-label="Từ điển khái niệm kỹ thuật">
        <div className="cockpit-dictionary-header">
          <div className="cockpit-dictionary-title-wrap">
            <span className="cockpit-dictionary-eyebrow">
              <BookOpen20Regular aria-hidden="true" />
              HIỂU CÁCH HỆ THỐNG HOẠT ĐỘNG
            </span>
            <h3 className="cockpit-dictionary-title">
              Hiểu Nhanh Công Nghệ Qua Góc Nhìn Người Trợ Lý
            </h3>
            <p className="cockpit-dictionary-subtitle">
              Những ví dụ gần gũi giúp bạn hiểu cách tìm tài liệu, tính toán và kiểm tra kết quả.
            </p>
          </div>
        </div>

        {/* Concept Pill Selector */}
        <div className="cockpit-dictionary-tabs" role="tablist" aria-label="Chọn thuật ngữ tra cứu">
          {CHEATSHEET_TERMS.map((term) => {
            const isSelected = activeTermId === term.id
            const TermIcon = term.icon
            return (
              <button
                key={term.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`cockpit-dictionary-tab ${isSelected ? 'is-active' : ''}`}
                onClick={() => setActiveTermId(term.id)}
              >
                <TermIcon aria-hidden="true" className="cockpit-dictionary-tab__icon" />
                <span>{term.tabLabel}</span>
              </button>
            )
          })}
        </div>

        {/* Selected Term Detail Card */}
        <div className="cockpit-dictionary-card">
          <div className="cockpit-dictionary-card__header">
            <div>
              <span className="cockpit-dictionary-card__tag">{activeTerm.tag}</span>
              <h4 className="cockpit-dictionary-card__name">{activeTerm.name}</h4>
            </div>
            <span className="cockpit-dictionary-card__concept-badge">
              <Sparkle20Regular aria-hidden="true" />
              Cách hoạt động
            </span>
          </div>

          <div className="cockpit-dictionary-card__grid">
            <div className="cockpit-dictionary-pane cockpit-dictionary-pane--metaphor">
              <span className="pane-label">Cách hiểu đơn giản</span>
              <p className="pane-text"><strong>{activeTerm.metaphor}</strong></p>
              <div className="pane-role">
                <span className="pane-role-label">Vai trò trong Veridra:</span>
                <p>{activeTerm.architectureRole}</p>
              </div>
            </div>

            <div className="cockpit-dictionary-pane cockpit-dictionary-pane--anatomy">
              <span className="pane-label">Quy trình ba bước</span>
              <ul className="cockpit-anatomy-steps">
                {activeTerm.anatomy.map((stepText, sIdx) => {
                  const [stepPrefix, stepBody] = stepText.split(': ')
                  return (
                    <li key={sIdx} className="cockpit-anatomy-step">
                      <span className="step-badge">Bước 0{sIdx + 1}</span>
                      <div className="step-content">
                        <strong>{stepPrefix}:</strong>
                        <span>{stepBody || ''}</span>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* 1. HUD TOP BAR & CORE TELEMETRY METRICS                            */}
      {/* ================================================================== */}
      <header className="cockpit-header">
        <div className="cockpit-header__main">
          <span className="cockpit-header__eyebrow">
            <Sparkle20Regular aria-hidden="true" />
            THEO DÕI THỰC THI
          </span>
          <h2 id="cockpit-title" className="cockpit-header__title">
            Theo dõi từng lần xử lý
          </h2>
          <p className="cockpit-header__subtitle">
            Số liệu lấy từ nhật ký của tài khoản. Độ đúng của nội dung cần được đối chiếu riêng với nguồn.
          </p>
        </div>

        <div className="cockpit-header__status-panel">
          <div className="cockpit-header__status-badge">
            <span
              className={`cockpit-pulse-dot ${telemetryState === 'live' ? 'is-live' : telemetryState === 'loading' ? 'is-loading' : 'is-unavailable'}`}
              aria-hidden="true"
            />
            <span>
              {telemetryState === 'live'
                ? `Dữ liệu tài khoản · n=${auditSampleSize}`
                : telemetryState === 'loading'
                  ? 'Đang tải số liệu…'
                  : 'Chưa lấy được nhật ký'}
            </span>
          </div>
          <button
            type="button"
            className="cockpit-reload-btn"
            onClick={fetchTelemetry}
            disabled={loading}
            title="Làm mới số liệu"
          >
            <ArrowClockwise20Regular className={loading ? 'is-spinning' : ''} aria-hidden="true" />
            <span>{loading ? 'Đang cập nhật…' : 'Cập nhật số liệu'}</span>
          </button>
        </div>
      </header>

      {telemetryState === 'unavailable' ? (
        <div className="cockpit-telemetry-state" role="status">
          Chưa lấy được số liệu. Hệ thống không hiển thị điểm đánh giá khi chưa có dữ liệu thật.
        </div>
      ) : null}

      {/* 4 HUD Core Metric Cards */}
      <div className="cockpit-hud-grid">
        {/* Metric 1: Grounded Citations */}
        {citationSampleSize > 0 && citationIntegrity != null ? <div className="cockpit-hud-card cockpit-hud-card--grounded">
          <div className="cockpit-hud-card__top">
            <span className="cockpit-hud-card__label">THÔNG TIN NGUỒN</span>
            <ShieldCheckmark20Regular className="cockpit-hud-card__icon" aria-hidden="true" />
          </div>
          <div className="cockpit-hud-card__value">{formatRate(citationIntegrity)}</div>
          <div className="cockpit-hud-card__subtext">
            Tỷ lệ liên kết nguồn đủ thông tin trong {citationSampleSize} câu có nguồn; chưa đo mức độ nguồn chứng minh nội dung nhận định.
          </div>
          <div className="cockpit-hud-card__badge">
            <Info20Regular aria-hidden="true" />
            <span>Kiểm tra cấu trúc, không phải kiểm chứng sự thật</span>
          </div>
        </div> : null}

        {/* Metric 2: Hallucination Tolerance */}

        {/* Metric 3: Latency Profile */}
        {latencySampleSize > 0 && p50 != null && p95 != null ? <div className="cockpit-hud-card cockpit-hud-card--latency">
          <div className="cockpit-hud-card__top">
            <span className="cockpit-hud-card__label">THỜI GIAN XỬ LÝ</span>
            <Timer20Regular className="cockpit-hud-card__icon" aria-hidden="true" />
          </div>
          <div className="cockpit-hud-card__value">
            {p50 == null ? '—' : `${p50}ms`} <span className="cockpit-hud-card__unit">/ {p95 == null ? '—' : `${p95}ms`}</span>
          </div>
          <div className="cockpit-hud-card__subtext">
            Độ trễ thao tác công cụ theo nhật ký thực thi đã tải; không phải thời gian phản hồi toàn bộ chat.
          </div>
          <div className="cockpit-hud-card__badge">
            <Flash20Regular aria-hidden="true" />
            <span>n={latencySampleSize} lượt gọi công cụ</span>
          </div>
        </div> : null}

        {/* Metric 4: Local-First Isolation */}
      </div>

      {/* ================================================================== */}
      {/* 2. OBSERVED EVENTS FOR THE MOST RECENT USER-SCOPED RUN              */}
      {/* ================================================================== */}
      <div className="cockpit-checkpoints-section">
        <div className="cockpit-checkpoints-header">
          <div>
            <h3 className="cockpit-checkpoints-title">
              Sự kiện ghi nhận ở lần chạy gần nhất
            </h3>
            <p className="cockpit-checkpoints-subtitle">
              Đây là nhật ký xử lý của một lần chạy; trạng thái thành công ở một bước không chứng minh câu trả lời đúng.
            </p>
          </div>
          <span className="cockpit-checkpoints-metric">
            Công cụ chạy thành công: <strong>{formatRate(toolSuccessRate)}</strong> · n={auditSampleSize}
          </span>
        </div>
        {data?.recent_runs?.[0]?.run_id ? (
          <p className="cockpit-checkpoints-subtitle" aria-label="Mã liên kết lần chạy">
            Mã lần chạy để đối chiếu với Nhật ký: <code>{data.recent_runs[0].run_id}</code>
          </p>
        ) : null}

        <div className="cockpit-checkpoints-list" role="list">
          {checkpoints.map((event, idx) => (
            <div key={`${event.stage ?? 'event'}-${idx}`} className="cockpit-checkpoint-item" role="listitem">
              <div className="cockpit-checkpoint-item__num-col">
                <span className="cockpit-checkpoint-item__num">{String(idx + 1).padStart(2, '0')}</span>
              </div>

              <div className="cockpit-checkpoint-item__main">
                <div className="cockpit-checkpoint-item__title-row">
                  <strong className="cockpit-checkpoint-item__name">{stageLabel(event.stage)}</strong>
                  {event.tool ? <span className="cockpit-checkpoint-item__tool">{event.tool}</span> : null}
                </div>
                <div className="cockpit-checkpoint-item__assistant-role">
                  <Info20Regular aria-hidden="true" />
                  <span>{eventStatusLabel(event.status)}</span>
                </div>
              </div>

              <div className="cockpit-checkpoint-item__meta">
                {typeof event.latency_ms === 'number' ? (
                  <span className="cockpit-checkpoint-item__latency">
                    <Timer20Regular aria-hidden="true" />
                    {event.latency_ms}ms
                  </span>
                ) : null}
              </div>
            </div>
          ))}
          {checkpoints.length === 0 ? (
            <div className="cockpit-telemetry-state" role="status">
              {telemetryState === 'live'
                ? 'Chưa có nhật ký của lần chạy gần nhất để hiển thị.'
                : 'Nhật ký xuất hiện sau khi bạn thực hiện yêu cầu.'}
            </div>
          ) : null}
        </div>

        <div className="cockpit-footer-note">
          <ChevronRight20Regular aria-hidden="true" />
          <span>
            {lastFetched
              ? `Hệ thống tổng hợp số liệu lúc ${new Date(lastFetched).toLocaleString('vi-VN')}. Dữ liệu hiện tại chỉ phản ánh mẫu nhật ký của tài khoản này.`
              : 'Chưa ghi nhận thời điểm tổng hợp số liệu.'}
          </span>
        </div>
      </div>
    </section>
  )
}
