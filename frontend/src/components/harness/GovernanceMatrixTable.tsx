import {
  CheckmarkCircle20Regular,
  ChevronDown20Regular,
  ChevronUp20Regular,
  DismissCircle20Regular,
  DocumentCheckmark20Regular,
  ShieldCheckmark20Regular,
  Sparkle20Regular,
  Table20Regular,
  Warning20Regular,
} from '@fluentui/react-icons'
import { type ReactNode, useState } from 'react'
import {
  GOVERNANCE_MATRIX,
  type GovernanceRow,
} from '../../harnessScenarios'
import './harnessComponents.css'

export interface GovernanceMatrixTableProps {
  className?: string
}

/**
 * Format markdown bold (**bold**) and italics (*italic*) into semantic React nodes
 * with dedicated high-contrast visual styling.
 */
function renderFormattedText(text?: string | null): ReactNode {
  if (!text) return null
  const parts: (string | ReactNode)[] = []
  const regex = /(\*\*[^*]+\*\*|\*(?!\s)[^*]+(?<!\s)\*)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let key = 0

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={key++} className="hl-strong">
          {token.slice(2, -2)}
        </strong>
      )
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={key++} className="hl-em">
          {token.slice(1, -1)}
        </em>
      )
    } else {
      parts.push(token)
    }
    lastIndex = regex.lastIndex
  }
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }
  return <>{parts}</>
}

/**
 * Split long pilot sentences or semicolon-separated clauses into distinct, punchy bullets.
 */
function formatPilotPoints(text: string): string[] {
  if (!text) return []
  return text
    .split(/;\s*|\.\s+(?=[A-ZĐ])/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

/**
 * Split metrics string separated by '·' into individual metric pills.
 */
function parseMetricPills(metrics: string): string[] {
  if (!metrics) return []
  return metrics
    .split('·')
    .map((m) => m.trim())
    .filter(Boolean)
}

export function GovernanceMatrixTable({ className = '' }: GovernanceMatrixTableProps) {
  const [activeTab, setActiveTab] = useState<'matrix' | 'pilot'>('matrix')
  const [expandedPilotIndex, setExpandedPilotIndex] = useState<number | null>(null)

  const togglePilot = (index: number) => {
    setExpandedPilotIndex(expandedPilotIndex === index ? null : index)
  }

  return (
    <section
      className={`governance-matrix-section ${className}`}
      aria-labelledby="governance-matrix-title"
    >
      {/* Matrix Header & Mode Switcher */}
      <header className="governance-matrix-header">
        <div className="governance-matrix-header__top-row">
          <div>
            <div className="governance-matrix-header__tag">
              <ShieldCheckmark20Regular aria-hidden="true" />
              <span>CÁCH KIỂM SOÁT VÀ VÍ DỤ</span>
            </div>
            <h2 id="governance-matrix-title" className="governance-matrix-header__title">
              Năng lực kiểm soát và giới hạn hiện tại
            </h2>
            <p className="governance-matrix-header__subtitle">
              Các khung tham chiếu bên dưới không phải chứng nhận hoặc kết quả kiểm toán Veridra.
            </p>
          </div>

          <div className="governance-tab-switch" role="tablist" aria-label="Chế độ xem ma trận quản trị">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'matrix'}
              className={`governance-tab-btn ${activeTab === 'matrix' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('matrix')}
            >
              <Table20Regular aria-hidden="true" />
              <span>Ma Trận So Sánh</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'pilot'}
              className={`governance-tab-btn ${activeTab === 'pilot' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('pilot')}
            >
              <DocumentCheckmark20Regular aria-hidden="true" />
              <span>Năm tình huống minh họa</span>
            </button>
          </div>
        </div>
      </header>

      {/* ================================================================== */}
      {/* TAB 1: ENTERPRISE COMPARISON MATRIX TABLE                          */}
      {/* ================================================================== */}
      {activeTab === 'matrix' ? (
        <div className="governance-matrix-table-wrap">
          <table className="governance-matrix-table" role="table">
            <thead>
              <tr>
                <th scope="col" className="col-dimension">Tiêu chí kiểm soát</th>
                <th scope="col" className="col-drive-agent">
                  <div className="col-header-drive">
                    <div className="col-header-drive__title-row">
                      <span className="col-header-drive__badge">Theo thiết kế</span>
                      <strong>Veridra, sáu bước kiểm soát</strong>
                    </div>
                    <span className="col-header-drive__sub">Kiểm tra quyền trước từng thao tác</span>
                  </div>
                </th>
                <th scope="col" className="col-generic-llm">
                  <div className="col-header-other">
                    <strong>Trợ lý chỉ tạo văn bản</strong>
                    <span className="col-header-other__sub">Thực thi tự do · Thiếu rào chắn</span>
                  </div>
                </th>
                <th scope="col" className="col-traditional-rpa">
                  <div className="col-header-other">
                    <strong>Tự động hóa theo kịch bản</strong>
                    <span className="col-header-other__sub">Kịch bản tĩnh · Chi phí bảo trì cao</span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {GOVERNANCE_MATRIX.map((row: GovernanceRow, index: number) => {
                const isPilotOpen = expandedPilotIndex === index
                const rowKey = row.dimension || row.criterion || index
                return [
                  <tr key={rowKey} className={`row-matrix-data ${isPilotOpen ? 'is-pilot-expanded' : ''}`}>
                    {/* Dimension Column */}
                    <td className="cell-dimension">
                      <div className="dimension-box">
                        <span className="dimension-num">0{index + 1}</span>
                        <strong className="dimension-title">{row.dimension || row.criterion}</strong>
                      </div>

                      {row.standardRef ? (
                        <div className="dimension-standard-badge">
                          <ShieldCheckmark20Regular aria-hidden="true" />
                          <span>{row.standardRef}</span>
                        </div>
                      ) : null}

                      {row.keyAdvantage ? (
                        <span className="dimension-advantage">
                          <Sparkle20Regular aria-hidden="true" />
                          {row.keyAdvantage}
                        </span>
                      ) : null}

                      {row.pilotExample ? (
                        <button
                          type="button"
                          className={`dimension-pilot-toggle ${isPilotOpen ? 'is-open' : ''}`}
                          onClick={() => togglePilot(index)}
                          aria-expanded={isPilotOpen}
                          title="Xem tình huống minh họa"
                        >
                          <Sparkle20Regular aria-hidden="true" />
                          <span>{isPilotOpen ? 'Đóng ví dụ' : 'Xem ví dụ'}</span>
                          {isPilotOpen ? <ChevronUp20Regular aria-hidden="true" /> : <ChevronDown20Regular aria-hidden="true" />}
                        </button>
                      ) : null}
                    </td>

                    {/* DriveAgent Column (Featured) */}
                    <td className="cell-drive-agent">
                      <div className="cell-verdict-pill cell-verdict-pill--success">
                        <CheckmarkCircle20Regular aria-hidden="true" />
                        <span>Năng lực theo thiết kế</span>
                      </div>
                      <div className="cell-body">
                        <p className="cell-summary">{renderFormattedText(row.driveAgent)}</p>
                        {row.driveBullets && row.driveBullets.length > 0 ? (
                          <ul className="cell-bullets cell-bullets--success">
                            {row.driveBullets.map((bullet, bIdx) => (
                              <li key={bIdx}>{renderFormattedText(bullet)}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    </td>

                    {/* Generic LLM Column */}
                    <td className="cell-generic-llm">
                      <div className="cell-verdict-pill cell-verdict-pill--warning">
                        <Warning20Regular aria-hidden="true" />
                        <span>Rủi ro nội dung sai</span>
                      </div>
                      <div className="cell-body">
                        <p className="cell-summary">
                          {renderFormattedText(row.genericLlm || (row as unknown as Record<string, string>).genericLLM)}
                        </p>
                        {row.genericBullets && row.genericBullets.length > 0 ? (
                          <ul className="cell-bullets cell-bullets--warning">
                            {row.genericBullets.map((bullet, bIdx) => (
                              <li key={bIdx}>{renderFormattedText(bullet)}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    </td>

                    {/* Traditional RPA Column */}
                    <td className="cell-traditional-rpa">
                      <div className="cell-verdict-pill cell-verdict-pill--danger">
                        <DismissCircle20Regular aria-hidden="true" />
                        <span>Kịch bản khó thích nghi</span>
                      </div>
                      <div className="cell-body">
                        <p className="cell-summary">
                          {renderFormattedText(row.traditionalRpa || (row as unknown as Record<string, string>).traditionalRPA)}
                        </p>
                        {row.rpaBullets && row.rpaBullets.length > 0 ? (
                          <ul className="cell-bullets cell-bullets--danger">
                            {row.rpaBullets.map((bullet, bIdx) => (
                              <li key={bIdx}>{renderFormattedText(bullet)}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    </td>
                  </tr>,

                  /* Full-width Pilot Expansion Tray (Balanced, Non-Overwhelming) */
                  isPilotOpen && row.pilotExample ? (
                    <tr key={`pilot-tray-${rowKey}`} className="row-pilot-expanded">
                      <td colSpan={4} className="cell-pilot-tray">
                        <div className="pilot-tray-card" role="region" aria-label={`Chi tiết minh họa cho ${row.criterion}`}>
                          <header className="pilot-tray-card__top">
                            <div className="pilot-tray-card__title-group">
                              <div className="pilot-tray-card__badge-row">
                                <span className="pilot-tray-idx">VÍ DỤ 0{index + 1}</span>
                                <span className="pilot-tray-criterion">{row.criterion || row.dimension}</span>
                              </div>
                              <h4 className="pilot-tray-card__title">{row.pilotExample.title}</h4>
                              <p className="pilot-tray-card__scope">
                                <strong>Phạm vi thử nghiệm:</strong> {row.pilotExample.scope}
                              </p>
                            </div>
                            <div className="pilot-tray-card__actions">
                              <button
                                type="button"
                                className="pilot-tray-btn-tab"
                                onClick={() => setActiveTab('pilot')}
                              >
                                <DocumentCheckmark20Regular aria-hidden="true" />
                                <span>Mở Báo Cáo Đầy Đủ</span>
                              </button>
                              <button
                                type="button"
                                className="pilot-tray-close-btn"
                                onClick={() => setExpandedPilotIndex(null)}
                                aria-label="Đóng chi tiết ví dụ"
                              >
                                ✕ Thu gọn
                              </button>
                            </div>
                          </header>

                          <div className="pilot-tray-card__grid">
                            <div className="pilot-tray-side pilot-tray-side--other">
                              <div className="pilot-tray-side__header">
                                <DismissCircle20Regular className="side-icon is-danger" aria-hidden="true" />
                                <strong>Hạn chế ở Sản phẩm khác theo thiết kế giả định</strong>
                              </div>
                              <ul className="pilot-tray-side__bullets">
                                {formatPilotPoints(row.pilotExample.otherIssue).map((point, pIdx) => (
                                  <li key={pIdx}>{renderFormattedText(point)}</li>
                                ))}
                              </ul>
                            </div>

                            <div className="pilot-tray-side pilot-tray-side--drive">
                              <div className="pilot-tray-side__header">
                                <CheckmarkCircle20Regular className="side-icon is-success" aria-hidden="true" />
                                <strong>Cách xử lý của Veridra</strong>
                              </div>
                              <ul className="pilot-tray-side__bullets">
                                {formatPilotPoints(row.pilotExample.driveSolution).map((point, pIdx) => (
                                  <li key={pIdx}>{renderFormattedText(point)}</li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          <footer className="pilot-tray-card__metrics-bar">
                            <span className="metrics-bar__label">Phạm vi minh họa:</span>
                            <div className="metrics-bar__pills">
                              {parseMetricPills(row.pilotExample.metrics).map((pill, pillIdx) => (
                                <span key={pillIdx} className="metric-pill">
                                  {pill}
                                </span>
                              ))}
                            </div>
                          </footer>
                        </div>
                      </td>
                    </tr>
                  ) : null,
                ]
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ================================================================== */
        /* TAB 2: DEDICATED EVALUATION REPORT                           */
        /* ================================================================== */
        <div className="governance-pilot-report" role="region" aria-label="Các kịch bản minh họa">
          <div className="governance-pilot-intro">
            <span className="governance-pilot-intro__eyebrow">DỮ LIỆU VÀ KẾT QUẢ GIẢ LẬP</span>
            <h3>Kịch bản dùng để giải thích cách kiểm soát</h3>
            <p>
              Đây không phải khảo sát khách hàng, kết quả thử nghiệm hay so sánh sản phẩm đã kiểm nghiệm. Kết quả đo chỉ được công bố khi có mẫu, phương pháp và bằng chứng.
            </p>
          </div>

          <div className="governance-pilot-cards-grid">
            {GOVERNANCE_MATRIX.map((row, idx) => {
              if (!row.pilotExample) return null
              const p = row.pilotExample
              return (
                <article key={idx} className="governance-pilot-card">
                  <header className="governance-pilot-card__header">
                    <div className="governance-pilot-card__tag-row">
                      <span className="pilot-idx">VÍ DỤ 0{idx + 1}</span>
                      <span className="pilot-criterion">{row.criterion || row.dimension}</span>
                    </div>
                    <h4 className="governance-pilot-card__title">{p.title}</h4>
                    <p className="governance-pilot-card__scope"><strong>Phạm vi:</strong> {p.scope}</p>
                  </header>

                  <div className="governance-pilot-card__comparison">
                    {/* Other products issue */}
                    <div className="pilot-side pilot-side--other">
                      <div className="pilot-side__header">
                        <DismissCircle20Regular aria-hidden="true" />
                        <strong>Rủi ro cần kiểm tra</strong>
                      </div>
                      <ul className="pilot-card__bullets">
                        {formatPilotPoints(p.otherIssue).map((pt, ptIdx) => (
                          <li key={ptIdx}>{renderFormattedText(pt)}</li>
                        ))}
                      </ul>
                    </div>

                    {/* DriveAgent breakthrough */}
                    <div className="pilot-side pilot-side--drive">
                      <div className="pilot-side__header">
                        <CheckmarkCircle20Regular aria-hidden="true" />
                        <strong>Luồng Veridra dự kiến</strong>
                      </div>
                      <ul className="pilot-card__bullets">
                        {formatPilotPoints(p.driveSolution).map((pt, ptIdx) => (
                          <li key={ptIdx}>{renderFormattedText(pt)}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <footer className="governance-pilot-card__footer">
                    <span className="metrics-label">Phạm vi minh họa:</span>
                    <div className="governance-pilot-card__pills">
                      {parseMetricPills(p.metrics).map((pill, pillIdx) => (
                        <span key={pillIdx} className="metric-pill">
                          {pill}
                        </span>
                      ))}
                    </div>
                  </footer>
                </article>
              )
            })}
          </div>
        </div>
      )}

      {/* Footer Assurance */}
      <footer className="governance-matrix-footer">
        <div className="governance-matrix-footer__note">
          <ShieldCheckmark20Regular aria-hidden="true" />
          <span>
            Khung tham chiếu giúp tổ chức kiểm soát cần kiểm chứng theo phạm vi triển khai; giao diện này không khẳng định Veridra đã được chứng nhận NIST, SOC 2 hoặc ISO.
          </span>
        </div>
      </footer>
    </section>
  )
}
