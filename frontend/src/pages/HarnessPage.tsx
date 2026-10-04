import { Button } from '@fluentui/react-components'
import {
  BuildingBank20Regular,
  CheckmarkCircle20Regular,
  ChevronRight20Regular,
  DocumentText20Regular,
  Flowchart20Regular,
  HatGraduation20Regular,
  LockClosed20Regular,
  Open20Regular,
  ShoppingBag20Regular,
  Sparkle20Regular,
  Table20Regular,
} from '@fluentui/react-icons'
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import {
  HarnessDiagram6,
  type DiagramViewMode,
} from '../components/harness/HarnessDiagram6'
import { TerminalCommandHub } from '../components/harness/TerminalCommandHub'
import {
  Step07MockupPreview,
  StepMicroCards,
} from '../components/harness/StepArtifactMockup'
import { TechInspectorDrawer } from '../components/harness/TechInspectorDrawer'
import { LiveTrustCockpit } from '../components/harness/LiveTrustCockpit'
import { InteractiveTestDrive } from '../components/harness/InteractiveTestDrive'
import { GovernanceMatrixTable } from '../components/harness/GovernanceMatrixTable'
import {
  HARNESS_SCENARIOS,
  HARNESS_SHARED_RAILS,
  type HarnessScenario,
  type HarnessScenarioId,
  type HarnessStep,
} from '../harnessScenarios'
import './harnessPage.css'
import '../components/harness/harnessComponents.css'

const DOMAIN_ENTERPRISE_META: Record<HarnessScenarioId, {
  tag: string
  copy: string
}> = {
  banking: {
    tag: 'NGÂN HÀNG',
    copy: 'Đối soát chênh lệch sổ sách & Giữ trọn vết kiểm toán',
  },
  education: {
    tag: 'GIÁO DỤC',
    copy: 'Nhận diện lỗ hổng kiến thức & Đánh giá khách quan theo tiêu chí đã định',
  },
  ecommerce: {
    tag: 'THƯƠNG MẠI',
    copy: 'Phân tích biến động đơn hàng & Đề xuất phương án vận hành kho',
  },
}

function outputIcon(label: string) {
  if (label.toLowerCase().includes('sheet') || label.toLowerCase().includes('bảng')) return <Table20Regular />
  if (label.toLowerCase().includes('gmail') || label.toLowerCase().includes('email')) return <Open20Regular />
  if (label.toLowerCase().includes('skill')) return <Sparkle20Regular />
  return <DocumentText20Regular />
}

function getDomainIcon(id: HarnessScenarioId) {
  switch (id) {
    case 'banking':
      return <BuildingBank20Regular aria-hidden="true" />
    case 'education':
      return <HatGraduation20Regular aria-hidden="true" />
    case 'ecommerce':
      return <ShoppingBag20Regular aria-hidden="true" />
  }
}

/**
 * Parses query parameters from hash, e.g. `#/harness?domain=education&step=3`.
 */
function parseHarnessUrl(): { domain?: HarnessScenarioId; stepIndex?: number } {
  try {
    const hash = window.location.hash || ''
    const qIndex = hash.indexOf('?')
    if (qIndex === -1) return {}
    const params = new URLSearchParams(hash.slice(qIndex + 1))
    const domainParam = params.get('domain')?.toLowerCase()
    const stepParam = params.get('step')

    const domain: HarnessScenarioId | undefined =
      domainParam === 'banking' || domainParam === 'education' || domainParam === 'ecommerce'
        ? (domainParam as HarnessScenarioId)
        : undefined

    let stepIndex: number | undefined
    if (stepParam !== null) {
      const parsed = parseInt(stepParam, 10)
      if (!Number.isNaN(parsed)) {
        stepIndex = Math.max(0, Math.min(6, parsed - 1))
      }
    }
    return { domain, stepIndex }
  } catch {
    return {}
  }
}

const STEP_PHASE_LABELS: Record<string, string> = {
  '01': 'GĐ 1 · Tiếp nhận',
  '02': 'GĐ 1 · Thu thập',
  '03': 'GĐ 2 · Tra cứu',
  '04': 'GĐ 3 · Tính toán',
  '05': 'GĐ 3 · Phối hợp',
  '06': 'GĐ 4 · Kiểm duyệt',
  '07': 'GĐ 4 · Bàn giao',
}

function HarnessFlow({
  scenario,
  activeStep,
  onSelect,
}: {
  scenario: HarnessScenario
  activeStep: number
  onSelect: (index: number) => void
}) {
  const stepRefs = useRef<(HTMLButtonElement | null)[]>([])
  const progress = `${(activeStep / Math.max(1, scenario.steps.length - 1)) * 100}%`
  const activePhase = STEP_PHASE_LABELS[scenario.steps[activeStep]?.number ?? '01'] ?? 'Đang thực thi'

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex = index
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      nextIndex = (index + 1) % scenario.steps.length
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      nextIndex = (index - 1 + scenario.steps.length) % scenario.steps.length
    } else if (e.key === 'Home') {
      e.preventDefault()
      nextIndex = 0
    } else if (e.key === 'End') {
      e.preventDefault()
      nextIndex = scenario.steps.length - 1
    }
    if (nextIndex !== index) {
      onSelect(nextIndex)
      stepRefs.current[nextIndex]?.focus()
    }
  }

  return (
    <div className="harness-flow" aria-label={`Luồng xử lý ${scenario.domain}`}>
      <div className="harness-flow__track-meta" aria-hidden="true">
        <span className="harness-flow__track-label">Tiến trình thực thi 7 bước</span>
        <span className="harness-flow__track-count">
          Bước {activeStep + 1} / {scenario.steps.length} · {activePhase}
        </span>
      </div>
      <div className="harness-flow__rail" aria-hidden="true">
        <span style={{ width: progress, ['--flow-progress' as string]: progress }} />
      </div>
      <div className="harness-flow__steps" role="tablist" aria-label="Các bước xử lý">
        {scenario.steps.map((step, index) => {
          const isActive = activeStep === index
          const isPast = index < activeStep
          const phaseLabel = STEP_PHASE_LABELS[step.number] ?? `Bước ${step.number}`

          return (
            <button
              key={step.id}
              ref={(el) => {
                stepRefs.current[index] = el
              }}
              type="button"
              role="tab"
              id={`harness-step-tab-${scenario.id}-${step.id}`}
              aria-selected={isActive}
              aria-controls={`harness-step-panel-${scenario.id}`}
              tabIndex={isActive ? 0 : -1}
              className={`harness-flow__step ${isActive ? 'is-active' : ''} ${
                isPast ? 'is-past' : ''
              }`}
              onClick={() => onSelect(index)}
              onKeyDown={(e) => handleKeyDown(e, index)}
            >
              <div className="harness-flow__step-top">
                <div className="harness-flow__step-header-row">
                  <span className="harness-flow__number">{step.number}</span>
                  {isActive && (
                    <span className="harness-flow__status-badge is-active">
                      <span className="harness-flow__pulse-dot" aria-hidden="true" />
                      <span>Đang xem</span>
                    </span>
                  )}
                  {isPast && (
                    <span className="harness-flow__status-badge is-past">
                      <CheckmarkCircle20Regular className="harness-flow__status-icon" aria-hidden="true" />
                      <span>Đã qua</span>
                    </span>
                  )}
                  {!isActive && !isPast && (
                    <span className="harness-flow__status-badge is-upcoming">
                      <span>0{index + 1}/07</span>
                    </span>
                  )}
                </div>
                <span className="harness-flow__phase-badge" title={phaseLabel}>
                  {phaseLabel}
                </span>
              </div>
              <span className="harness-flow__step-copy">
                <strong>{step.plainTitle}</strong>
                <small title={step.plainSummary}>{step.plainSummary}</small>
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function HarnessStepPanel({
  scenario,
  step,
  stepIndex,
}: {
  scenario: HarnessScenario
  step: HarnessStep
  stepIndex: number
}) {
  const isOutcomeStep = step.number === '07' || stepIndex === 6

  return (
    <article
      className="harness-step-panel"
      id={`harness-step-panel-${scenario.id}`}
      role="tabpanel"
      aria-live="polite"
    >
      {/* Top Banner: Symmetrical Header with Milestone Info & Assistant Role */}
      <div className="harness-step-panel__header-row">
        <div className="harness-step-panel__meta">
          <span className="harness-step-panel__eyebrow">
            BƯỚC {step.number} / 07 · {STEP_PHASE_LABELS[step.number] ?? 'TIẾN TRÌNH THỰC THI'}
          </span>
          <h3 className="harness-step-panel__title">{step.plainTitle}</h3>
        </div>
        <div className="harness-step-panel__assistant-tag">
          <Sparkle20Regular aria-hidden="true" />
          <span>Trợ lý số thực thi chuẩn mực</span>
        </div>
      </div>

      {/* Symmetrical 3-Card Fact Grid spanning 100% width (Balanced, Zero Dead Space) */}
      <div className="harness-step-panel__facts-grid">
        <div className="harness-step-fact-card">
          <div className="harness-step-fact-card__header">
            <span className="fact-card-icon">🎯</span>
            <strong>Mục tiêu xử lý của trợ lý</strong>
          </div>
          <p className="harness-step-fact-card__body">{step.plainSummary}</p>
        </div>

        <div className="harness-step-fact-card">
          <div className="harness-step-fact-card__header">
            <span className="fact-card-icon">📁</span>
            <strong>Bằng chứng &amp; Hồ sơ đối chiếu</strong>
          </div>
          <p className="harness-step-fact-card__body">{step.evidence}</p>
        </div>

        <div className="harness-step-fact-card">
          <div className="harness-step-fact-card__header">
            <span className="fact-card-icon">⚙️</span>
            <strong>Hệ thống điều phối ngầm</strong>
          </div>
          <p className="harness-step-fact-card__body">
            <strong>{step.technicalTitle}:</strong> {step.technicalSummary}
          </p>
        </div>
      </div>

      {/* Full-width Detail Body (Zero empty space) */}
      <div className="harness-step-panel__detail-body">
        {isOutcomeStep ? (
          <Step07MockupPreview scenarioId={scenario.id} />
        ) : (
          <StepMicroCards scenarioId={scenario.id} stepIndex={stepIndex} />
        )}
      </div>
    </article>
  )
}

export function HarnessPage() {
  const initialParams = parseHarnessUrl()
  const [selectedId, setSelectedId] = useState<HarnessScenarioId>(initialParams.domain ?? 'banking')
  const [activeStep, setActiveStep] = useState(initialParams.stepIndex ?? 0)
  const [diagramViewMode, setDiagramViewMode] = useState<DiagramViewMode>('business')
  const [isTechDrawerOpen, setIsTechDrawerOpen] = useState(false)
  const [selectedTechId, setSelectedTechId] = useState<string | null>(null)
  const isInternalUpdate = useRef(false)

  const scenario = useMemo(
    () => HARNESS_SCENARIOS.find((item) => item.id === selectedId) ?? HARNESS_SCENARIOS[0]!,
    [selectedId],
  )
  const step = scenario.steps[activeStep] ?? scenario.steps[0]!

  function openTechInspector(techIdOrName: string | null) {
    setSelectedTechId(techIdOrName)
    setIsTechDrawerOpen(true)
  }

  // Bidirectional URL deep-linking: update hash query params
  useEffect(() => {
    const currentHash = window.location.hash || ''
    if (!currentHash || currentHash.startsWith('#/harness') || currentHash.startsWith('#harness')) {
      const targetHash = `#/harness?domain=${selectedId}&step=${activeStep + 1}`
      if (currentHash !== targetHash) {
        isInternalUpdate.current = true
        window.history.replaceState(null, '', targetHash)
      }
    }
  }, [selectedId, activeStep])

  // Bidirectional URL deep-linking: listen for hashchange and popstate
  useEffect(() => {
    const handleLocationChange = () => {
      if (isInternalUpdate.current) {
        isInternalUpdate.current = false
        return
      }
      const currentHash = window.location.hash || ''
      if (!currentHash.startsWith('#/harness') && !currentHash.startsWith('#harness')) {
        return
      }
      const { domain, stepIndex } = parseHarnessUrl()
      if (domain && domain !== selectedId) {
        setSelectedId(domain)
      }
      if (stepIndex !== undefined && stepIndex !== activeStep) {
        setActiveStep(stepIndex)
      }
    }

    window.addEventListener('hashchange', handleLocationChange)
    window.addEventListener('popstate', handleLocationChange)
    return () => {
      window.removeEventListener('hashchange', handleLocationChange)
      window.removeEventListener('popstate', handleLocationChange)
    }
  }, [selectedId, activeStep])

  function selectScenario(id: HarnessScenarioId) {
    setSelectedId(id)
    setActiveStep(0)
  }

  return (
    <section className="stack-page harness-flagship" data-domain={selectedId}>
      {/* Enterprise Editorial Header without badge or noisy eyebrows */}
      <header className="harness-flagship__header">
        <div className="harness-flagship__header-content">
          <h1 className="harness-flagship__title">
            Kiến trúc Veridra: từ yêu cầu đến kết quả có thể kiểm tra
          </h1>
          <p className="harness-flagship__subtitle">
            Minh bạch hóa mọi quyết định, luồng dữ liệu và rào cản an toàn trước khi bất kỳ tác vụ nào được ghi nhận.
          </p>
        </div>
      </header>

      <section className="harness-story" aria-labelledby="harness-story-title">
        <div className="harness-story__copy">
          <span className="harness-story__label">Bối cảnh sử dụng</span>
          <h2 id="harness-story-title">Một yêu cầu ngắn thường che giấu cả một chuỗi rủi ro.</h2>
          <p>
            Người dùng bắt đầu bằng một email, tài liệu hoặc câu hỏi. Phần khó không phải tạo thêm văn bản,
            mà là tìm đúng nguồn, phối hợp đúng công cụ, xin duyệt đúng lúc và để lại bằng chứng đủ rõ để kiểm tra lại.
          </p>
          <ol className="harness-story__sequence">
            <li><strong>Nỗi đau:</strong><span>Dữ liệu nằm rải rác; kết quả nhanh nhưng khó biết nhận định nào dựa trên nguồn nào.</span></li>
            <li><strong>Lý do có Veridra:</strong><span>Nối nguồn, trợ lý, công cụ và bước duyệt thành một hành trình có phạm vi.</span></li>
            <li><strong>Cách giải quyết:</strong><span>Đọc và phân tích trước; mọi thao tác ghi được hỗ trợ đều qua xem trước, duyệt và đọc lại.</span></li>
            <li><strong>Khác biệt cần kiểm chứng:</strong><span>Nhật ký, nguồn trích dẫn và số liệu cho biết điều đã được kiểm tra.</span></li>
          </ol>
        </div>
        <figure className="harness-story__figure">
          <img
            className="harness-story__image"
            src="/harness/veridra-verified-workflow.png"
            alt="Hành trình Veridra: dữ liệu rải rác → nối nguồn và công cụ → đọc, xem trước, duyệt, thực thi, đọc lại → kết quả có nguồn và nhật ký"
            width={1672}
            height={941}
            loading="lazy"
          />
          <figcaption>Minh họa hành trình xử lý của Veridra. Các số 12 nguồn, 5 hành động, 100%, +24% và −18% trong ảnh là ví dụ minh họa, không phải số đo hoặc cam kết của sản phẩm.</figcaption>
        </figure>
      </section>

      <div className="harness-telemetry-disclosure" role="note">
        Các tình huống và bản xem trước bên dưới là minh họa luồng nghiệp vụ. Số liệu trong ví dụ không phải kết quả kiểm thử hoặc điểm đánh giá thực tế của hệ thống.
      </div>

      <section className="harness-casebook" aria-label="Ba ví dụ nghiệp vụ">
        {/* Left Rail Switcher with Dedicated Vector Icons and Enterprise Domain Copy */}
        <nav className="harness-casebook__rail" aria-label="Chọn lĩnh vực nghiệp vụ">
          <div className="harness-casebook__rail-heading">
            <span>TÌNH HUỐNG DOANH NGHIỆP</span>
            <p>Ba mô hình điều phối tác tử với rào cản an toàn riêng biệt.</p>
          </div>
          <div className="harness-casebook__rail-grid">
            {HARNESS_SCENARIOS.map((item) => {
              const meta = DOMAIN_ENTERPRISE_META[item.id]
              const isSelected = selectedId === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={isSelected}
                  className={`harness-case harness-case--${item.id} ${isSelected ? 'is-active' : ''}`}
                  onClick={() => selectScenario(item.id)}
                >
                  <span className="harness-case__icon-badge">
                    {getDomainIcon(item.id)}
                  </span>
                  <span className="harness-case__copy">
                    <strong className="harness-case__domain-tag">{meta?.tag ?? item.domain}</strong>
                    <span className="harness-case__domain-desc">{meta?.copy ?? item.title}</span>
                  </span>
                  <ChevronRight20Regular className="harness-case__chevron" aria-hidden="true" />
                </button>
              )
            })}
          </div>
        </nav>

        <article className="harness-casebook__main">
          <header className="harness-scenario-header">
            <div>
              <span className="harness-scenario-header__domain">{scenario.domain}</span>
              <h2>{scenario.title}</h2>
              <p>{scenario.subtitle}</p>
            </div>
          </header>

          {/* Interactive Terminal Command Hub */}
          <TerminalCommandHub
            domainId={scenario.id}
            suggestedCommand={scenario.suggestedCommand}
            request={scenario.request}
            title={scenario.title}
          />

          <div className="harness-scenario-brief">
            <div>
              <span>Vấn đề</span>
              <p>{scenario.pain}</p>
            </div>
            <div>
              <span>Yêu cầu mẫu</span>
              <p>“{scenario.request}”</p>
            </div>
            <div>
              <span>Kết quả cuối</span>
              <p>{scenario.result}</p>
            </div>
          </div>

          {/* Canonical 6-Harness Architecture Diagram */}
          <HarnessDiagram6
            domainId={scenario.id}
            activeViewMode={diagramViewMode}
            onViewModeChange={setDiagramViewMode}
            onSelectTier={(tierIdx) => {
              if (tierIdx >= 1 && tierIdx <= 7) {
                setActiveStep(tierIdx - 1)
              }
            }}
            onSelectStep={setActiveStep}
          />

          <div className="harness-flow-heading">
            <div>
              <span className="harness-flow-heading__eyebrow">ĐƯỜNG ĐI CÓ THỂ KIỂM TRA</span>
              <h3>Nhấn vào từng bước để xem việc thật đã xảy ra.</h3>
            </div>
            <span className="harness-flow-heading__hint">
              <Flowchart20Regular /> Không hiển thị suy nghĩ riêng của mô hình
            </span>
          </div>

          <HarnessFlow scenario={scenario} activeStep={activeStep} onSelect={setActiveStep} />
          <HarnessStepPanel scenario={scenario} step={step} stepIndex={activeStep} />

          <div className="harness-scenario-columns">
            <section className="harness-scenario-block">
              <div className="harness-block-heading">
                <span>ĐẦU VÀO</span>
                <strong>Dữ liệu được dùng</strong>
              </div>
              <ul>
                {scenario.inputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="harness-scenario-block harness-scenario-block--output">
              <div className="harness-block-heading">
                <span>ĐẦU RA</span>
                <strong>Kết quả người dùng nhận</strong>
              </div>
              <ul className="harness-output-list">
                {scenario.outputs.map((item) => (
                  <li key={item}>
                    {outputIcon(item)}
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="harness-scenario-block harness-scenario-block--guard">
              <div className="harness-block-heading">
                <span>GIỚI HẠN</span>
                <strong>Điều hệ thống không tự làm</strong>
              </div>
              <ul>
                {scenario.guardrails.map((item) => (
                  <li key={item}>
                    <LockClosed20Regular aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          </div>

          {/* Technical Lens with Interactive Tech Inspector Chips */}
          <details className="harness-technical-lens">
            <summary>
              <span>
                <span className="harness-technical-lens__eyebrow">XEM CẤU TRÚC KỸ THUẬT</span>
                <strong>Tên công nghệ được dùng trong ví dụ này</strong>
              </span>
              <ChevronRight20Regular aria-hidden="true" />
            </summary>
            <div className="harness-technical-lens__body">
              <ul>
                {scenario.technologies.map((item) => (
                  <li key={item}>
                    <button
                      type="button"
                      className="tech-chip-btn"
                      onClick={() => openTechInspector(item)}
                      title={`Xem giải phẫu 3 tầng của ${item}`}
                    >
                      <Sparkle20Regular aria-hidden="true" />
                      <span>{item}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: '14px' }}>
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<Flowchart20Regular />}
                  onClick={() => openTechInspector(null)}
                >
                  Khám phá các nhóm công nghệ
                </Button>
              </div>
              <p>
                Chọn một nhóm để xem cách hoạt động, vai trò trong Veridra và quy trình từ tiếp nhận đến trả kết quả.
              </p>
            </div>
          </details>
        </article>
      </section>

      {/* ================================================================== */}
      {/* FLAGSHIP ENDING (Milestone 2)                                      */}
      {/* ================================================================== */}

      {/* 1. Live Trust & Audit Cockpit */}
      <LiveTrustCockpit />

      {/* 2. 1-Click Interactive Test Drive */}
      <InteractiveTestDrive scenario={scenario} />

      {/* 3. Enterprise Governance Comparison Matrix */}
      <GovernanceMatrixTable />

      {/* Shared Rails */}
      <section className="harness-shared-rails" aria-labelledby="harness-shared-rails-title">
        <div>
          <span className="harness-flagship__eyebrow">LỚP BẢO VỆ CHUNG</span>
          <h2 id="harness-shared-rails-title">Mọi lĩnh vực đều đi qua cùng một cổng kiểm soát.</h2>
        </div>
        <div className="harness-shared-rails__grid">
          {HARNESS_SHARED_RAILS.map((rail) => (
            <div key={rail.label}>
              <span>{rail.label}</span>
              <strong>{rail.value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="harness-conclusion" aria-labelledby="harness-conclusion-title">
        <div>
          <h2 id="harness-conclusion-title">Kết quả tốt chưa đủ. Kết quả phải kiểm tra lại được.</h2>
          <p>Veridra không thay người dùng chịu trách nhiệm cho quyết định nghiệp vụ. Sản phẩm giúp giảm công việc gom nguồn, làm phép tính, soạn đầu ra và lưu bằng chứng, trong khi giữ quyền duyệt ở người dùng.</p>
        </div>
        <dl>
          <div><dt>Khi dữ liệu thiếu</dt><dd>Dừng hoặc ghi rõ giới hạn.</dd></div>
          <div><dt>Khi công cụ ghi</dt><dd>Xem trước, phê duyệt, thực thi, đọc lại.</dd></div>
          <div><dt>Khi đánh giá</dt><dd>Công bố mẫu đo, công thức và giới hạn còn chưa kiểm chứng.</dd></div>
        </dl>
      </section>

      <footer className="harness-flagship__footer">
        <CheckmarkCircle20Regular aria-hidden="true" />
        <p>
          Các luồng ghi được hỗ trợ yêu cầu bước xác nhận theo chính sách của công cụ. Nhật ký ghi nhận sự kiện thao tác; các chỉ số đó không tự chứng minh câu trả lời đúng hoặc loại bỏ hoàn toàn nội dung bịa đặt.
        </p>
      </footer>

      {/* Interactive Tech Inspector Drawer / Modal */}
      <TechInspectorDrawer
        isOpen={isTechDrawerOpen}
        selectedTechId={selectedTechId}
        onClose={() => setIsTechDrawerOpen(false)}
        onSelectTech={(techId) => setSelectedTechId(techId)}
      />
    </section>
  )
}
