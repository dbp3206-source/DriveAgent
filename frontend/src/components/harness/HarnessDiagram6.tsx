import {
  ArrowRight20Regular,
  Bot20Regular,
  Brain20Regular,
  CheckmarkCircle20Regular,
  Database20Regular,
  Dismiss20Regular,
  DocumentCheckmark20Regular,
  Flowchart20Regular,
  Info20Regular,
  LockClosed20Regular,
  Open20Regular,
  Person20Regular,
  Play20Regular,
  ShieldCheckmark16Regular,
  ShieldCheckmark20Regular,
  Sparkle20Regular,
  Warning20Regular,
  Wrench20Regular,
} from '@fluentui/react-icons'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { HarnessScenarioId } from '../../harnessScenarios'
import './harnessComponents.css'

export type DiagramViewMode = 'business' | 'safety' | 'evidence'

export interface HarnessDiagram6Props {
  domainId: HarnessScenarioId
  activeViewMode?: DiagramViewMode
  onViewModeChange?: (mode: DiagramViewMode) => void
  onSelectTier?: (tierId: number) => void
  onSelectStep?: (stepIndex: number) => void
  onInspectNode?: (nodeId: string) => void
}

export type DiagramNodeCategory = 'business' | 'safety' | 'evidence' | 'storage' | 'output' | 'stop'

export interface DiagramNodeItem {
  id: string
  tierTag: string
  name: string
  techKeyword: string
  metaphor: string
  driveAgentRole: string
  anatomy: [string, string, string] // [1. Kích hoạt, 2. Kiểm soát, 3. Xuất kết quả]
  targetStepNumber: number // 1 to 7
  targetStepTitle: string
  harnessTier?: number // 1 to 6
  category: DiagramNodeCategory
  color: string
  domainHighlights: Record<HarnessScenarioId, string>
}

export type DiagramNodeId =
  | 'user-persona'
  | 'terminal-dispatcher'
  | 'adk-coordinator'
  | 'orchestration-harness'
  | 'storage-infra'
  | 'context-harness'
  | 'tool-harness'
  | 'evaluation-harness'
  | 'governed-output'
  | 'safe-halt-gate'

const DIAGRAM_NODES: Record<DiagramNodeId, DiagramNodeItem> = {
  'user-persona': {
    id: 'user-persona',
    tierTag: 'GIAI ĐOẠN 1 · KHỞI TẠO',
    name: 'Doanh Nghiệp / User Persona',
    techKeyword: 'User Intent & Persona Identity',
    metaphor: 'Người ủy thác công việc — Đóng vai trò là lãnh đạo hoặc chuyên viên nghiệp vụ đặt ra mục tiêu bài toán, quy định ngân sách và giới hạn phạm vi cho trợ lý số.',
    driveAgentRole: 'Có kiểm tra danh tính phiên, role và OAuth scope ở các luồng được bảo vệ; chưa phải một kiến trúc Zero Trust đã được kiểm định.',
    anatomy: [
      'Kích hoạt: Tiếp nhận mục tiêu nghiệp vụ tự nhiên hoặc câu lệnh slash kèm tập tin chứng từ đính kèm.',
      'Kiểm soát: Xác thực danh tính người dùng, kiểm tra quyền truy cập thư mục Google Workspace được ủy quyền.',
      'Xuất kết quả: Khởi tạo phiên làm việc có trạng thái (Stateful Session) chuyển giao an toàn sang Dispatcher.',
    ],
    targetStepNumber: 1,
    targetStepTitle: 'Tiếp nhận yêu cầu & Thiết lập ngữ cảnh',
    category: 'business',
    color: '#38bdf8',
    domainHighlights: {
      banking: 'Kế toán viên ngân hàng yêu cầu đối soát 1.428 giao dịch Q3 giữa sao kê CSV nội bộ và Google Sheets đối tác.',
      education: 'Giáo viên phụ trách yêu cầu nhận diện lỗ hổng kiến thức từ bảng điểm và bài nộp học viên theo rubric chuẩn.',
      ecommerce: 'Quản lý vận hành yêu cầu phân tích biến động đơn hàng và đề xuất phương án điều chuyển 1.200 SKU kho.',
    },
  },
  'terminal-dispatcher': {
    id: 'terminal-dispatcher',
    tierTag: 'TIẾP NHẬN & PHÂN QUYỀN',
    name: 'Terminal Dispatcher',
    techKeyword: 'Command Hub & Slash Dispatcher',
    metaphor: 'Lễ tân phân luồng thông minh — Tiếp nhận hồ sơ, kiểm tra thẻ ra vào và phân loại chính xác tới đúng phòng ban chuyên trách mà không làm thất lạc dữ liệu.',
    driveAgentRole: 'Bóc tách các cờ lệnh slash (/skill, /local, /sheet, /drive), kiểm tra whitelist tham số và gán token quyền hạn tối thiểu cho phiên làm việc.',
    anatomy: [
      'Kích hoạt: Bắt sự kiện gõ lệnh slash hoặc chọn kịch bản mẫu từ Terminal Command Hub.',
      'Kiểm soát: Chống injection, phân giải token quyền hạn và kiểm tra whitelist cờ lệnh nghiêm ngặt.',
      'Xuất kết quả: Gói cấu hình phiên chuẩn hóa được nạp thẳng vào ADK Coordinator.',
    ],
    targetStepNumber: 1,
    targetStepTitle: 'Phân giải cờ lệnh & Chọn nhóm chuyên trách',
    category: 'business',
    color: '#60a5fa',
    domainHighlights: {
      banking: 'Chuẩn hóa lệnh /skill:daily_reconciliation /local /sheet cho kỳ đối soát sổ sách kế toán.',
      education: 'Kích hoạt cờ /skill:rubric_support /drive /doc để bảo mật bảng điểm học sinh.',
      ecommerce: 'Phân giải cờ /skill:campaign_review /auto /sheet cho bài toán điều phối kho hàng.',
    },
  },
  'adk-coordinator': {
    id: 'adk-coordinator',
    tierTag: 'TẦNG 01 · AGENT FRAMEWORK ★',
    name: 'ADK Coordinator',
    techKeyword: 'Google ADK Agent Framework',
    metaphor: 'Coordinator quản lý lượt chạy và chuyển việc giữa các agent theo hướng dẫn cùng giới hạn runtime đã cấu hình.',
    driveAgentRole: 'Google ADK điều phối agent và handoff; lượt gọi mô hình bị giới hạn theo cấu hình, nhưng không phải planner DAG hay token budget cố định 4.000 token.',
    anatomy: [
      'Kích hoạt: Tiếp nhận phiên làm việc đã chuẩn hóa từ Terminal Dispatcher.',
      'Kiểm soát: Giới hạn lượt gọi theo cấu hình và timeout của luồng; không có cycle detector tổng quát được khẳng định ở đây.',
      'Xuất kết quả: Các handoff/tool event quan sát được trong trace của lượt chạy.',
    ],
    targetStepNumber: 2,
    targetStepTitle: 'Phân chia mục tiêu & Lập kế hoạch thực thi',
    harnessTier: 1,
    category: 'business',
    color: '#818cf8',
    domainHighlights: {
      banking: 'Lập kế hoạch đối soát 3 pha: Thu thập sao kê → Tính toán chênh lệch → Soạn thảo biên bản.',
      education: 'Thiết lập quy trình đánh giá: Đối chiếu rubric → Khoanh vùng điểm yếu → Đề xuất lộ trình.',
      ecommerce: 'Lập sơ đồ phân tích: Gom dữ liệu hoàn đơn → Phân tích tồn kho SKU → Lên phương án xe.',
    },
  },
  'orchestration-harness': {
    id: 'orchestration-harness',
    tierTag: 'TẦNG 05 · ORCHESTRATION',
    name: 'Multi-Agent DAG',
    techKeyword: 'DAG Multi-Agent & 2-Phase Approval',
    metaphor: 'Nhạc trưởng chỉ huy dàn nhạc — Phân việc nhịp nhàng giữa các chuyên gia, ngăn chặn vòng lặp và luôn dừng lại chờ bạn phê duyệt.',
    driveAgentRole: 'Đồ thị thực thi không lặp (DAG), bàn giao công việc A2A có kiểm soát và cơ chế Human-in-the-Loop 2 pha: Đề xuất → Người duyệt → Thi hành.',
    anatomy: [
      'Kích hoạt: Nhận kết quả từ Tool Harness để chuyển giao cho chuyên viên tổng hợp biên bản.',
      'Kiểm soát: Giới hạn độ sâu tối đa 5 bước chuyển việc, khóa hành vi ghi cloud cho đến khi có chữ ký số.',
      'Xuất kết quả: Bản thảo hồ sơ nghiệp vụ hoàn chỉnh sẵn sàng trình duyệt người dùng.',
    ],
    targetStepNumber: 5,
    targetStepTitle: 'Phối hợp đa tác tử & Soạn thảo bản đề xuất',
    harnessTier: 5,
    category: 'safety',
    color: '#f59e0b',
    domainHighlights: {
      banking: 'Tác tử đối soát bàn giao số liệu cho tác tử lập biên bản Google Docs.',
      education: 'Chuyên viên phân tích phối hợp cùng chuyên viên sư phạm xây dựng lộ trình can thiệp.',
      ecommerce: 'Nhóm phân tích đơn hàng chuyển phương án cho tác tử điều phối lịch xe tải.',
    },
  },
  'storage-infra': {
    id: 'storage-infra',
    tierTag: 'TẦNG 03 · HẠ TẦNG NỀN',
    name: 'Qdrant & SQLite WAL',
    techKeyword: 'Qdrant Vector DB & SQLite WAL Audit',
    metaphor: 'Kho vector và nhật ký thao tác cục bộ theo cấu hình. Một số bước tạo embedding hoặc gọi mô hình vẫn có thể gửi dữ liệu tới nhà cung cấp đã cấu hình; SQLite WAL không tự làm nhật ký bất biến.',
    driveAgentRole: 'Qdrant Embedded lưu và truy vấn vector cục bộ; độ trễ phải đo theo môi trường thực. SQLite WAL lưu sự kiện audit, nhưng không tự chống sửa hoặc xóa.',
    anatomy: [
      'Kích hoạt: Lưu trữ vector embedding 768 chiều và ghi nhật ký mọi quyết định của tác tử.',
      'Kiểm soát: Chế độ WAL đảm bảo đọc đồng thời không chặn ghi; tuân thủ giao dịch ACID toàn vẹn.',
      'Xuất kết quả: Truy vấn vector siêu tốc và bộ dữ liệu minh chứng phục vụ thanh tra pháp lý.',
    ],
    targetStepNumber: 3,
    targetStepTitle: 'Lưu trữ bảo mật tại chỗ & Ghi vết kiểm toán',
    harnessTier: 3,
    category: 'storage',
    color: '#38bdf8',
    domainHighlights: {
      banking: 'Ví dụ minh họa cách ghi sự kiện đối soát vào SQLite WAL; bản ghi cần backup và kiểm soát quyền riêng, không phải sổ cái bất biến.',
      education: 'Chỉ mục vector rubric tại máy trạm, bảo mật tuyệt đối điểm số học sinh.',
      ecommerce: 'Lưu trữ chỉ số biến động tồn kho và nhật ký quyết định điều chuyển hàng hóa.',
    },
  },
  'context-harness': {
    id: 'context-harness',
    tierTag: 'TẦNG 02 · CONTEXT HARNESS',
    name: 'Hybrid RAG & Memory',
    techKeyword: 'Dense + BM25 Retrieval & RRF Reranking',
    metaphor: 'Thủ thư tra cứu mẫn cán — Gom đúng cuốn sổ và điều khoản liên quan nhất, không để tài liệu thừa làm phân tâm người thực hiện.',
    driveAgentRole: 'Tìm kiếm lai kết hợp Dense Vector (ngữ nghĩa) và Lexical BM25 (từ khóa chính xác), tái xếp hạng RRF và bảo đảm bối cảnh <4.000 tokens.',
    anatomy: [
      'Kích hoạt: Nhận truy vấn mở rộng bối cảnh từ ADK Coordinator hoặc Orchestration Harness.',
      'Kiểm soát: Freshness Gate kiểm tra content hash tệp trên Drive để từ chối dữ liệu cũ lỗi thời.',
      'Xuất kết quả: Bối cảnh cô đọng, kèm nguồn dẫn trích xuất chính xác theo số trang, số dòng.',
    ],
    targetStepNumber: 3,
    targetStepTitle: 'Thu thập hồ sơ & Tìm bằng chứng trích dẫn',
    harnessTier: 2,
    category: 'evidence',
    color: '#c084fc',
    domainHighlights: {
      banking: 'Truy xuất quy trình kiểm toán mục 4.2 và sổ cái đối soát nội bộ kỳ trước.',
      education: 'Lập chỉ mục rubric PDF theo từng tiêu chí chấm điểm và hồ sơ năng lực học viên.',
      ecommerce: 'Nạp danh mục 1.200 SKU cùng chính sách đổi trả và định mức tồn kho an toàn.',
    },
  },
  'tool-harness': {
    id: 'tool-harness',
    tierTag: 'TẦNG 04 · TOOL HARNESS',
    name: '31 Tools & Sandbox',
    techKeyword: 'Tool Registry & Python AST Sandbox',
    metaphor: 'Bộ tính toán giới hạn biểu thức và các công cụ theo quyền; không cấp cho mô hình khả năng chạy Python tổng quát.',
    driveAgentRole: 'Tool Registry kiểm tra role, scope và yêu cầu xác nhận theo từng tool. Calculator dùng allowlist AST; không phải mọi tool đều chỉ đọc.',
    anatomy: [
      'Kích hoạt: Nhận yêu cầu tính toán hoặc trích xuất từ tác tử chuyên trách.',
      'Kiểm soát: Sandbox AST cô lập module nhạy cảm, áp đặt timeout 2.000ms và chặn quyền ghi ngoài thẩm quyền.',
      'Xuất kết quả: Giá trị cùng biểu thức để người dùng đối chiếu; tính đúng còn phụ thuộc dữ liệu đầu vào và quy tắc nghiệp vụ.',
    ],
    targetStepNumber: 4,
    targetStepTitle: 'Tính toán độc lập & Đối soát số liệu trong Sandbox',
    harnessTier: 4,
    category: 'safety',
    color: '#fbbf24',
    domainHighlights: {
      banking: 'Khớp 1.428 dòng giao dịch, tìm ra chính xác 2 khoản lệch trị giá 12.450.000 ₫.',
      education: 'Tính điểm trung bình theo rubric, nhận diện 4 học viên cần hỗ trợ thuật toán.',
      ecommerce: 'Phân tích tỷ lệ hoàn đơn 4.8% và tính toán định mức xe tải cần điều chuyển.',
    },
  },
  'evaluation-harness': {
    id: 'evaluation-harness',
    tierTag: 'TẦNG 06 · EVALUATION',
    name: 'Citation & Read-back',
    techKeyword: 'Citation Binding & Read-back Audit',
    metaphor: 'Lớp kiểm tra cấu trúc và liên kết nguồn giúp người dùng xem lại kết quả; không thay thế việc xác minh ngữ nghĩa.',
    driveAgentRole: 'Output contract kiểm tra định dạng; citation metadata liên kết marker với nguồn trong luồng hỗ trợ. Read-back chỉ chạy trên trường mà từng tool đọc lại được.',
    anatomy: [
      'Kích hoạt: Tiếp nhận bản thảo kết quả và danh mục trích dẫn chứng từ.',
      'Kiểm soát: Các kiểm tra đã triển khai có thể phát hiện một số lỗi marker, trường và hợp đồng đầu ra; không xác nhận mọi claim đều được nguồn chứng minh.',
      'Xuất kết quả: Câu trả lời/đề xuất cùng trạng thái kiểm tra thực tế của luồng.',
    ],
    targetStepNumber: 6,
    targetStepTitle: 'Thẩm định trích dẫn & Kiểm duyệt theo chính sách',
    harnessTier: 6,
    category: 'evidence',
    color: '#34d399',
    domainHighlights: {
      banking: 'Kịch bản minh họa yêu cầu gắn nguồn cho các dòng sao kê 312 và 849 trước khi tạo Sheet đối soát.',
      education: 'So khớp từng nhận xét với tiêu chí rubric, loại bỏ từ ngữ phán xét chủ quan.',
      ecommerce: 'Xác thực căn cứ tồn kho thực tế trước khi đề xuất lệnh chuyển hàng.',
    },
  },
  'governed-output': {
    id: 'governed-output',
    tierTag: 'KẾT QUẢ KIỂM CHỨNG ★',
    name: 'Governed Output',
    techKeyword: 'Verified Google Workspace Artifacts',
    metaphor: 'Proposal cho thao tác ghi được hỗ trợ cho phép người dùng xem trước và xác nhận trước khi thực thi.',
    driveAgentRole: 'Một số thao tác ghi đi qua preview/approval và audit theo hợp đồng tool; phạm vi kiểm tra, lịch sử phiên bản và read-back khác nhau theo loại tài nguyên.',
    anatomy: [
      'Kích hoạt: Người dùng nhấn nút chấp thuận trên giao diện phê duyệt đề xuất.',
      'Kiểm soát: Ghi có điều kiện lên Google Drive, kiểm tra checksum toàn vẹn qua Read-back API.',
      'Xuất kết quả: Tệp Drive cùng bản ghi AuditEvent có thể đối chiếu theo quyền và request ID.',
    ],
    targetStepNumber: 7,
    targetStepTitle: 'Bàn giao kết quả thực tế có kiểm chứng & Chờ ký',
    category: 'output',
    color: '#10b981',
    domainHighlights: {
      banking: 'Tạo Google Sheet đối soát 2 khoản lệch và bản nháp Docs trình Ban Kiểm soát.',
      education: 'Xuất Google Docs kế hoạch bồi dưỡng và Gmail Draft gửi phụ huynh học sinh.',
      ecommerce: 'Lập bảng phân bổ SKU Google Sheets và bản nháp thư điều động kho vận.',
    },
  },
  'safe-halt-gate': {
    id: 'safe-halt-gate',
    tierTag: 'PHÒNG VỆ KHẨN CẤP',
    name: 'Safe Halt Gate',
    techKeyword: 'Defensive Circuit Breaker Sentinel',
    metaphor: 'Cổng dừng có kiểm soát — Từ chối hoặc yêu cầu người dùng xử lý tiếp khi một điều kiện bảo vệ được hỗ trợ phát hiện; không thay thế kiểm tra nghiệp vụ.',
    driveAgentRole: 'Các policy/tool guard có thể dừng thao tác khi phát hiện một điều kiện được hỗ trợ, như thiếu quyền; không phải bộ phát hiện mọi sai lệch nghiệp vụ.',
    anatomy: [
      'Kích hoạt: Một policy hoặc công cụ hỗ trợ phát hiện điều kiện cần dừng, như thiếu quyền hay dữ liệu đầu vào không hợp lệ.',
      'Kiểm soát: Từ chối hoặc yêu cầu duyệt theo hành vi của guard/tool; không tuyên bố thu hồi token hay đóng băng toàn hệ thống nếu luồng không thực hiện.',
      'Xuất kết quả: Lý do dừng mà policy/tool thực tế ghi nhận để người dùng xử lý tiếp.',
    ],
    targetStepNumber: 6,
    targetStepTitle: 'Rào cản phòng vệ dừng an toàn khi gặp sự cố',
    category: 'stop',
    color: '#f43f5e',
    domainHighlights: {
      banking: 'Chốt ngắt kích hoạt khi phát hiện lệnh chuyển tiền tự động hoặc lệch số chưa rõ lý do.',
      education: 'Dừng ngay nếu phát hiện hành vi tự ý sửa điểm trong Gradebook mà không có rubric.',
      ecommerce: 'Khóa lệnh tức thì nếu kịch bản đòi tự ý hạ giá bán hoặc hủy đơn hàng của khách.',
    },
  },
}

const MODE_DESCRIPTIONS: Record<DiagramViewMode, { title: string; desc: string; buttonLabel: string }> = {
  business: {
    buttonLabel: 'Quy trình 4 Giai đoạn',
    title: 'Toàn cảnh Quy trình 4 Giai đoạn (End-to-End Workflow)',
    desc: 'Hành trình liền mạch như một người trợ lý đắc lực: [GĐ 1] Tiếp nhận mục tiêu → [GĐ 2] Điều phối tác tử → [GĐ 3] Thu thập hồ sơ → [GĐ 4] Xử lý & Xuất báo cáo đã kiểm duyệt.',
  },
  safety: {
    buttonLabel: 'Giai đoạn Xử lý & Rào chắn',
    title: 'Giai đoạn Xử lý Công cụ & Rào Chắn An Toàn (Execution & Governance)',
    desc: 'Trực quan hóa calculator allowlist AST, kiểm tra quyền RBAC và các điểm dừng có trong từng tool; đây không phải cơ chế chặn mọi sai lệch nghiệp vụ.',
  },
  evidence: {
    buttonLabel: 'Giai đoạn Thu thập & Bằng chứng',
    title: 'Giai đoạn Thu Thập Tri Thức & Bằng Chứng Pháp Lý (Knowledge & Evidence)',
    desc: 'Minh họa chu trình truy xuất Qdrant, audit SQLite WAL và liên kết citation metadata trước thao tác ghi Drive; không phải chứng cứ pháp lý hay kiểm chứng ngữ nghĩa 100%.',
  },
}

function getNodeIcon(nodeId: string) {
  switch (nodeId) {
    case 'user-persona':
      return <Person20Regular aria-hidden="true" />
    case 'terminal-dispatcher':
      return <Bot20Regular aria-hidden="true" />
    case 'adk-coordinator':
      return <Bot20Regular aria-hidden="true" />
    case 'context-harness':
      return <Brain20Regular aria-hidden="true" />
    case 'storage-infra':
      return <Database20Regular aria-hidden="true" />
    case 'tool-harness':
      return <Wrench20Regular aria-hidden="true" />
    case 'orchestration-harness':
      return <Flowchart20Regular aria-hidden="true" />
    case 'evaluation-harness':
      return <ShieldCheckmark20Regular aria-hidden="true" />
    case 'governed-output':
      return <DocumentCheckmark20Regular aria-hidden="true" />
    case 'safe-halt-gate':
      return <Warning20Regular aria-hidden="true" />
    default:
      return <Sparkle20Regular aria-hidden="true" />
  }
}

function getNode(id: DiagramNodeId): DiagramNodeItem {
  const node = DIAGRAM_NODES[id]
  if (!node) {
    throw new Error(`Diagram node not found: ${id}`)
  }
  return node
}

export function HarnessDiagram6({
  domainId,
  activeViewMode: controlledMode,
  onViewModeChange,
  onSelectTier,
  onSelectStep,
  onInspectNode,
}: HarnessDiagram6Props) {
  const [internalMode, setInternalMode] = useState<DiagramViewMode>('business')
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  const nodeUser = getNode('user-persona')
  const nodeHub = getNode('terminal-dispatcher')
  const nodeAdk = getNode('adk-coordinator')
  const nodeOrch = getNode('orchestration-harness')
  const nodeStorage = getNode('storage-infra')
  const nodeContext = getNode('context-harness')
  const nodeTools = getNode('tool-harness')
  const nodeEval = getNode('evaluation-harness')
  const nodeOutput = getNode('governed-output')
  const nodeStop = getNode('safe-halt-gate')

  const mode = controlledMode ?? internalMode
  const modeInfo = MODE_DESCRIPTIONS[mode]

  const handleModeSelect = (nextMode: DiagramViewMode) => {
    setInternalMode(nextMode)
    onViewModeChange?.(nextMode)
  }

  const handleInspect = useCallback((nodeId: string) => {
    setInspectedNodeId(nodeId)
    onInspectNode?.(nodeId)
    const node = DIAGRAM_NODES[nodeId as DiagramNodeId]
    if (node) {
      if (node.harnessTier) {
        onSelectTier?.(node.harnessTier)
      } else if (node.targetStepNumber) {
        onSelectTier?.(node.targetStepNumber)
      }
      if (node.targetStepNumber) {
        onSelectStep?.(node.targetStepNumber - 1)
      }
    }
  }, [onInspectNode, onSelectTier, onSelectStep])

  const handleCloseDrawer = useCallback(() => {
    setInspectedNodeId(null)
  }, [])

  // Close on Escape key, prevent background scroll and autofocus close button
  useEffect(() => {
    if (!inspectedNodeId) return

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseDrawer()
      }
    }
    window.addEventListener('keydown', handleKeyDown)

    const timer = setTimeout(() => {
      closeButtonRef.current?.focus()
    }, 50)

    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', handleKeyDown)
      clearTimeout(timer)
    }
  }, [inspectedNodeId, handleCloseDrawer])

  const activeNode = useMemo(() => {
    return inspectedNodeId ? DIAGRAM_NODES[inspectedNodeId as DiagramNodeId] ?? null : null
  }, [inspectedNodeId])

  const handleJumpToStep = useCallback((stepNumber: number) => {
    onSelectTier?.(stepNumber)
    onSelectStep?.(stepNumber - 1)
    handleCloseDrawer()
    const targetElement = document.querySelector('.harness-flow') || document.querySelector('.harness-flow-heading')
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [onSelectTier, onSelectStep, handleCloseDrawer])

  // Determine node active/highlight/dim classes according to view mode
  const getNodeClass = (nodeCategory: DiagramNodeCategory) => {
    if (mode === 'business') {
      if (nodeCategory === 'storage' || nodeCategory === 'stop') return 'is-standby'
      return 'is-active'
    }
    if (mode === 'safety') {
      if (nodeCategory === 'safety' || nodeCategory === 'stop') return 'is-highlighted is-safety'
      return 'is-dimmed'
    }
    if (mode === 'evidence') {
      if (nodeCategory === 'evidence' || nodeCategory === 'storage' || nodeCategory === 'output') return 'is-highlighted is-evidence'
      return 'is-dimmed'
    }
    return 'is-active'
  }

  return (
    <div className={`harness-diagram-card harness-diagram-card--${domainId}`} aria-label="Sơ đồ Kiến trúc 6 Tầng Chuẩn Tắc">
      {/* Header & Tri-mode perspective switcher */}
      <div className="harness-diagram-card__header">
        <div>
          <span className="harness-diagram-card__eyebrow">CANONICAL 6-HARNESS WORKFLOW · HD INTERACTIVE ARCHITECTURE</span>
          <h3 className="harness-diagram-card__title">Quy Trình Tác Tử 4 Giai Đoạn · Kiến Trúc 6 Tầng Chuẩn Doanh Nghiệp</h3>
          <p className="harness-diagram-card__subtitle">
            Nhấp vào bất kỳ ô nào để mở bảng <strong>Giải phẫu Công nghệ (Tech Anatomy)</strong>: Ẩn dụ đời thường, vai trò trong Veridra &amp; luồng 3 bước.
          </p>
        </div>

        <div className="harness-diagram-modes" role="tablist" aria-label="Chế độ xem sơ đồ">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'business'}
            className={`harness-diagram-modes__btn ${mode === 'business' ? 'is-active' : ''}`}
            onClick={() => handleModeSelect('business')}
          >
            <span className="harness-diagram-modes__indicator" />
            {MODE_DESCRIPTIONS.business.buttonLabel}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'safety'}
            className={`harness-diagram-modes__btn ${mode === 'safety' ? 'is-active is-safety' : ''}`}
            onClick={() => handleModeSelect('safety')}
          >
            <ShieldCheckmark16Regular />
            {MODE_DESCRIPTIONS.safety.buttonLabel}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'evidence'}
            className={`harness-diagram-modes__btn ${mode === 'evidence' ? 'is-active is-evidence' : ''}`}
            onClick={() => handleModeSelect('evidence')}
          >
            <DocumentCheckmark20Regular />
            {MODE_DESCRIPTIONS.evidence.buttonLabel}
          </button>
        </div>
      </div>

      {/* Perspective explanation banner */}
      <div className={`harness-diagram-banner harness-diagram-banner--${mode}`}>
        <strong>{modeInfo.title}:</strong> <span>{modeInfo.desc}</span>
      </div>

      {/* Canonical SVG 6-tier architecture canvas */}
      <div className="harness-diagram-viewport">
        <svg
          viewBox="0 0 1160 590"
          className="harness-diagram-svg"
          xmlns="http://www.w3.org/2000/svg"
          aria-label="Bản đồ trực quan 6 tầng Harness và 4 giai đoạn nghiệp vụ"
        >
          <defs>
            {/* Edge and Pulse Glow Gradients */}
            <linearGradient id="edgeGradMain" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--domain-primary, #10b981)" />
              <stop offset="100%" stopColor="var(--domain-accent, #34d399)" />
            </linearGradient>
            <linearGradient id="edgeGradSafety" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
            <linearGradient id="edgeGradEvidence" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>

            {/* Glowing Signal Cable Gradients */}
            <linearGradient id="pulseGlowMain" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#34d399" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="1" />
            </linearGradient>

            {/* Refined Border Gradients for each Harness Tier */}
            <linearGradient id="grad-tier-adk" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="grad-tier-context" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#2dd4bf" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="grad-tier-storage" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#0284c7" />
            </linearGradient>
            <linearGradient id="grad-tier-tools" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#fbbf24" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            <linearGradient id="grad-tier-orchestration" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            <linearGradient id="grad-tier-eval" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
            <linearGradient id="grad-tier-stop" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#fb7185" />
              <stop offset="100%" stopColor="#e11d48" />
            </linearGradient>
            <linearGradient id="grad-tier-intake" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#818cf8" />
            </linearGradient>
            <linearGradient id="grad-tier-final" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>

            {/* HD Marker Arrows */}
            <marker
              id="harnessArrow"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="rgba(148, 163, 184, 0.75)" />
            </marker>
            <marker
              id="harnessArrowSafety"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#f59e0b" />
            </marker>
            <marker
              id="harnessArrowEvidence"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 7 5 L 0 8.5 z" fill="#06b6d4" />
            </marker>
          </defs>

          {/* 4 Swimlanes Background: Clear Business Workflow Stages */}
          <g className="harness-swimlanes" aria-hidden="true">
            {/* Lane 1: Intake & Interface */}
            <rect x="20" y="16" width="1120" height="128" rx="12" className="harness-lane-bg" />
            <text x="36" y="36" className="harness-lane-title">
              LÀN 1 · GIAI ĐOẠN 1: TIẾP NHẬN YÊU CẦU (Trợ lý lắng nghe mục tiêu &amp; chuẩn hóa cờ lệnh)
            </text>

            {/* Lane 2: Orchestration & Delegation */}
            <rect x="20" y="156" width="1120" height="132" rx="12" className="harness-lane-bg" />
            <text x="36" y="174" className="harness-lane-title">
              LÀN 2 · GIAI ĐOẠN 2: ĐIỀU PHỐI TÁC TỬ (Trợ lý trưởng ADK giao việc cho chuyên viên AI)
            </text>

            {/* Lane 3: Context & Knowledge Storage */}
            <rect x="20" y="300" width="1120" height="132" rx="12" className="harness-lane-bg" />
            <text x="36" y="318" className="harness-lane-title">
              LÀN 3 · GIAI ĐOẠN 3: THU THẬP HỒ SƠ &amp; TRI THỨC (Ngăn kéo Qdrant &amp; Sổ cái SQLite WAL)
            </text>

            {/* Lane 4: Tool Execution & Quality Verification */}
            <rect x="20" y="444" width="1120" height="132" rx="12" className="harness-lane-bg" />
            <text x="36" y="462" className="harness-lane-title">
              LÀN 4 · GIAI ĐOẠN 4: XỬ LÝ CÔNG CỤ &amp; KIỂM DUYỆT BÁO CÁO (Phòng tính toán sandbox &amp; Thẩm định trích dẫn)
            </text>
          </g>

          {/* Edges & Pulse Signal Flow */}
          <g className="harness-edges">
            {/* User -> Hub */}
            <path d="M 276 89 L 312 89" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 276 89 L 312 89" className="harness-edge-pulse harness-pulse-main" />

            {/* Hub -> Tier 1 (ADK) */}
            <path d="M 452 132 L 452 186" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 452 132 L 452 186" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 1 (ADK) -> Tier 2 (Context) */}
            <path d="M 452 272 L 452 330" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 452 272 L 452 330" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 2 (Context) <-> Tier 3 (Storage) */}
            <path d="M 312 373 L 276 373" className="harness-edge-base" markerEnd="url(#harnessArrowEvidence)" />
            <path d="M 312 373 L 276 373" className="harness-edge-pulse harness-pulse-evidence" />

            {/* Tier 1 (ADK) -> Tier 5 (Orchestration) */}
            <path d="M 592 229 L 628 229" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 592 229 L 628 229" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 2 (Context) -> Tier 4 (Tools) */}
            <path d="M 452 416 L 452 474" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 452 416 L 452 474" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 4 (Tools) -> Tier 6 (Evaluation) */}
            <path d="M 592 517 L 628 517" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 592 517 L 628 517" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 5 (Orchestration) -> Tier 6 (Evaluation) */}
            <path d="M 768 272 L 768 474" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 768 272 L 768 474" className="harness-edge-pulse harness-pulse-main" />

            {/* Tier 6 -> Governed Output */}
            <path d="M 908 498 C 930 498, 930 373, 944 373" className="harness-edge-base" markerEnd="url(#harnessArrow)" />
            <path d="M 908 498 C 930 498, 930 373, 944 373" className="harness-edge-pulse harness-pulse-main" />

            {/* Safe Halt Gate: Tier 6 -> Safe Halt Gate */}
            <path d="M 908 517 L 944 517" className="harness-edge-base harness-edge--safety" markerEnd="url(#harnessArrowSafety)" />
            <path d="M 908 517 L 944 517" className="harness-edge-pulse harness-pulse-safety" />
          </g>

          {/* Clean, Minimalist Architecture Nodes (Keyword + Tag + Click Cue Only) */}
          <g className="harness-nodes">
            {/* LANE 1: USER PERSONA NODE */}
            <g
              className={`harness-node harness-node--intake ${getNodeClass('business')} ${
                inspectedNodeId === 'user-persona' ? 'is-inspecting' : ''
              }`}
              transform="translate(36, 46)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Doanh Nghiệp / User Persona"
              onClick={() => handleInspect('user-persona')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('user-persona') }}
            >
              <rect width="240" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-category">{nodeUser.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeUser.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 1: COMMAND HUB NODE */}
            <g
              className={`harness-node harness-node--intake ${getNodeClass('business')} ${
                inspectedNodeId === 'terminal-dispatcher' ? 'is-inspecting' : ''
              }`}
              transform="translate(312, 46)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Terminal Dispatcher"
              onClick={() => handleInspect('terminal-dispatcher')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('terminal-dispatcher') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-category">{nodeHub.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeHub.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 2: TIER 1 - ADK AGENT FRAMEWORK (SHARED MULTI-STAGE: THICK BORDER) */}
            <g
              className={`harness-node harness-node--tier harness-node--adk harness-node--shared ${getNodeClass('business')} ${
                inspectedNodeId === 'adk-coordinator' ? 'is-inspecting' : ''
              }`}
              transform="translate(312, 186)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết ADK Coordinator"
              onClick={() => handleInspect('adk-coordinator')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('adk-coordinator') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeAdk.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeAdk.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 2: TIER 5 - ORCHESTRATION HARNESS */}
            <g
              className={`harness-node harness-node--tier harness-node--orchestration ${getNodeClass('safety')} ${
                inspectedNodeId === 'orchestration-harness' ? 'is-inspecting' : ''
              }`}
              transform="translate(628, 186)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Multi-Agent DAG & HITL"
              onClick={() => handleInspect('orchestration-harness')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('orchestration-harness') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeOrch.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeOrch.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 3: TIER 3 - STORAGE (BACKGROUND INFRASTRUCTURE NODE) */}
            <g
              className={`harness-node harness-node--tier harness-node--storage ${getNodeClass('storage')} ${
                inspectedNodeId === 'storage-infra' ? 'is-inspecting' : ''
              }`}
              transform="translate(36, 330)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Qdrant & SQLite WAL"
              onClick={() => handleInspect('storage-infra')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('storage-infra') }}
            >
              <rect width="240" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeStorage.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeStorage.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 3: TIER 2 - CONTEXT HARNESS */}
            <g
              className={`harness-node harness-node--tier harness-node--context ${getNodeClass('evidence')} ${
                inspectedNodeId === 'context-harness' ? 'is-inspecting' : ''
              }`}
              transform="translate(312, 330)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Hybrid RAG & Memory"
              onClick={() => handleInspect('context-harness')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('context-harness') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeContext.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeContext.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 4: TIER 4 - TOOL HARNESS */}
            <g
              className={`harness-node harness-node--tier harness-node--tools ${getNodeClass('safety')} ${
                inspectedNodeId === 'tool-harness' ? 'is-inspecting' : ''
              }`}
              transform="translate(312, 474)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết 31 Tools & Sandbox"
              onClick={() => handleInspect('tool-harness')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('tool-harness') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeTools.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeTools.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* LANE 4: TIER 6 - EVALUATION HARNESS */}
            <g
              className={`harness-node harness-node--tier harness-node--eval ${getNodeClass('evidence')} ${
                inspectedNodeId === 'evaluation-harness' ? 'is-inspecting' : ''
              }`}
              transform="translate(628, 474)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Citation & Read-back"
              onClick={() => handleInspect('evaluation-harness')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('evaluation-harness') }}
            >
              <rect width="280" height="86" rx="12" className="harness-node-box" />
              <text x="16" y="24" className="harness-node-tier-tag">{nodeEval.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeEval.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* VERIFIED OUTPUT: GOVERNED OUTPUT (SHARED MULTI-STAGE: THICK BORDER) */}
            <g
              className={`harness-node harness-node--final harness-node--shared ${getNodeClass('output')} ${
                inspectedNodeId === 'governed-output' ? 'is-inspecting' : ''
              }`}
              transform="translate(944, 330)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Governed Output"
              onClick={() => handleInspect('governed-output')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('governed-output') }}
            >
              <rect width="196" height="86" rx="12" className="harness-node-box harness-node-box--final" />
              <text x="16" y="24" className="harness-node-category">{nodeOutput.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeOutput.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>

            {/* SAFE HALT GATE (DEFENSIVE SENTINEL: ACTIVATES ONLY ON EXCEPTION) */}
            <g
              className={`harness-node harness-node--stop ${getNodeClass('stop')} ${
                inspectedNodeId === 'safe-halt-gate' ? 'is-inspecting' : ''
              }`}
              transform="translate(944, 474)"
              role="button"
              tabIndex={0}
              aria-label="Xem chi tiết Safe Halt Gate"
              onClick={() => handleInspect('safe-halt-gate')}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleInspect('safe-halt-gate') }}
            >
              <rect width="196" height="86" rx="12" className="harness-node-box harness-node-box--stop" />
              <text x="16" y="24" className="harness-node-category">{nodeStop.tierTag}</text>
              <text x="16" y="47" className="harness-node-name">{nodeStop.name}</text>
              <g className="harness-node-pill" transform="translate(16, 58)">
                <rect width="82" height="18" rx="9" className="harness-pill-bg" />
                <text x="41" y="9" dominantBaseline="central" textAnchor="middle" className="harness-pill-text">↗ Chi tiết</text>
              </g>
            </g>
          </g>
        </svg>
      </div>

      {/* Footer Legend & Dimmed Node Clarification Callout */}
      <div className="harness-diagram-footer">
        <div className="harness-diagram-legend">
          <span><i className="legend-dot legend-dot--adk" /> ADK Điều phối</span>
          <span><i className="legend-dot legend-dot--context" /> Context Ngữ cảnh</span>
          <span><i className="legend-dot legend-dot--tools" /> Tool &amp; Sandbox</span>
          <span><i className="legend-dot legend-dot--eval" /> Evaluation Kiểm duyệt</span>
          <span><i className="legend-dot legend-dot--shared" /> ★ Thành phần liên giai đoạn (Viền đậm)</span>
          <span><i className="legend-dot legend-dot--gate" /> Chốt phòng vệ dừng an toàn</span>
        </div>

        {/* User-friendly Callout explaining why Qdrant & Safe Halt Gate are standby */}
        <div className="harness-diagram-note-box">
          <div className="harness-diagram-note-box__header">
            <Info20Regular aria-hidden="true" />
            <strong>Giải thích trạng thái ô hạ tầng ngầm &amp; chốt phòng vệ (Qdrant &amp; Safe Halt Gate):</strong>
          </div>
          <p className="harness-diagram-note-box__text">
            Ở chế độ mặc định, hai ô này có viền nét đứt và hiển thị ở chế độ nền <em>hoàn toàn không phải do lỗi hệ thống</em>. Đây là các <strong>thành phần hạ tầng ngầm &amp; phòng vệ dự phòng</strong>:
            {' '}<strong>Qdrant (Tầng 03)</strong> lưu vector cục bộ, nhưng các bước embedding hoặc gọi mô hình có thể truyền dữ liệu tới nhà cung cấp đã cấu hình; cần xem cấu hình và luồng xử lý thay vì suy ra rằng dữ liệu không rời máy;
            {' '}<strong>Safe Halt Gate</strong> minh họa các kiểm tra dừng hiện có theo từng luồng, không đảm bảo phát hiện mọi vi phạm quyền, sai số hoặc thiếu trích dẫn.
          </p>
        </div>
      </div>

      {/* ================================================================== */}
      {/* INTERACTIVE SIDE POP-UP / DRAWER ON NODE CLICK                     */}
      {/* ================================================================== */}
      {activeNode && (
        <>
          <div
            className="diagram-drawer-backdrop"
            onClick={handleCloseDrawer}
            aria-hidden="true"
          />
          <aside
            className="diagram-node-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="diagram-drawer-title"
            aria-describedby="diagram-drawer-subtitle"
            style={{ ['--node-theme' as string]: activeNode.color }}
          >
            {/* Drawer Header */}
            <header className="diagram-drawer-header">
              <div className="diagram-drawer-header__main">
                <span className="diagram-drawer-header__badge">
                  {getNodeIcon(activeNode.id)}
                  <span>{activeNode.tierTag}</span>
                </span>
                <h3 id="diagram-drawer-title" className="diagram-drawer-header__title">
                  {activeNode.name}
                </h3>
                <p id="diagram-drawer-subtitle" className="diagram-drawer-header__tech">
                  {activeNode.techKeyword}
                </p>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                className="diagram-drawer-close-btn"
                onClick={handleCloseDrawer}
                aria-label="Đóng cửa sổ giải phẫu"
                title="Đóng (Esc)"
              >
                <Dismiss20Regular aria-hidden="true" />
              </button>
            </header>

            {/* Drawer Body Content */}
            <div className="diagram-drawer-body">
              {/* Card 1: Plain English Assistant Metaphor */}
              <article className="diagram-drawer-card diagram-drawer-card--metaphor">
                <div className="diagram-drawer-card__header">
                  <div className="diagram-drawer-card__icon-box diagram-drawer-card__icon-box--metaphor">
                    <Sparkle20Regular aria-hidden="true" />
                  </div>
                  <div>
                    <span className="diagram-drawer-card__tag">TÓM GỌN · DỄ HIỂU</span>
                    <h4 className="diagram-drawer-card__heading">Ẩn dụ trợ lý đời thường</h4>
                  </div>
                </div>
                <p className="diagram-drawer-card__text">{activeNode.metaphor}</p>
                <div className="diagram-drawer-card__footer">
                  <CheckmarkCircle20Regular aria-hidden="true" />
                  <span>Diễn giải trực quan, loại bỏ hoàn toàn thuật ngữ hàn lâm khó hiểu</span>
                </div>
              </article>

              {/* Card 2: Mission & Safety Guardrails */}
              <article className="diagram-drawer-card diagram-drawer-card--role">
                <div className="diagram-drawer-card__header">
                  <div className="diagram-drawer-card__icon-box diagram-drawer-card__icon-box--role">
                    <ShieldCheckmark20Regular aria-hidden="true" />
                  </div>
                  <div>
                    <span className="diagram-drawer-card__tag">SỨ MỆNH HỆ THỐNG</span>
                    <h4 className="diagram-drawer-card__heading">Vai trò Veridra &amp; Rào cản an toàn</h4>
                  </div>
                </div>
                <p className="diagram-drawer-card__text">{activeNode.driveAgentRole}</p>
                <div className="diagram-drawer-card__footer">
                  <LockClosed20Regular aria-hidden="true" />
                  <span>Phân quyền RBAC · Audit có thể đối chiếu · Không phải chứng nhận Zero Trust</span>
                </div>
              </article>

              {/* Card 3: 3-Step Mini Anatomy Diagram */}
              <article className="diagram-drawer-card diagram-drawer-card--anatomy">
                <div className="diagram-drawer-card__header">
                  <div className="diagram-drawer-card__icon-box diagram-drawer-card__icon-box--anatomy">
                    <Flowchart20Regular aria-hidden="true" />
                  </div>
                  <div>
                    <span className="diagram-drawer-card__tag">SƠ ĐỒ MINI-ANATOMY</span>
                    <h4 className="diagram-drawer-card__heading">Giải phẫu chu trình 3 bước</h4>
                  </div>
                </div>

                <div className="diagram-drawer-steps">
                  {/* Step 1: Trigger */}
                  <div className="diagram-drawer-step diagram-drawer-step--trigger">
                    <div className="diagram-drawer-step__badge">
                      <span className="diagram-drawer-step__num">01</span>
                      <Play20Regular className="diagram-drawer-step__icon" aria-hidden="true" />
                    </div>
                    <div className="diagram-drawer-step__info">
                      <strong>KÍCH HOẠT (Trigger)</strong>
                      <p>{activeNode.anatomy[0].replace(/^Kích hoạt:\s*/i, '')}</p>
                    </div>
                  </div>

                  <div className="diagram-drawer-connector" aria-hidden="true">
                    <ArrowRight20Regular />
                  </div>

                  {/* Step 2: Control */}
                  <div className="diagram-drawer-step diagram-drawer-step--control">
                    <div className="diagram-drawer-step__badge">
                      <span className="diagram-drawer-step__num">02</span>
                      <LockClosed20Regular className="diagram-drawer-step__icon" aria-hidden="true" />
                    </div>
                    <div className="diagram-drawer-step__info">
                      <strong>KIỂM SOÁT (Control &amp; Gate)</strong>
                      <p>{activeNode.anatomy[1].replace(/^Kiểm soát:\s*/i, '')}</p>
                    </div>
                  </div>

                  <div className="diagram-drawer-connector" aria-hidden="true">
                    <ArrowRight20Regular />
                  </div>

                  {/* Step 3: Output */}
                  <div className="diagram-drawer-step diagram-drawer-step--output">
                    <div className="diagram-drawer-step__badge">
                      <span className="diagram-drawer-step__num">03</span>
                      <DocumentCheckmark20Regular className="diagram-drawer-step__icon" aria-hidden="true" />
                    </div>
                    <div className="diagram-drawer-step__info">
                      <strong>XUẤT KẾT QUẢ (Output &amp; Audit)</strong>
                      <p>{activeNode.anatomy[2].replace(/^Xuất kết quả:\s*/i, '')}</p>
                    </div>
                  </div>
                </div>
              </article>

              {/* Card 4: Domain Spotlight Context */}
              <article className="diagram-drawer-card diagram-drawer-card--domain">
                <div className="diagram-drawer-card__header">
                  <div className="diagram-drawer-card__icon-box diagram-drawer-card__icon-box--domain">
                    <CheckmarkCircle20Regular aria-hidden="true" />
                  </div>
                  <div>
                    <span className="diagram-drawer-card__tag">ÁP DỤNG THỰC TẾ · DOMAIN {domainId.toUpperCase()}</span>
                    <h4 className="diagram-drawer-card__heading">Hành vi cụ thể trong tình huống hiện tại</h4>
                  </div>
                </div>
                <p className="diagram-drawer-card__text">
                  {activeNode.domainHighlights[domainId] || activeNode.domainHighlights.banking}
                </p>
              </article>
            </div>

            {/* Drawer Footer Actions */}
            <footer className="diagram-drawer-footer">
              <button
                type="button"
                className="diagram-drawer-jump-btn"
                onClick={() => handleJumpToStep(activeNode.targetStepNumber)}
              >
                <span>Xem bước thực thi tương ứng ({activeNode.targetStepTitle})</span>
                <Open20Regular aria-hidden="true" />
              </button>

              <button
                type="button"
                className="diagram-drawer-close-secondary-btn"
                onClick={handleCloseDrawer}
              >
                Đóng
              </button>
            </footer>
          </aside>
        </>
      )}
    </div>
  )
}
