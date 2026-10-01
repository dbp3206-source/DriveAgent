import {
  Calculator20Regular,
  CheckmarkCircle20Regular,
  DocumentCheckmark20Regular,
  DocumentTableSearch20Regular,
  DocumentText20Regular,
  Open20Regular,
  ShieldLock20Regular,
  Sparkle20Regular,
  Table20Regular,
} from '@fluentui/react-icons'
import { useEffect, useRef, useState } from 'react'
import {
  STEP_ARTIFACTS,
  type ArtifactType,
  type HarnessScenarioId,
} from '../../harnessScenarios'

// ============================================================================
// 1. STEP 07: INTERACTIVE THUMBNAIL MOCKUP PREVIEW
// ============================================================================

export interface Step07MockupPreviewProps {
  scenarioId: HarnessScenarioId
}

export function Step07MockupPreview({ scenarioId }: Step07MockupPreviewProps) {
  const [activeTab, setActiveTab] = useState<ArtifactType>('sheet')
  const [actionFeedback, setActionFeedback] = useState<string | null>(null)
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (feedbackTimerRef.current) clearTimeout(feedbackTimerRef.current)
    }
  }, [])

  const artifacts = STEP_ARTIFACTS[scenarioId] || STEP_ARTIFACTS.banking
  const currentArtifact = artifacts.find((a) => a.type === activeTab) || artifacts[0]!

  function handleActionClick(actionLabel: string) {
    setActionFeedback(`Đây là mô phỏng giao diện: "${actionLabel}" chưa thực hiện thao tác trên Google Drive hoặc Gmail.`)
    if (feedbackTimerRef.current) clearTimeout(feedbackTimerRef.current)
    feedbackTimerRef.current = setTimeout(() => {
      setActionFeedback(null)
      feedbackTimerRef.current = null
    }, 3500)
  }

  return (
    <div className="step-mockup-preview" data-artifact-type={activeTab}>
      <div className="step-mockup-preview__topbar">
        <div className="step-mockup-preview__tabs" role="tablist" aria-label="Định dạng kết quả đầu ra">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'sheet'}
            className={`step-mockup-tab ${activeTab === 'sheet' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('sheet')}
          >
            <Table20Regular aria-hidden="true" />
            <span>Google Sheets</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'docs'}
            className={`step-mockup-tab ${activeTab === 'docs' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('docs')}
          >
            <DocumentText20Regular aria-hidden="true" />
            <span>Google Docs</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'gmail'}
            className={`step-mockup-tab ${activeTab === 'gmail' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('gmail')}
          >
            <Open20Regular aria-hidden="true" />
            <span>Gmail Draft</span>
          </button>
        </div>
        <span className="step-mockup-preview__status-pill">
          <DocumentCheckmark20Regular aria-hidden="true" />
          {currentArtifact.badge}
        </span>
      </div>

      {/* Artifact Mockup Content Surface */}
      <div className="step-mockup-preview__surface">
        <div className="step-mockup-demo-notice" role="note">
          Dữ liệu và nút bên dưới chỉ minh họa giao diện. Nhấn nút không tạo, sửa, gửi hoặc chia sẻ dữ liệu Google.
        </div>
        <div className="step-mockup-preview__header">
          <div>
            <span className="step-mockup-preview__type-tag">
              {activeTab === 'sheet'
                ? 'BẢNG TÍNH ĐỐI SOÁT & CÔNG THỨC ĐỘNG'
                : activeTab === 'docs'
                ? 'TÀI LIỆU BÁO CÁO & BIÊN BẢN CÓ CẤU TRÚC'
                : 'THƯ ĐIỆN TỬ NHÁP CÓ KIỂM SOÁT (DRAFT ONLY)'}
            </span>
            <h4 className="step-mockup-preview__title">{currentArtifact.title}</h4>
          </div>
        </div>

        {/* Dynamic Metrics Cards */}
        <div className="step-mockup-preview__metrics-grid">
          {Object.entries(currentArtifact.metrics).map(([key, value]) => (
            <div key={key} className="step-mockup-metric-card">
              <span className="step-mockup-metric-card__key">{key}</span>
              <strong className="step-mockup-metric-card__val">{value}</strong>
            </div>
          ))}
        </div>

        {/* Highlight Preview Snippet */}
        <div className="step-mockup-preview__snippet-box">
          <div className="step-mockup-preview__snippet-header">
            <span>BẢN XEM TRƯỚC NỘI DUNG (PREVIEW PROPOSAL)</span>
            <small>Chưa ghi đè cloud</small>
          </div>
          <p className="step-mockup-preview__snippet-text">
            “{currentArtifact.previewSnippet}”
          </p>
        </div>

        {/* Action Buttons */}
        <div className="step-mockup-preview__actions">
          {currentArtifact.actions.map((action) => (
            <button
              key={action}
              type="button"
              className="step-mockup-btn"
              onClick={() => handleActionClick(action)}
            >
              <Sparkle20Regular aria-hidden="true" />
              <span>{action}</span>
            </button>
          ))}
        </div>

        {actionFeedback ? (
          <div className="step-mockup-feedback" role="status">
            <CheckmarkCircle20Regular aria-hidden="true" />
            <span>{actionFeedback}</span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

// ============================================================================
// 2. STEPS 01-06: VISUAL MICRO-CARDS (SOURCES, CALCULATIONS, GATES)
// ============================================================================

export interface StepMicroCardsProps {
  scenarioId: HarnessScenarioId
  stepIndex: number // 0 to 5 for steps 01-06
}

interface MicroCardData {
  sourceTitle: string
  sourceDetail: string
  sourceTags: string[]
  formulaTitle: string
  formulaDetail: string
  formulaTags: string[]
  gateTitle: string
  gateDetail: string
  gateStatus: string
}

const STEP_MICRO_DATA: Record<HarnessScenarioId, Record<number, MicroCardData>> = {
  banking: {
    0: {
      sourceTitle: 'Tập tin giao dịch máy trạm',
      sourceDetail: 'CSV sao kê nội bộ + Thư mục cho phép',
      sourceTags: ['/local', 'CSV', 'Session Scope'],
      formulaTitle: 'Phân giải câu lệnh & Session token',
      formulaDetail: 'ADK Intent Parser + Slash Dispatcher',
      formulaTags: ['ADK Coordinator', 'Prompt Injection Controls'],
      gateTitle: 'Khóa phạm vi tài khoản',
      gateDetail: 'Chỉ đọc thư mục cục bộ được phân quyền',
      gateStatus: 'Khóa ghi cloud',
    },
    1: {
      sourceTitle: 'Đa nguồn dữ liệu liên kết',
      sourceDetail: 'Google Sheets đối tác + PDF quy trình ngân hàng',
      sourceTags: ['/sheet', 'Google Drive', 'SQLite Memory'],
      formulaTitle: 'Phân vùng ngữ cảnh phiên',
      formulaDetail: 'Scoped Context Window (<4.000 tokens)',
      formulaTags: ['Memory Guard', 'Dynamic Partitioning'],
      gateTitle: 'Freshness Checksum Gate',
      gateDetail: 'Ví dụ đối chiếu hash đã lưu; không tự xác nhận chỉ mục khớp bản mới nhất trên Drive nếu chưa đọc lại nguồn.',
      gateStatus: 'Hash khớp · ví dụ mô phỏng',
    },
    2: {
      sourceTitle: 'Vector Index & Sổ cái kiểm toán',
      sourceDetail: 'Qdrant Embedded 768 chiều + SQLite WAL',
      sourceTags: ['Qdrant Local', 'BM25 Index', 'Dense Embeddings'],
      formulaTitle: 'Thuật toán Tái xếp hạng RRF',
      formulaDetail: 'RRF(d) = Σ 1 / (60 + r(d)), Cosine Sim >= 0.75',
      formulaTags: ['RRF k=60', 'Hybrid RAG'],
      gateTitle: 'Lọc thẩm quyền tài liệu',
      gateDetail: 'Tenant ID và Phân quyền cấp thư mục Drive',
      gateStatus: 'Cô lập dữ liệu',
    },
    3: {
      sourceTitle: 'Dữ liệu số dư đối soát',
      sourceDetail: '1.428 bản ghi giao dịch + Tỷ giá liên ngân hàng',
      sourceTags: ['Tabular Frame', 'Decimal Types', 'No Float Drift'],
      formulaTitle: 'Môi trường tính toán Sandbox',
      formulaDetail: 'Python Sandbox AST cô lập, cấm os/sys, timeout 2s',
      formulaTags: ['Calculator Sandbox', 'Kết quả theo biểu thức mẫu'],
      gateTitle: 'Chặn lệnh chuyển tiền tự động',
      gateDetail: 'RBAC: Khóa quyền can thiệp vào tài khoản ngân quỹ',
      gateStatus: 'Minh họa policy chặn',
    },
    4: {
      sourceTitle: 'Chuỗi bàn giao đa tác tử',
      sourceDetail: 'Reconciliation Agent → Compliance Agent → Doc Generator',
      sourceTags: ['A2A Protocol', 'DAG Nodes', 'Structured Envelope'],
      formulaTitle: 'Chuỗi handoff minh họa',
      formulaDetail: 'Phân công agent và bàn giao kết quả theo workflow ví dụ',
      formulaTags: ['Agent Handoff · mô phỏng', 'Human review'],
      gateTitle: 'Cơ chế Human-in-the-Loop',
      gateDetail: 'Tạo bản đề xuất chờ kiểm soát viên xác nhận',
      gateStatus: 'Yêu cầu chữ ký',
    },
    5: {
      sourceTitle: 'Chứng từ và Bằng chứng gốc',
      sourceDetail: 'Biên bản đối soát + 4 Citation tham chiếu',
      sourceTags: ['Citation Marks', 'Page & Line Hash', 'Read-Back'],
      formulaTitle: 'Output Contract Schema Validator',
      formulaDetail: 'Kiểm tra cấu trúc Pydantic/Zod & Loại trích dẫn ảo',
      formulaTags: ['Schema Check · mô phỏng', 'Citation metadata'],
      gateTitle: 'Read-Back Verification API',
      gateDetail: 'Đọc lại dữ liệu vừa chuẩn bị để đối chiếu checksum',
      gateStatus: 'Read-back mẫu · đã qua',
    },
  },
  education: {
    0: {
      sourceTitle: 'Bảng điểm & Hồ sơ học tập',
      sourceDetail: 'Gradebook Google Sheets + Danh sách lớp',
      sourceTags: ['/drive', 'Gradebook', 'Student ID Whitelist'],
      formulaTitle: 'Phân tích mục tiêu sư phạm',
      formulaDetail: 'ADK Intent Parser + Slash Dispatcher /skill:rubric',
      formulaTags: ['Education Domain', 'FERPA Compliance'],
      gateTitle: 'Bảo mật thông tin điểm số',
      gateDetail: 'Khóa quyền xuất bản công khai danh sách điểm',
      gateStatus: 'Ẩn danh hóa',
    },
    1: {
      sourceTitle: 'Hồ sơ tiêu chí & Bài làm',
      sourceDetail: 'Rubric đánh giá chuẩn PDF + Bài tập học viên',
      sourceTags: ['Rubric PDF', 'Student Submissions', 'Teacher Feedback'],
      formulaTitle: 'Bộ phân đoạn tài liệu Layout-aware',
      formulaDetail: 'Cắt đoạn theo số trang và ma trận bảng rubric',
      formulaTags: ['Layout Chunking', 'Table Preservation'],
      gateTitle: 'Phân quyền giáo viên phụ trách',
      gateDetail: 'Chỉ truy cập bài làm của lớp học được phân công',
      gateStatus: 'Đúng lớp phụ trách',
    },
    2: {
      sourceTitle: 'Chỉ mục vector chuẩn năng lực',
      sourceDetail: 'Qdrant Embedded: Thang đo rubric 4 mức độ',
      sourceTags: ['Rubric Vectors', 'Semantic Search', 'SQLite WAL'],
      formulaTitle: 'Truy vấn tương đồng ngữ nghĩa',
      formulaDetail: 'Khớp câu trả lời học viên với từng mức rubric',
      formulaTags: ['Cosine Similarity', 'RRF Reranking'],
      gateTitle: 'Kiểm tra phiên bản Rubric',
      gateDetail: 'Freshness Gate xác minh bản rubric mới nhất',
      gateStatus: 'Rubric chuẩn',
    },
    3: {
      sourceTitle: 'Dữ liệu đánh giá chi tiết',
      sourceDetail: '35 bài nộp + Thang đo 5 tiêu chí kỹ năng',
      sourceTags: ['Rubric RubricScores', 'Gap Matrix', 'Python Engine'],
      formulaTitle: 'Tổng hợp khoảng trống tri thức',
      formulaDetail: 'Python Sandbox tính điểm trung bình từng tiêu chí',
      formulaTags: ['Decimal Sandbox', 'Stat Analysis'],
      gateTitle: 'Cấm tự động sửa điểm',
      gateDetail: 'Giữ nguyên điểm số gốc, chỉ đề xuất can thiệp',
      gateStatus: 'Không sửa điểm',
    },
    4: {
      sourceTitle: 'Phối hợp nhóm chuyên môn',
      sourceDetail: 'Rubric Evaluator → Pedagogy Specialist → Draft Writer',
      sourceTags: ['A2A Routing', 'Pedagogy Chain', 'Specialist Roles'],
      formulaTitle: 'Điều phối đa tác tử sư phạm',
      formulaDetail: 'Lập lộ trình bài tập bổ trợ theo từng mức tiếp thu',
      formulaTags: ['Pedagogy Flow', 'Non-judgmental Tone'],
      gateTitle: 'Kiểm duyệt giọng điệu nhân văn',
      gateDetail: 'Ví dụ policy nhắc kiểm tra giọng điệu; nội dung vẫn cần người dùng rà soát.',
      gateStatus: 'Văn phong tích cực',
    },
    5: {
      sourceTitle: 'Hồ sơ kế hoạch can thiệp',
      sourceDetail: 'Dự thảo kế hoạch Docs + Bảng theo dõi Sheets',
      sourceTags: ['Docs Plan', 'Sheets Matrix', 'Gmail Draft'],
      formulaTitle: 'Ràng buộc trích dẫn Rubric',
      formulaDetail: 'Mỗi nhận xét phải gắn đúng tiêu chí trong Rubric PDF',
      formulaTags: ['Citation Binding', 'Metadata khớp · ví dụ'],
      gateTitle: 'Quyền quyết định của Giáo viên',
      gateDetail: 'Chờ giáo viên trực tiếp phê duyệt trước khi gửi',
      gateStatus: 'Chờ giáo viên',
    },
  },
  ecommerce: {
    0: {
      sourceTitle: 'Hệ thống đơn hàng & Báo cáo',
      sourceDetail: 'Order CSV bán lẻ + Báo cáo chiến dịch khuyến mãi',
      sourceTags: ['/local', 'Order CSV', 'Campaign Log'],
      formulaTitle: 'Phân tích mục tiêu vận hành kho',
      formulaDetail: 'ADK Intent Parser + Slash Dispatcher /skill:campaign',
      formulaTags: ['ADK Orchestrator', 'Multi-source'],
      gateTitle: 'Phân quyền quản lý chuỗi cung ứng',
      gateDetail: 'Chỉ đọc số liệu bán lẻ trong kỳ chiến dịch',
      gateStatus: 'Quyền quản trị kho',
    },
    1: {
      sourceTitle: 'Kho hàng & Chính sách đổi trả',
      sourceDetail: 'Google Sheets tồn kho + PDF quy định bảo hành',
      sourceTags: ['Sheets Tồn kho', 'Chính sách hoàn trả', 'Email khách'],
      formulaTitle: 'Gom bối cảnh đa kênh có kiểm soát',
      formulaDetail: 'Context Harness phân vùng dữ liệu SKU và tỷ lệ hoàn',
      formulaTags: ['Scoped Memory', 'Catalog Context'],
      gateTitle: 'Đồng bộ dữ liệu kho thực tế',
      gateDetail: 'Kiểm tra timestamp cập nhật tồn kho mới nhất',
      gateStatus: 'Tồn kho đồng bộ',
    },
    2: {
      sourceTitle: 'Chỉ mục vector SKU hàng hóa',
      sourceDetail: 'Qdrant Embedded: 1.200 SKU mặt hàng và phản hồi',
      sourceTags: ['Qdrant Local', 'SKU Metadata', 'Feedback Embeddings'],
      formulaTitle: 'Tìm kiếm lai mã hàng & phản hồi',
      formulaDetail: 'RRF(d): Kết hợp SKU Code chính xác và ngữ nghĩa lỗi',
      formulaTags: ['RRF Ranking', 'Hybrid Search'],
      gateTitle: 'Bảo mật chi phí nhập hàng',
      gateDetail: 'Ẩn biên lợi nhuận thô khi xuất sang phân hệ phân tích',
      gateStatus: 'Bảo vệ giá vốn',
    },
    3: {
      sourceTitle: 'Dữ liệu tỷ lệ hoàn & tồn kho an toàn',
      sourceDetail: 'Số liệu xuất/nhập/tồn của 18 SKU cảnh báo thiếu hụt',
      sourceTags: ['Tabular Inventory', 'Return Rates', 'Reorder Point'],
      formulaTitle: 'Tính toán tối ưu hóa điều chuyển',
      formulaDetail: 'Ví dụ phân tích phương án luân chuyển; cần dữ liệu và solver nghiệp vụ để xác nhận tối ưu.',
      formulaTags: ['Inventory Sandbox', 'Cost Optimizer'],
      gateTitle: 'Chặn tự động đổi giá bán & hoàn tiền',
      gateDetail: 'RBAC: Khóa các API thay đổi giá bán hoặc tạo refund',
      gateStatus: 'Chặn thay đổi giá',
    },
    4: {
      sourceTitle: 'Hội đồng chuyên gia logistics',
      sourceDetail: 'Logistics Analyst → Inventory Planner → Notifier',
      sourceTags: ['Multi-Agent DAG', 'Handoff Protocol', 'HITL Proposal'],
      formulaTitle: 'Lập phương án luân chuyển liên kho',
      formulaDetail: 'Ví dụ phân tích phương án luân chuyển; cần dữ liệu và solver nghiệp vụ để xác nhận tối ưu.',
      formulaTags: ['Phương án minh họa', 'Cần xác nhận dữ liệu'],
      gateTitle: 'Duyệt kế hoạch điều phối',
      gateDetail: 'Bắt buộc Giám đốc Vận hành duyệt trước khi xuất phiếu',
      gateStatus: 'Chờ giám đốc duyệt',
    },
    5: {
      sourceTitle: 'Báo cáo và Lệnh điều chuyển',
      sourceDetail: 'Báo cáo Docs + Lệnh kho Sheets + Gmail Draft gửi kho',
      sourceTags: ['Docs Report', 'Sheets Transfer', 'Gmail Logistics'],
      formulaTitle: 'Thẩm định tính toàn vẹn 2 pha',
      formulaDetail: 'Output Contract kiểm tra mã SKU và số lượng điều chuyển',
      formulaTags: ['Output Contract', 'Read-Back API'],
      gateTitle: 'Read-Back xác thực tồn kho',
      gateDetail: 'Đọc lại bảng tính để bảo đảm không vượt quá năng lực kho',
      gateStatus: 'Read-back mẫu · đã qua',
    },
  },
}

export function StepMicroCards({ scenarioId, stepIndex }: StepMicroCardsProps) {
  const safeIndex = Math.max(0, Math.min(5, stepIndex))
  const data = STEP_MICRO_DATA[scenarioId]?.[safeIndex] || STEP_MICRO_DATA.banking[0]!

  return (
    <div className="step-micro-cards" role="region" aria-label="Chi tiết kỹ thuật và kiểm soát an toàn của bước">
      {/* Micro-Card 1: Sources */}
      <div className="step-micro-card step-micro-card--source">
        <div className="step-micro-card__header">
          <DocumentTableSearch20Regular className="step-micro-card__icon" aria-hidden="true" />
          <span>Nguồn tệp & Dữ liệu</span>
        </div>
        <strong className="step-micro-card__title">{data.sourceTitle}</strong>
        <p className="step-micro-card__detail">{data.sourceDetail}</p>
        <div className="step-micro-card__tags">
          {data.sourceTags.map((tag) => (
            <span key={tag} className="step-micro-card__tag">{tag}</span>
          ))}
        </div>
      </div>

      {/* Micro-Card 2: Computation */}
      <div className="step-micro-card step-micro-card--formula">
        <div className="step-micro-card__header">
          <Calculator20Regular className="step-micro-card__icon" aria-hidden="true" />
          <span>Công thức & Xử lý</span>
        </div>
        <strong className="step-micro-card__title">{data.formulaTitle}</strong>
        <p className="step-micro-card__detail">{data.formulaDetail}</p>
        <div className="step-micro-card__tags">
          {data.formulaTags.map((tag) => (
            <span key={tag} className="step-micro-card__tag step-micro-card__tag--formula">{tag}</span>
          ))}
        </div>
      </div>

      {/* Micro-Card 3: Control Gate */}
      <div className="step-micro-card step-micro-card--gate">
        <div className="step-micro-card__header">
          <ShieldLock20Regular className="step-micro-card__icon" aria-hidden="true" />
          <span>Trạng thái kiểm soát</span>
        </div>
        <strong className="step-micro-card__title">{data.gateTitle}</strong>
        <p className="step-micro-card__detail">{data.gateDetail}</p>
        <div className="step-micro-card__status-row">
          <span className="step-micro-card__status-badge">
            <CheckmarkCircle20Regular aria-hidden="true" />
            {data.gateStatus}
          </span>
        </div>
      </div>
    </div>
  )
}
