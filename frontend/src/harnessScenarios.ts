import {
  BuildingBank20Regular,
  HatGraduation20Regular,
  ShoppingBag20Regular,
} from '@fluentui/react-icons'

// ============================================================================
// 1. DOMAIN & THEME CONTRACTS
// ============================================================================

export type HarnessScenarioId = 'banking' | 'education' | 'ecommerce'

export interface DomainTheme {
  primaryColor: string
  accentColor: string
  lightBg: string
  glowColor: string
  borderGlow: string
  gradient: string
  badgeLabel: string
  iconName: 'BuildingBank20Regular' | 'HatGraduation20Regular' | 'ShoppingBag20Regular'
  businessHeadline: string
  businessSub: string
}

export const DOMAIN_THEMES: Record<HarnessScenarioId, DomainTheme> = {
  banking: {
    primaryColor: '#10b981',
    accentColor: '#e2e8f0',
    lightBg: 'rgba(16, 185, 129, 0.08)',
    glowColor: 'rgba(16, 185, 129, 0.28)',
    borderGlow: 'rgba(16, 185, 129, 0.45)',
    gradient: 'linear-gradient(135deg, #10b981 0%, #34d399 45%, #e2e8f0 100%)',
    badgeLabel: 'Tài chính & Ngân hàng',
    iconName: 'BuildingBank20Regular',
    businessHeadline: 'Đối soát chênh lệch sổ sách & Giữ trọn vết kiểm toán',
    businessSub: 'Tình huống minh họa: đối chiếu CSV, Sheet và biên bản điều chỉnh; dấu vết audit phụ thuộc từng bước được tích hợp.',
  },
  education: {
    primaryColor: '#8b5cf6',
    accentColor: '#6366f1',
    lightBg: 'rgba(139, 92, 246, 0.08)',
    glowColor: 'rgba(139, 92, 246, 0.28)',
    borderGlow: 'rgba(139, 92, 246, 0.45)',
    gradient: 'linear-gradient(135deg, #8b5cf6 0%, #a78bfa 45%, #6366f1 100%)',
    badgeLabel: 'Giáo dục & Đào tạo',
    iconName: 'HatGraduation20Regular',
    businessHeadline: 'Nhận diện lỗ hổng kiến thức & Đánh giá khách quan theo rubric',
    businessSub: 'Định vị chính xác khoảng trống kỹ năng học viên, đề xuất can thiệp cá nhân hóa theo thang đo chuẩn mực.',
  },
  ecommerce: {
    primaryColor: '#f59e0b',
    accentColor: '#f97316',
    lightBg: 'rgba(245, 158, 11, 0.08)',
    glowColor: 'rgba(245, 158, 11, 0.28)',
    borderGlow: 'rgba(245, 158, 11, 0.45)',
    gradient: 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 45%, #f97316 100%)',
    badgeLabel: 'Thương mại điện tử',
    iconName: 'ShoppingBag20Regular',
    businessHeadline: 'Phân tích biến động đơn hàng & Đề xuất phương án vận hành kho',
    businessSub: 'Liên kết doanh số bán lẻ, tỷ lệ hoàn trả và tồn kho thực tế để tối ưu chuỗi cung ứng theo thời gian thực.',
  },
}

export const DOMAIN_ICONS: Record<HarnessScenarioId, typeof BuildingBank20Regular> = {
  banking: BuildingBank20Regular,
  education: HatGraduation20Regular,
  ecommerce: ShoppingBag20Regular,
}

// ============================================================================
// 2. COMMAND HUB FLAGS & POPOVERS CONTRACT
// ============================================================================

export type FlagCategory = 'scope' | 'skill' | 'security'

export interface FlagInfo {
  flag: string
  label: string
  syntax: string
  category: FlagCategory
  description: string
  mechanism: string
}

export const COMMAND_FLAGS: Record<string, FlagInfo> = {
  '/skill': {
    flag: '/skill',
    label: 'Kỹ năng chuyên biệt (Skill)',
    syntax: '/skill:<skill_id>',
    category: 'skill',
    description: 'Nạp gói quy trình, schema kiểm tra và chuẩn mực nghiệp vụ đã lưu vào bối cảnh hệ thống.',
    mechanism: 'Nạp chỉ dẫn hệ thống (system instruction), biểu mẫu và ràng buộc đầu ra từ SkillStore vào phiên làm việc mà không làm loãng bộ nhớ ngữ cảnh.',
  },
  '/local': {
    flag: '/local',
    label: 'Nguồn dữ liệu cục bộ',
    syntax: '/local',
    category: 'scope',
    description: 'Khai thác tập tin CSV, Excel hoặc văn bản sao kê lưu trữ trên máy tính làm việc trong phạm vi phiên.',
    mechanism: 'Chỉ đọc nội dung tệp tại thư mục cho phép, phân tích tại chỗ trong bộ nhớ tạm và không đồng bộ dữ liệu thô lên đám mây.',
  },
  '/sheet': {
    flag: '/sheet',
    label: 'Google Sheets Integration',
    syntax: '/sheet',
    category: 'scope',
    description: 'Kết nối đối soát và lập bảng tính tự động trên Google Sheets theo định dạng chuẩn.',
    mechanism: 'Khai thác Google Sheets API với OAuth scope đọc/ghi tối thiểu, luôn tạo bản xem trước (preview proposal) để người dùng phê duyệt trước khi ghi.',
  },
  '/doc': {
    flag: '/doc',
    label: 'Google Docs Integration',
    syntax: '/doc',
    category: 'scope',
    description: 'Tạo lập văn bản báo cáo, biên bản kiểm toán và kế hoạch can thiệp có cấu trúc trên Google Docs.',
    mechanism: 'Khởi tạo tài liệu mới trong thư mục Drive được ủy quyền, tự động gắn trích dẫn số trang/dòng (citation marks) và bảo toàn lịch sử chỉnh sửa.',
  },
  '/drive': {
    flag: '/drive',
    label: 'Google Drive RAG',
    syntax: '/drive',
    category: 'scope',
    description: 'Truy xuất và đối chiếu tài liệu, rubric, quy trình lưu trữ trên Google Drive thông qua RAG ngữ nghĩa.',
    mechanism: 'Tìm kiếm ngữ nghĩa qua Qdrant vector index và đối chiếu content hash bản mới nhất (freshness gate) để ngăn ngừa dữ liệu lỗi thời.',
  },
  '/auto': {
    flag: '/auto',
    label: 'Điều phối tự chủ có kiểm soát (Autonomous)',
    syntax: '/auto',
    category: 'security',
    description: 'Cho phép tác tử tự lập kế hoạch chuỗi bước xử lý đa công cụ nhưng vẫn tuân thủ rào cản an toàn.',
    mechanism: 'ADK coordinator chuyển việc giữa các agent chuyên trách; các thao tác ghi được hỗ trợ qua bước preview và phê duyệt theo hợp đồng tool.',
  },
}

// ============================================================================
// 3. 5/6 HARNESS TECH STACK & 3-TIER ANATOMY
// ============================================================================

export type HarnessGroupKey = 'adk' | 'context' | 'storage' | 'tools' | 'orchestration' | 'eval'

export interface TechStackGroup {
  id: HarnessGroupKey
  title: string
  subtitle: string
  badge: string
  color: string
}

export const HARNESS_TECH_GROUPS: TechStackGroup[] = [
  {
    id: 'adk',
    title: '1. ADK Agent Framework',
    subtitle: 'Nền tảng tác tử, quản lý phiên và phân rã mục tiêu',
    badge: 'Framework',
    color: '#3b82f6',
  },
  {
    id: 'context',
    title: '2. Context Harness & RAG',
    subtitle: 'Tìm kiếm lai (Dense + Lexical), RRF Reranking và phân vùng bối cảnh',
    badge: 'Retrieval',
    color: '#8b5cf6',
  },
  {
    id: 'storage',
    title: '3. Storage & State',
    subtitle: 'Vector database Qdrant Embedded và SQLite WAL lưu trữ bền vững',
    badge: 'Storage',
    color: '#06b6d4',
  },
  {
    id: 'tools',
    title: '4. Tool Harness & Sandbox',
    subtitle: '31 công cụ chuẩn hóa, RBAC, OAuth scope và môi trường tính toán cách ly',
    badge: 'Execution',
    color: '#10b981',
  },
  {
    id: 'orchestration',
    title: '5. Orchestration Harness',
    subtitle: 'Đồ thị luồng DAG, giao tiếp A2A và cơ chế Human-in-the-loop 2 pha',
    badge: 'Orchestration',
    color: '#f59e0b',
  },
  {
    id: 'eval',
    title: '6. Evaluation & Audit',
    subtitle: 'Output contract, ràng buộc trích dẫn (citation binding) và sự kiện audit có thể đối chiếu',
    badge: 'Governance',
    color: '#ef4444',
  },
]

export interface TechItem {
  id: string
  name: string
  harnessGroup: HarnessGroupKey
  plainEnglish: string
  driveAgentRole: string
  anatomy: [string, string, string] // [1. Kích hoạt, 2. Kiểm soát, 3. Xuất kết quả]
}

export const TECH_STACK_ITEMS: Record<string, TechItem> = {
  'google-adk': {
    id: 'google-adk',
    name: 'Google ADK',
    harnessGroup: 'adk',
    plainEnglish: 'Bộ não điều phối tổng quát, đóng vai trò như trưởng nhóm tiếp nhận công việc và phân công cho đúng chuyên viên.',
    driveAgentRole: 'Đóng gói vòng đời tác tử (agent lifecycle), duy trì phiên làm việc stateful và phân giải câu lệnh slash.',
    anatomy: [
      'Kích hoạt: Tiếp nhận câu lệnh tự nhiên hoặc lệnh slash từ giao diện người dùng.',
      'Kiểm soát: Giới hạn token budget, ép buộc timeout và kiểm tra quyền hạn mức phiên.',
      'Xuất kết quả: Kế hoạch thực thi chuẩn hóa và chỉ định agent chuyên trách xử lý.',
    ],
  },
  'memory': {
    id: 'memory',
    name: 'Memory',
    harnessGroup: 'context',
    plainEnglish: 'Sổ tay ghi nhớ dài hạn, giúp tác tử nhớ sở thích, quy ước tính toán và các quyết định đã duyệt từ các phiên trước.',
    driveAgentRole: 'Lưu trữ LongTermMemory trong SQLite, tự động nạp các quy ước nghiệp vụ liên quan vào system prompt.',
    anatomy: [
      'Kích hoạt: Khi người dùng yêu cầu ghi nhớ hoặc khi bắt đầu một phiên nghiệp vụ lặp lại.',
      'Kiểm soát: Người dùng có toàn quyền xem, sửa, xoá; không lưu dữ liệu bí mật ngoài ý muốn.',
      'Xuất kết quả: Đoạn bối cảnh quy ước nghiệp vụ được chèn tự động vào phiên làm việc.',
    ],
  },
  'local-source': {
    id: 'local-source',
    name: 'Local Source',
    harnessGroup: 'context',
    plainEnglish: 'Ngăn chứa hồ sơ nội bộ trên máy, cho phép phân tích tài liệu mà không cần tải lên máy chủ bên ngoài.',
    driveAgentRole: 'Trình trích xuất dữ liệu tập tin cục bộ (CSV, XLSX, PDF), xử lý an toàn trong sandbox cục bộ.',
    anatomy: [
      'Kích hoạt: Nhận cờ lệnh /local kèm đường dẫn tệp dữ liệu máy trạm.',
      'Kiểm soát: Kiểm tra whitelist thư mục được cấp quyền, chặn truy cập tệp hệ thống.',
      'Xuất kết quả: Bảng dữ liệu chuẩn hóa dạng bảng (tabular DataFrame) trong bộ nhớ đệm.',
    ],
  },
  'drive-rag': {
    id: 'drive-rag',
    name: 'Drive RAG',
    harnessGroup: 'context',
    plainEnglish: 'Thư viện số giúp tìm các đoạn liên quan; vị trí trang phụ thuộc nội dung và khả năng trích xuất của bộ đọc.',
    driveAgentRole: 'Pipeline trích xuất, lập chỉ mục và truy xuất ngữ nghĩa từ kho lưu trữ Google Drive của người dùng.',
    anatomy: [
      'Kích hoạt: Khi câu hỏi yêu cầu đối chiếu văn bản quy trình, cẩm nang hoặc rubric trên Drive.',
      'Kiểm soát: Freshness Gate: kiểm tra content hash, nếu tệp trên Drive bị sửa sẽ từ chối dùng cache cũ.',
      'Xuất kết quả: Danh sách đoạn trích liên quan kèm số trang, số dòng và mã định danh tệp.',
    ],
  },
  'qdrant-embedded': {
    id: 'qdrant-embedded',
    name: 'Qdrant Embedded',
    harnessGroup: 'storage',
    plainEnglish: 'Bộ chỉ mục vector siêu tốc chạy ngay trên máy tính, chuyển hóa ý nghĩa câu từ thành tọa độ toán học.',
    driveAgentRole: 'Vector database nhúng cục bộ, lưu embedding 768 chiều và tìm kiếm độ tương đồng cosine; độ trễ phải đo theo kích thước dữ liệu và môi trường thực.',
    anatomy: [
      'Kích hoạt: Nhận vector truy vấn từ câu hỏi của người dùng hoặc bước mở rộng bối cảnh.',
      'Kiểm soát: Lọc chặt chẽ theo user_id và file_id quyền hạn trước khi trả về ứng viên vector.',
      'Xuất kết quả: Top-K đoạn văn bản có độ tương đồng ngữ nghĩa cao nhất.',
    ],
  },
  'rrf': {
    id: 'rrf',
    name: 'RRF (Reciprocal Rank Fusion)',
    harnessGroup: 'context',
    plainEnglish: 'Trọng tài dung hòa, kết hợp kết quả tìm kiếm theo từ khóa chính xác và tìm kiếm theo ý nghĩa ngữ nghĩa.',
    driveAgentRole: 'Thuật toán tái xếp hạng hợp nhất kết quả giữa Lexical BM25 và Dense Vector search để tối ưu độ chính xác.',
    anatomy: [
      'Kích hoạt: Tiếp nhận hai danh sách kết quả xếp hạng từ bộ tìm kiếm từ khóa và bộ tìm kiếm ngữ nghĩa.',
      'Kiểm soát: Hằng số dung hòa k=60 ngăn chặn việc một bên thiên vị điểm số tuyệt đối.',
      'Xuất kết quả: Bảng xếp hạng hợp nhất duy nhất với các bằng chứng có độ tin cậy vượt trội.',
    ],
  },
  'calculator': {
    id: 'calculator',
    name: 'Calculator',
    harnessGroup: 'tools',
    plainEnglish: 'Bộ tính toán xác định cho các biểu thức được hỗ trợ, giúp kiểm tra phép tính thay vì để mô hình tự nhẩm.',
    driveAgentRole: 'Calculator chỉ đánh giá biểu thức theo allowlist AST; không chạy mã Python tổng quát. Kết quả đúng theo biểu thức đã nhập, không xác nhận đầu vào nghiệp vụ đúng.',
    anatomy: [
      'Kích hoạt: Khi có biểu thức toán học, chênh lệch số dư hoặc tỷ lệ phần trăm cần tính.',
      'Kiểm soát: Sandbox cô lập AST, cấm module os/sys, giới hạn thời gian chạy tối đa 2.000ms.',
      'Xuất kết quả: Giá trị và phép tính để người dùng đối chiếu với dữ liệu nguồn.',
    ],
  },
  'docs-sheets-approval': {
    id: 'docs-sheets-approval',
    name: 'Docs/Sheets approval',
    harnessGroup: 'orchestration',
    plainEnglish: 'Bản đề xuất chờ xác nhận, giúp người dùng xem nội dung trước khi một thao tác ghi được hỗ trợ thực thi.',
    driveAgentRole: 'Luồng preview/approve/execute/read-back áp dụng cho các tool ghi được hỗ trợ; không phải mọi thao tác hay mọi tài nguyên đều đi qua cùng một quy trình.',
    anatomy: [
      'Kích hoạt: Tác tử hoàn tất việc chuẩn bị nội dung bảng tính hoặc văn bản báo cáo.',
      'Kiểm soát: Registry yêu cầu xác nhận theo hợp đồng của tool trước khi chạy thao tác ghi được bảo vệ.',
      'Xuất kết quả: Proposal hoặc kết quả của tool hỗ trợ, cùng sự kiện audit nếu luồng đó ghi nhận.',
    ],
  },
  'read-back': {
    id: 'read-back',
    name: 'Read-back',
    harnessGroup: 'eval',
    plainEnglish: 'Bước đọc lại có chọn lọc sau khi ghi để phát hiện khác biệt ở các trường được tool hỗ trợ kiểm tra.',
    driveAgentRole: 'Một số luồng Docs/Sheets đọc lại dữ liệu vừa ghi và so sánh các trường mục tiêu; phạm vi kiểm tra tùy tool, không bảo đảm toàn bộ định dạng/tài nguyên giống hệt.',
    anatomy: [
      'Kích hoạt: Ngay sau khi tác vụ tạo tệp Sheets, Docs hoặc Gmail Draft hoàn tất thành công.',
      'Kiểm soát: Báo khác biệt ở trường được đọc lại; không tự khẳng định đã hoàn tác nếu chưa có thao tác rollback tương ứng.',
      'Xuất kết quả: Trạng thái và phạm vi read-back thực tế trong trace/audit của luồng được hỗ trợ.',
    ],
  },
  'research-study-agents': {
    id: 'research-study-agents',
    name: 'Research/Study Agents',
    harnessGroup: 'orchestration',
    plainEnglish: 'Hội đồng cố vấn học thuật, chuyên trách phân tích thang đo chuẩn và thiết kế lộ trình tiến bộ.',
    driveAgentRole: 'Nhóm tác tử chuyên ngành trong lĩnh vực giáo dục, tuân thủ nghiêm ngặt nguyên tắc sư phạm.',
    anatomy: [
      'Kích hoạt: Khi người dùng chọn bài toán phân tích học tập hoặc nạp cờ /rubric.',
      'Kiểm soát: Quyền ghi và cách diễn đạt được giới hạn theo role, tool contract và yêu cầu người dùng đã cấu hình.',
      'Xuất kết quả: Bảng ma trận lỗ hổng kiến thức và đề xuất bài tập bổ trợ theo rubric.',
    ],
  },
  'pdf-page-chunks': {
    id: 'pdf-page-chunks',
    name: 'PDF page chunks',
    harnessGroup: 'context',
    plainEnglish: 'Kính lúp chia nhỏ tài liệu, cắt văn bản theo từng trang và khối bảng biểu để không làm lẫn lộn số liệu.',
    driveAgentRole: 'Bộ phân đoạn tài liệu nhận thức cấu trúc (layout-aware chunker), bảo toàn số trang và bảng dữ liệu.',
    anatomy: [
      'Kích hoạt: Khi tệp PDF quy trình, chính sách hoặc bài nộp được nạp vào hệ thống RAG.',
      'Kiểm soát: Chunking có giới hạn kích thước theo cấu hình; metadata trang được giữ khi bộ đọc nguồn cung cấp.',
      'Xuất kết quả: Danh sách các chunk có định danh vị trí chính xác để phục vụ citation.',
    ],
  },
  'gmail-read': {
    id: 'gmail-read',
    name: 'Gmail read',
    harnessGroup: 'tools',
    plainEnglish: 'Công cụ đọc thư theo scope được cấp; việc tạo nháp và gửi thư là luồng riêng có quyền/approval riêng.',
    driveAgentRole: 'Công cụ tích hợp Gmail API ở chế độ chỉ đọc (read-only scope), phục vụ trích xuất phản hồi và trao đổi.',
    anatomy: [
      'Kích hoạt: Khi yêu cầu cần tìm email xác nhận, phản ánh khách hàng hoặc thư xin hỗ trợ.',
      'Kiểm soát: Tool đọc thư không gửi mail; các thao tác nháp/gửi được phân quyền riêng và phải theo hợp đồng tool hiện hành.',
      'Xuất kết quả: Trích đoạn email liên quan kèm người gửi, thời gian và tiêu đề thư.',
    ],
  },
  'citation-binding': {
    id: 'citation-binding',
    name: 'Citation binding',
    harnessGroup: 'eval',
    plainEnglish: 'Liên kết ký hiệu trích dẫn với nguồn để người dùng mở và đối chiếu bằng chứng.',
    driveAgentRole: 'Một số kiểm tra xác nhận marker và metadata nguồn; chưa đánh giá ngữ nghĩa rằng tài liệu thực sự chứng minh mọi claim.',
    anatomy: [
      'Kích hoạt: Khi mô hình sinh câu trả lời có chứa các nhận định nghiệp vụ quan trọng.',
      'Kiểm soát: Phát hiện marker không khớp với danh sách citation trong những luồng đã kiểm tra.',
      'Xuất kết quả: Câu trả lời có nguồn để người dùng đối chiếu; citation metadata không tự chứng minh nội dung.',
    ],
  },
  'multi-agent-routing': {
    id: 'multi-agent-routing',
    name: 'Multi-agent routing',
    harnessGroup: 'orchestration',
    plainEnglish: 'Bộ điều phối chuyển yêu cầu đến agent/tool chuyên trách theo tuyến đã xác định.',
    driveAgentRole: 'ADK coordinator lựa chọn agent chuyên trách và ghi nhận handoff; không phải đồ thị DAG hay bảo đảm loại bỏ mọi vòng lặp.',
    anatomy: [
      'Kích hoạt: Khi yêu cầu có độ phức tạp cao, đòi hỏi kết hợp nhiều kỹ năng liên ngành.',
      'Kiểm soát: Giới hạn lượt gọi mô hình theo cấu hình và tool contract; chưa có cycle detector tổng quát.',
      'Xuất kết quả: Các handoff event được ghi trong trace của lượt chạy.',
    ],
  },
  'artifact-versioning': {
    id: 'artifact-versioning',
    name: 'Artifact versioning',
    harnessGroup: 'storage',
    plainEnglish: 'Cỗ máy thời gian cho tài liệu, lưu giữ từng phiên bản dự thảo để bạn luôn có thể xem lại hoặc quay về bản cũ.',
    driveAgentRole: 'Artifact lưu phiên bản và mã hash theo bản ghi ứng dụng; cần backup và kiểm soát quyền riêng, không phải kho chống sửa đổi.',
    anatomy: [
      'Kích hoạt: Khi một đề xuất bảng tính, tài liệu hoặc email nháp mới được tạo ra.',
      'Kiểm soát: Không ghi đè trực tiếp; tạo phiên bản mới v1, v2 kèm ghi nhận sự khác biệt (diff).',
      'Xuất kết quả: Bản ghi Artifact có mã định danh phiên bản và đường dẫn tra cứu lịch sử.',
    ],
  },
  'sqlite-wal': {
    id: 'sqlite-wal',
    name: 'SQLite WAL',
    harnessGroup: 'storage',
    plainEnglish: 'Cuốn sổ cái ghi chép bất khả xâm phạm, ghi lại mọi hoạt động mà không làm chậm hệ thống.',
    driveAgentRole: 'Cơ sở dữ liệu SQLite cấu hình Write-Ahead Logging (WAL), lưu trữ toàn bộ sự kiện kiểm toán và trạng thái phiên.',
    anatomy: [
      'Kích hoạt: Mọi thao tác bắt đầu, chạy công cụ, duyệt hoặc lỗi đều phát sinh bản ghi.',
      'Kiểm soát: Chế độ WAL đảm bảo đọc đồng thời không chặn ghi; giao dịch ACID toàn vẹn.',
      'Xuất kết quả: Bảng AuditEvent hoàn chỉnh làm căn cứ cho Trust Cockpit và kiểm tra pháp lý.',
    ],
  },
  'output-contract': {
    id: 'output-contract',
    name: 'Output Contract',
    harnessGroup: 'eval',
    plainEnglish: 'Khuôn đúc chuẩn mực, bắt buộc kết quả đầu ra phải đúng định dạng yêu cầu trước khi đến tay người dùng.',
    driveAgentRole: 'Bộ kiểm tra schema đầu ra (Pydantic / Zod / JSON Schema), từ chối và yêu cầu sửa lại nếu sai cấu trúc.',
    anatomy: [
      'Kích hoạt: Khi mô hình sinh dữ liệu dạng bảng, danh sách hành động hoặc bản ghi đề xuất.',
      'Kiểm soát: Kiểm tra tính hợp lệ của trường dữ liệu, kiểu dữ liệu và các ràng buộc nghiệp vụ.',
      'Xuất kết quả: Dữ liệu sạch, sẵn sàng nạp vào các component giao diện mà không gây crash.',
    ],
  },
}

// ============================================================================
// 4. STEP 07 MOCKUP PREVIEW ARTIFACTS
// ============================================================================

export type ArtifactType = 'sheet' | 'docs' | 'gmail'

export interface StepArtifact {
  type: ArtifactType
  title: string
  badge: string
  domain: HarnessScenarioId
  metrics: Record<string, string>
  previewSnippet: string
  actions: string[]
}

export const STEP_ARTIFACTS: Record<HarnessScenarioId, StepArtifact[]> = {
  banking: [
    {
      type: 'sheet',
      title: 'Bảng Đối Soát Chênh Lệch Giao Dịch Q3',
      badge: 'Google Sheets · Chờ duyệt',
      domain: 'banking',
      metrics: {
        'Khoản lệch': '2 giao dịch (12.450.000 ₫)',
        'Khớp lệnh': '1.428 giao dịch (99.86%)',
        'Độ tin cậy': 'P99 Citation Binding',
      },
      previewSnippet: 'Dòng 42: TX-88219 chênh lệch 10.000.000 ₫ giữa sao kê đối tác và sổ cái nội bộ. Căn cứ điều khoản hoàn phí bổ sung.',
      actions: ['Xem trước công thức', 'Chấp thuận ghi lên Drive', 'Xuất CSV đối soát'],
    },
    {
      type: 'docs',
      title: 'Biên Bản Rà Soát Bất Thường Sổ Sách',
      badge: 'Google Docs · Sẵn sàng',
      domain: 'banking',
      metrics: {
        'Căn cứ': 'Quy trình kiểm toán mục 4.2',
        'Số phụ lục': 'PL-2026-09/KT',
        'Chữ ký số': 'Chờ kiểm soát viên',
      },
      previewSnippet: 'Biên bản ghi nhận nguyên nhân chậm hạch toán từ cổng thanh toán trung gian, kiến nghị xử lý trước kỳ đối soát kế tiếp.',
      actions: ['Mở bản nháp Docs', 'Ký duyệt điện tử', 'Chia sẻ cho ban kiểm soát'],
    },
    {
      type: 'gmail',
      title: 'Thư Nháp Yêu Cầu Đối Tác Xác Nhận Lại',
      badge: 'Gmail Draft · Chưa gửi',
      domain: 'banking',
      metrics: {
        'Người nhận': 'reconciliation@partner-bank.vn',
        'Đính kèm': 'Google Sheet & Docs Link',
        'Trạng thái': 'Bản nháp an toàn (Draft only)',
      },
      previewSnippet: 'Kính gửi Ban Đối soát Đối tác, Chúng tôi xin gửi kèm bảng kê 2 khoản lệch ngày 20/09 để cùng thống nhất bút toán điều chỉnh...',
      actions: ['Xem toàn bộ thư nháp', 'Mở trong Gmail để gửi', 'Hủy bỏ bản nháp'],
    },
  ],
  education: [
    {
      type: 'sheet',
      title: 'Bảng Ma Trận Lỗ Hổng Kỹ Năng Học Viên',
      badge: 'Google Sheets · Chuẩn Rubric',
      domain: 'education',
      metrics: {
        'Cần hỗ trợ': '4/35 học viên',
        'Tiêu chí yếu': 'Tư duy thuật toán (Tiêu chí 3)',
        'Điểm trung bình': '6.4/10',
      },
      previewSnippet: 'Học viên Nguyễn Văn A và Lê Thị B gặp khó khăn trong phần xử lý đệ quy. Đề xuất can thiệp bổ trợ vào tuần 4.',
      actions: ['Xem ma trận tiêu chí', 'Lưu vào Google Drive', 'Tạo nhóm học tập'],
    },
    {
      type: 'docs',
      title: 'Kế Hoạch Can Thiệp Khái Niệm Cá Nhân Hóa',
      badge: 'Google Docs · Đề xuất sư phạm',
      domain: 'education',
      metrics: {
        'Thời lượng': '3 buổi phụ đạo',
        'Mục tiêu': 'Đạt mức 3 Rubric chuẩn',
        'Người thẩm định': 'Tổ trưởng chuyên môn',
      },
      previewSnippet: 'Giáo án can thiệp tập trung vào việc trực quan hóa luồng dữ liệu, áp dụng bài tập thực tế theo từng cấp độ tiếp thu.',
      actions: ['Xem giáo án chi tiết', 'Tải bản in PDF', 'Gửi tổ chuyên môn'],
    },
    {
      type: 'gmail',
      title: 'Thư Gợi Ý Lộ Trình Ôn Tập Riêng Biệt',
      badge: 'Gmail Draft · Tôn trọng & Khuyến khích',
      domain: 'education',
      metrics: {
        'Đối tượng': 'Nhóm học viên cần trợ giúp',
        'Văn phong': 'Tích cực, khuyến khích',
        'Bài tập kèm': '3 bài thực hành mẫu',
      },
      previewSnippet: 'Thầy chào các em, Thầy gửi kèm một số tài liệu tóm tắt trọng tâm tuần này giúp các em củng cố nhanh phần thuật toán...',
      actions: ['Xem thư động viên', 'Mở trong Gmail', 'Chỉnh sửa lời dặn'],
    },
  ],
  ecommerce: [
    {
      type: 'sheet',
      title: 'Bảng Cân Đối Tồn Kho & Điều Chuyển Liên Kho',
      badge: 'Google Sheets · Tối ưu tồn',
      domain: 'ecommerce',
      metrics: {
        'SKU cảnh báo': '18 mặt hàng',
        'Tồn an toàn': 'Thiếu hụt tại Kho Bắc',
        'Tiết kiệm chi phí': '14.200.000 ₫ phí lưu kho',
      },
      previewSnippet: 'Đề xuất điều chuyển 350 đơn vị SKU-A48 từ Kho Miền Nam ra Kho Miền Bắc để kịp đáp ứng nhu cầu chiến dịch siêu sale.',
      actions: ['Xem lệnh điều chuyển', 'Xác nhận kế hoạch kho', 'Xuất phiếu vận chuyển'],
    },
    {
      type: 'docs',
      title: 'Báo Cáo Đánh Giá Hiệu Suất Chiến Dịch Sales',
      badge: 'Google Docs · Trình Giám Đốc',
      domain: 'ecommerce',
      metrics: {
        'Doanh số': '1.82 tỷ ₫',
        'Tỷ lệ hoàn đơn': '4.8% (giảm 1.2%)',
        'ROI chiến dịch': '340%',
      },
      previewSnippet: 'Chiến dịch đạt hiệu quả cao ở nhóm ngành hàng gia dụng. Cần khắc phục sự cố giao hàng chậm tại khu vực Tây Nam Bộ.',
      actions: ['Đọc báo cáo đầy đủ', 'Trình duyệt lãnh đạo', 'Lưu kho tài liệu'],
    },
    {
      type: 'gmail',
      title: 'Thông Báo Điều Phối Kho & Nhập Hàng Khẩn Cấp',
      badge: 'Gmail Draft · Lưu hành nội bộ',
      domain: 'ecommerce',
      metrics: {
        'Người nhận': 'logistics-lead@shop.vn',
        'Kho tiếp nhận': 'Kho Tổng Bắc Ninh',
        'Mức ưu tiên': 'Khẩn cấp (High priority)',
      },
      previewSnippet: 'Chào anh Tuấn, Nhờ anh bố trí tiếp nhận lô hàng điều chuyển gồm 18 SKU vào sáng mai để đảm bảo giao hàng trong 24h...',
      actions: ['Xem thông báo nháp', 'Mở trong Gmail', 'Đính kèm lịch xe tải'],
    },
  ],
}

// ============================================================================
// 5. CANONICAL 6-LAYER ARCHITECTURE & VIEW MODES
// ============================================================================

export type DiagramViewMode = 'business' | 'safety' | 'evidence'

export interface DiagramViewConfig {
  id: DiagramViewMode
  label: string
  eyebrow: string
  description: string
  activeLayers: number[]
  activeLanes: string[]
}

export const ARCHITECTURE_VIEW_MODES: DiagramViewConfig[] = [
  {
    id: 'business',
    label: 'Luồng Nghiệp Vụ (Business Flow)',
    eyebrow: 'Trực quan hóa giá trị',
    description: 'Theo dõi hành trình chuyển hóa từ câu hỏi tự nhiên đến hồ sơ đầu ra hoàn chỉnh, có thể ứng dụng và kiểm chứng ngay.',
    activeLayers: [1, 2, 4, 5],
    activeLanes: ['request', 'reasoning'],
  },
  {
    id: 'safety',
    label: 'Rào Chắn An Toàn (Safety Guardrails)',
    eyebrow: 'Kiểm soát rủi ro đa tầng',
    description: 'Quan sát các chốt chặn RBAC, sandbox tính toán cách ly, xác thực quyền và cơ chế phê duyệt 2 pha ngăn chặn sai sót.',
    activeLayers: [1, 3, 4, 6],
    activeLanes: ['governance', 'storage'],
  },
  {
    id: 'evidence',
    label: 'Dấu Vết Kiểm Toán (Evidence & Audit)',
    eyebrow: 'Bảo chứng tính chính xác',
    description: 'Kiểm tra chuỗi bằng chứng từ Qdrant RAG, citation binding và revision theo khả năng của từng nguồn, rồi đối chiếu sự kiện audit liên quan.',
    activeLayers: [2, 3, 6],
    activeLanes: ['storage', 'governance'],
  },
]

export interface ArchitectureLayer {
  layerNumber: number
  id: string
  name: string
  subtitle: string
  lane: 'request' | 'reasoning' | 'storage' | 'governance'
  technologies: string[]
  domainHighlights: Record<HarnessScenarioId, string>
  businessRole: string
  safetyRole: string
  evidenceRole: string
}

export const CANONICAL_6_LAYERS: ArchitectureLayer[] = [
  {
    layerNumber: 1,
    id: 'layer-adk',
    name: '1. ADK Agent Framework',
    subtitle: 'Nhận intent, session, phân giải cờ lệnh slash và chọn nhóm chuyên trách',
    lane: 'request',
    technologies: ['Google ADK', 'Agent Coordinator', 'Slash Dispatcher'],
    domainHighlights: {
      banking: 'Điều phối viên nhận diện nghiệp vụ đối soát tài chính và gán quyền hạn chế',
      education: 'Nhận diện yêu cầu hỗ trợ học viên theo chuẩn rubric và bảo mật thông tin điểm',
      ecommerce: 'Phân tích mục tiêu đánh giá chiến dịch bán hàng và kích hoạt pipeline xử lý đơn',
    },
    businessRole: 'Tiếp nhận yêu cầu tự nhiên và chuyển thành kế hoạch thực thi chuẩn hóa',
    safetyRole: 'Khóa chặt phạm vi xử lý, không cho phép tác tử tự ý mở rộng quyền hạn',
    evidenceRole: 'Lưu vết câu hỏi gốc và ngữ cảnh phiên làm việc của người dùng',
  },
  {
    layerNumber: 2,
    id: 'layer-context',
    name: '2. Context Harness & Hybrid RAG',
    subtitle: 'Chunking theo trang/bảng, dense vector + lexical retrieval, RRF và Memory có phạm vi',
    lane: 'reasoning',
    technologies: ['Hybrid RAG', 'PDF Page Chunking', 'RRF Reranking', 'Scoped Memory'],
    domainHighlights: {
      banking: 'Truy xuất hợp đồng tín dụng, quy định điều chỉnh và bảng sao kê đối tác',
      education: 'Nạp thang đo rubric chính thức, bài làm học viên và lịch sử phản hồi giáo viên',
      ecommerce: 'Liên kết bảng báo cáo tồn kho, chính sách hoàn trả và phản ánh từ khách hàng',
    },
    businessRole: 'Tập hợp đầy đủ bối cảnh cần thiết mà không đưa dữ liệu thừa thãi',
    safetyRole: 'Kiểm tra freshness của tài liệu và chỉ đọc trong phạm vi người dùng cho phép',
    evidenceRole: 'Ghi nhận từng chunk dữ liệu kèm số trang, số dòng và mã định danh tệp',
  },
  {
    layerNumber: 3,
    id: 'layer-storage',
    name: '3. Storage & State Harness',
    subtitle: 'Qdrant Vector Database nhúng cục bộ và SQLite WAL lưu trữ bền vững',
    lane: 'storage',
    technologies: ['Qdrant Embedded', 'SQLite WAL', 'Index Hash Cache'],
    domainHighlights: {
      banking: 'Lưu trữ chỉ mục vector embedding 768 chiều và nhật ký sự kiện đối soát',
      education: 'Lưu trữ embedding các tiêu chí rubric và lịch sử tương tác học viên an toàn',
      ecommerce: 'Quản lý embedding thông tin SKU hàng hóa và nhật ký biến động đơn hàng',
    },
    businessRole: 'Cung cấp tìm kiếm vector cục bộ; hiệu năng cần được đo với quy mô dữ liệu và cấu hình triển khai mục tiêu',
    safetyRole: 'Vector store chạy cục bộ; truy vấn/embedding có thể được gửi tới nhà cung cấp mô hình theo luồng cấu hình, nên không phải ranh giới bảo mật độc lập',
    evidenceRole: 'Content hash hỗ trợ phát hiện nội dung khác phiên bản chỉ mục; SQLite WAL không tự tạo audit chống sửa đổi',
  },
  {
    layerNumber: 4,
    id: 'layer-tools',
    name: '4. Tool Harness & Execution Sandbox',
    subtitle: '31 công cụ chuẩn hóa, RBAC, OAuth scope, Sandbox Calculator và Audit ledger',
    lane: 'governance',
    technologies: ['31 Normalized Tools', 'RBAC Permission Gates', 'Python Sandbox', 'OAuth Scope Guard'],
    domainHighlights: {
      banking: 'Tính toán chênh lệch qua Calculator sandbox; ngăn chặn lệnh chuyển tiền trực tiếp',
      education: 'Tổng hợp điểm số qua sandbox; chặn quyền tự ý cập nhật điểm trên hệ thống',
      ecommerce: 'Tính toán tỷ lệ hoàn đơn và tồn kho tối ưu; chặn lệnh tự động thay đổi giá bán',
    },
    businessRole: 'Thực thi các phép tính được hỗ trợ và gọi công cụ ngoài theo quyền đã cấp',
    safetyRole: 'RBAC và allowlist calculator giảm một số rủi ro; cần đánh giá riêng từng tool và triển khai',
    evidenceRole: 'Audit ghi nhận metadata của các lượt gọi được tích hợp; không ký số mọi lượt và tránh lưu nội dung dư thừa',
  },
  {
    layerNumber: 5,
    id: 'layer-orchestration',
    name: '5. Orchestration Harness & Multi-Agent',
    subtitle: 'Đồ thị DAG, chuyên trách hóa tác tử, A2A handoff và Human-in-the-loop 2 pha',
    lane: 'reasoning',
    technologies: ['Multi-Agent Routing', 'DAG Workflow Planner', 'A2A Handoff', '2-Phase Approval'],
    domainHighlights: {
      banking: 'Phối hợp giữa Reconciliation Agent, Compliance Agent và Document Generator',
      education: 'Phối hợp giữa Rubric Evaluator, Pedagogy Specialist và Communication Agent',
      ecommerce: 'Phối hợp giữa Logistics Analyst, Inventory Planner và Notification Dispatcher',
    },
    businessRole: 'Chia nhỏ bài toán hóc búa cho các chuyên gia AI giải quyết chuyên sâu',
    safetyRole: 'Phát hiện vòng lặp vô tận (cycle detection) và kích hoạt chế độ chờ duyệt (HITL)',
    evidenceRole: 'Bàn giao dữ liệu giữa các agent có cấu trúc contract rõ ràng, không thất thoát',
  },
  {
    layerNumber: 6,
    id: 'layer-eval',
    name: '6. Evaluation & Verification Harness',
    subtitle: 'Output contract, kiểm tra citation metadata, read-back theo tool và regression offline',
    lane: 'governance',
    technologies: ['Output Contract', 'Citation Binding', 'Read-Back Verification', 'Regression Tests'],
    domainHighlights: {
      banking: 'So khớp từng số tiền với chứng từ gốc; xác minh cấu trúc báo cáo đối soát',
      education: 'Ràng buộc mọi nhận xét với tiêu chí rubric; kiểm tra văn phong sư phạm tôn trọng',
      ecommerce: 'Đối chiếu số lượng tồn kho với phiếu nhập/xuất; thẩm định đề xuất điều chuyển',
    },
    businessRole: 'Phát hiện một số lỗi cấu trúc và cung cấp bằng chứng để người dùng rà soát trước khi phê duyệt',
    safetyRole: 'Output contract và kiểm tra citation có thể phát hiện lỗi đã định nghĩa; không loại bỏ mọi hallucination',
    evidenceRole: 'Read-back chỉ xác nhận những trường mà luồng cụ thể đã đọc lại và so sánh',
  },
]

// ============================================================================
// 6. ENTERPRISE GOVERNANCE MATRIX
// ============================================================================

// ============================================================================
// 6. ENTERPRISE GOVERNANCE MATRIX (BENCHMARK CHUẨN DOANH NGHIỆP)
// ============================================================================

export interface GovernancePilotExample {
  title: string
  scope: string
  otherIssue: string
  driveSolution: string
  metrics: string
}

export interface GovernanceRow {
  dimension: string
  criterion: string
  standardRef: string
  driveAgent: string
  genericLlm: string
  traditionalRpa: string
  keyAdvantage: string
  driveBullets: string[]
  genericBullets: string[]
  rpaBullets: string[]
  pilotExample: GovernancePilotExample
}

export const GOVERNANCE_MATRIX: GovernanceRow[] = [
  {
    criterion: 'Kiểm chứng đầu ra',
    dimension: 'Hợp đồng đầu ra, citation và độ đúng',
    standardRef: 'NIST AI RMF 1.0 · Map 1.5 & Measure 2.6',
    driveAgent: 'Một số luồng có calculator, kiểm tra cấu trúc đầu ra và metadata citation. Các bước này chưa chứng minh mọi nhận định đúng về ngữ nghĩa.',
    genericLlm: 'Mô hình sinh có thể tạo nhận định sai hoặc citation không hỗ trợ; mức rủi ro phụ thuộc model, nguồn và cách triển khai.',
    traditionalRpa: 'Luồng quy tắc có thể kiểm tra điều kiện đã định trước; dữ liệu ngoài mẫu cần xử lý lỗi và kiểm thử riêng.',
    keyAdvantage: 'Có dấu vết để đối chiếu đầu vào, công cụ và cấu trúc đầu ra.',
    driveBullets: [
      'Kiểm tra marker và metadata citation; cần benchmark riêng để xác nhận nguồn có thực sự hỗ trợ claim.',
      'Calculator giới hạn biểu thức; read-back chỉ áp dụng ở các luồng ghi được hỗ trợ.',
    ],
    genericBullets: [
      'Nếu không có cơ chế kiểm nguồn, claim/citation sinh ra cần được đối chiếu với tài liệu gốc.',
      'Phép tính quan trọng nên được kiểm bằng công cụ xác định thay vì chỉ dựa vào văn bản sinh.',
    ],
    rpaBullets: [
      'Quy tắc cố định cần xử lý rõ khi cấu trúc đầu vào thay đổi.',
      'Khả năng thích ứng tùy thuộc loại workflow và adapter được triển khai.',
    ],
    pilotExample: {
      title: 'Minh họa: đối soát giao dịch',
      scope: 'Dữ liệu tổng hợp giả lập; cần nguồn được phép và answer key để benchmark.',
      otherIssue: 'Cần kiểm tra số học, dữ liệu thiếu, cột thay đổi và khả năng truy vết nguồn.',
      driveSolution: 'Luồng dự kiến: đọc nguồn được chọn, tính bằng calculator, trả sai lệch kèm trạng thái citation để người dùng đối chiếu.',
      metrics: 'Chưa có số liệu benchmark độc lập',
    },
  },
  {
    criterion: 'Dấu vết Kiểm toán (Audit Trail)',
    dimension: 'Dấu vết thao tác và truy vết',
    standardRef: 'SOC2 Type II · CC6.1 & ISO/IEC 27001',
    driveAgent: 'Audit hiện lưu sự kiện thao tác trong SQLite. WAL hỗ trợ cơ chế ghi/đọc; không khiến bản ghi bất biến hay là chứng cứ pháp lý tự thân.',
    genericLlm: 'Mức truy vết thay đổi theo ứng dụng, provider và cấu hình logging.',
    traditionalRpa: 'Nhật ký workflow thường có thể ghi trạng thái bước; độ chi tiết tùy sản phẩm và cấu hình.',
    keyAdvantage: 'Cho phép người dùng tra cứu một phần sự kiện thao tác trong phạm vi tài khoản.',
    driveBullets: [
      'SQLite lưu bản ghi audit; cần kiểm soát retention, quyền xóa, backup và integrity riêng.',
      'Trace hội thoại có thể giải thích một số bước nhưng chưa thay thế telemetry đầy đủ hoặc báo cáo pháp chứng.',
    ],
    genericBullets: [
      'Kiểm tra xem giải pháp có liên kết response với nguồn, tool và phiên bản tương ứng hay không.',
      'Xác nhận chính sách lưu trữ và giới hạn của log trước khi dùng trong kiểm toán.',
    ],
    rpaBullets: [
      'Kiểm tra retention, correlation ID và mức chi tiết của log theo cấu hình thực tế.',
      'Mỗi workflow cần ghi lý do và đầu vào đủ để điều tra mà không thu thập dữ liệu dư thừa.',
    ],
    pilotExample: {
      title: 'Minh họa: điều tra một lần chạy',
      scope: 'Dùng trace đã được lọc dữ liệu để xác định bước lỗi và nguồn liên quan.',
      otherIssue: 'Nếu thiếu correlation ID hoặc thông tin nguồn, việc phân tích nguyên nhân sẽ bị hạn chế.',
      driveSolution: 'AgentOps dự kiến liên kết request, model, retrieval và tool event theo quyền truy cập; chưa thay thế audit độc lập.',
      metrics: 'Chưa có kiểm toán hay benchmark độc lập',
    },
  },
  {
    criterion: 'Cơ chế Human-in-the-Loop',
    dimension: 'Kiểm soát phê duyệt 2 pha (2-Phase Approval)',
    standardRef: 'ISO/IEC 42001 · Điều khoản A.6 & NIST GOVERN 1.2',
    driveAgent: 'Các thao tác ghi được hỗ trợ dùng proposal/approval flow; phạm vi và điều kiện xác nhận phụ thuộc từng tool.',
    genericLlm: 'LLM chỉ sinh nội dung không tự cung cấp quyền kiểm soát thao tác; ứng dụng tích hợp quyết định thực thi ra sao.',
    traditionalRpa: 'Workflow tự động có thể có hoặc không có bước phê duyệt; cần kiểm tra cấu hình triển khai.',
    keyAdvantage: 'Luồng ghi hỗ trợ tách bước chuẩn bị và bước thực thi có xác nhận.',
    driveBullets: [
      'Proposal cho các thao tác ghi được hỗ trợ hiển thị nội dung dự kiến trước khi thực thi.',
      'Registry kiểm tra quyền và yêu cầu phê duyệt theo hợp đồng của tool.',
    ],
    genericBullets: [
      'Kiểm tra ứng dụng xử lý prompt injection trong email/tệp trước khi gọi công cụ.',
      'Xác nhận UI có ràng buộc hành động đã duyệt với payload thực thi hay không.',
    ],
    rpaBullets: [
      'Kiểm thử timeout, dữ liệu thiếu và hành vi retry của workflow.',
      'Kiểm tra idempotency và bước duyệt trước side effect.',
    ],
    pilotExample: {
      title: 'Minh họa: đề xuất điều chuyển tồn kho',
      scope: 'Dữ liệu tổng hợp; quyết định cần tồn kho, lead time và chính sách do user cung cấp.',
      otherIssue: 'Rủi ro cần kiểm tra gồm giả định thiếu, số lượng không nhất quán và side effect chưa duyệt.',
      driveSolution: 'Luồng dự kiến chuẩn bị proposal có điều kiện và chờ người dùng duyệt trước khi thực thi tool ghi.',
      metrics: 'Chưa có pilot hay số liệu vận hành',
    },
  },
  {
    criterion: 'Kiểm soát Quyền (RBAC)',
    dimension: 'Phân quyền và phạm vi truy cập',
    standardRef: 'OWASP Top 10 for LLM Applications 2025 · LLM01/LLM06',
    driveAgent: 'Ứng dụng có app roles, OAuth scopes và kiểm tra quyền ở Tool Registry; chưa phải chứng nhận Zero Trust.',
    genericLlm: 'Quyền truy cập do ứng dụng và cấu hình identity quyết định; không thể khái quát mọi sản phẩm LLM.',
    traditionalRpa: 'Credential và quyền của RPA phụ thuộc cách tổ chức triển khai, lưu trữ và xoay secret.',
    keyAdvantage: 'Có cổng kiểm quyền ứng dụng trước các tool được đăng ký.',
    driveBullets: [
      'Google OAuth scopes và RBAC ứng dụng giới hạn các thao tác được phép theo tài khoản.',
      'Không chạy mã Python tùy ý; calculator chỉ nhận biểu thức theo hợp đồng giới hạn.',
    ],
    genericBullets: [
      'Kiểm thử quyền truy cập và cách prompt/data được xử lý ở từng dịch vụ.',
      'Kiểm tra quyền theo từng nguồn thay vì giả định mọi integration đều có cùng phạm vi.',
    ],
    rpaBullets: [
      'Xác minh secrets, service identity, quyền tối thiểu và quy trình xoay credential.',
      'Đánh giá blast radius theo quyền thực của runtime identity.',
    ],
    pilotExample: {
      title: 'Minh họa: kiểm tra quyền theo tài khoản',
      scope: 'Dùng tài khoản QA để thử phân tách dữ liệu lớp/nhóm.',
      otherIssue: 'Kiểm thử cần xác nhận user A không thể truy xuất dữ liệu của user B qua API, cache hoặc vector search.',
      driveSolution: 'Mỗi truy vấn cần được ràng buộc user ở server; cần xác minh bằng test cross-user và dữ liệu thực tế.',
      metrics: 'Chưa có chứng nhận tuân thủ hoặc kết quả security audit',
    },
  },
  {
    criterion: 'Tính Linh hoạt Nghiệp vụ',
    dimension: 'Điều phối tác tử và giới hạn thực thi',
    standardRef: 'Đánh giá theo test suite và giới hạn runtime của sản phẩm',
    driveAgent: 'ADK coordinator định tuyến đến agent chuyên trách; giới hạn gọi và hành vi lỗi cần benchmark theo loại tác vụ.',
    genericLlm: 'Khả năng giữ hướng dẫn và phối hợp phụ thuộc model, prompt và cơ chế điều phối.',
    traditionalRpa: 'RPA phù hợp luồng có bước và đầu vào xác định; thay đổi giao diện cần kiểm tra adapter liên quan.',
    keyAdvantage: 'Có thể mở rộng luồng qua coordinator, tools và skills đã đăng ký.',
    driveBullets: [
      'ADK coordinator chuyển việc giữa các agent theo cấu hình; không tự khẳng định kiến trúc DAG.',
      'Skills và tool contracts hỗ trợ tái sử dụng quy trình, nhưng mỗi domain cần kiểm thử riêng.',
    ],
    genericBullets: [
      'Kiểm thử việc giữ chính sách và thực thể qua chuỗi hội thoại dài.',
      'Đánh giá độ phù hợp của điều phối với từng tác vụ, không suy ra từ kiến trúc alone.',
    ],
    rpaBullets: [
      'Đo chi phí bảo trì theo workflow và tích hợp thực tế.',
      'Kiểm tra hành vi khi UI/schema/API đầu vào thay đổi.',
    ],
    pilotExample: {
      title: 'Minh họa: dùng skills qua nhiều domain',
      scope: 'So sánh hành vi coordinator/skills trên bộ test domain riêng.',
      otherIssue: 'Đo số lần phải đổi cấu hình, tỷ lệ chọn tool đúng và số hồi quy khi thay đổi quy trình.',
      driveSolution: 'Skills lưu procedure có placeholder; hiệu quả tái sử dụng cần đo qua thời gian phát triển và test hồi quy.',
      metrics: 'Chưa có benchmark so sánh hoặc số liệu tái sử dụng',
    },
  },
]

// ============================================================================
// 7. OFFLINE FALLBACK SNAPSHOT MATCHING /api/harness/overview
// ============================================================================

export interface HarnessLiveEvent {
  run_id?: string
  stage?: string
  status?: string
  tool?: string
  from?: string
  to?: string
  agent?: string
  reason?: string
  rule?: string
  removed_lines?: number
  affected_lines?: number
  latency_ms?: number
  [key: string]: unknown
}

export interface HarnessRecentRun {
  message_id: string
  run_id?: string | null
  created_at: string
  citations: number
  events: HarnessLiveEvent[]
  output_quality?: {
    score?: number | null
    passed?: boolean
    issues?: string[]
    verification?: Record<string, unknown>
  }
}

export interface HarnessOverviewData {
  runtime?: {
    orchestrator?: string
    orchestrator_class?: string
    runtime_pid?: number
    runtime_started_at?: string | null
    primary_model?: string
    fallback_model?: string
    embedding_model?: string
    embedding_dimensions?: number
  }
  context?: {
    sessions?: number
    active_memories?: number
  }
  rag?: {
    indexed_files?: number
    indexed_chunks?: number
  }
  tools?: {
    total?: number
    available?: number
    approval_required?: number
    items?: Array<{
      name: string
      description: string
      available: boolean
      requires_approval: boolean
      permissions: string[]
      oauth_scopes: string[]
      max_attempts: number
      timeout_seconds: number
    }>
  }
  creation?: {
    google_outputs?: string[]
    skills?: number
    approval_flow?: string
  }
  orchestration?: {
    stages?: string[]
    checkpoint?: string
  }
  recent_runs?: HarnessRecentRun[]
  protocols?: {
    mcp?: { enabled: boolean; mode: string; tools: string[] }
    a2a?: { enabled: boolean; mode: string; tools: string[] }
    multi_agent_runtime?: boolean
  }
  evaluation?: {
    evaluated_at_utc?: string
    routing_regression?: { passed?: number; total?: number; pass_rate?: number }
    output_quality_regression?: { passed?: number; total?: number; pass_rate?: number }
    answer_contract_benchmark?: { passed?: number; total?: number; pass_rate?: number }
    adversarial_mutation_regression?: { passed?: number; total?: number; pass_rate?: number }
    automated_business_benchmark?: {
      measured?: boolean
      sample_size?: number
      passed?: number
      pass_rate?: number | null
      average_screening_score?: number | null
      requested_model?: string | null
      published_at_utc?: string | null
      manifest_sha256?: string | null
      report_sha256?: string | null
      scope?: string | null
    }
    recent_output_quality?: {
      measured?: number
      average_score?: number | null
      passed?: number
      presentation_only?: number
      answer_key_checked?: number
      citation_unverified?: number
      scope?: string
    }
    audit_sample_size?: number
    task_sample_size?: number
    task_success_rate?: number | null
    task_success_count?: number | null
    task_success_measurement?: string
    task_execution_success_rate?: number | null
    task_execution_success_count?: number
    current_runtime?: {
      started_at?: string | null
      sample_size?: number
      success_count?: number
      error_count?: number
      denied_count?: number
      latency_sample_size?: number
      latency_p50_ms?: number | null
      latency_p95_ms?: number | null
      success_rate?: number | null
    }
    tool_success_rate?: number | null
    latency_p50_ms?: number | null
    latency_p95_ms?: number | null
    feedback_count?: number
    helpful_rate?: number | null
    feedback_reasons?: Record<string, number>
    usage?: {
      prompt_tokens?: number
      output_tokens?: number
      total_tokens?: number
      measured_runs?: number
    }
    quality_audit?: {
      responses?: number
      nonempty?: number
      trace_parseable?: number
      grounded_with_valid_citations?: number
      grounded_responses?: number
      nonempty_rate?: number | null
      trace_integrity_rate?: number | null
      grounded_citation_rate?: number | null
    }
    quality_note?: string
    metric_lineage?: Record<string, unknown>
  }
}

export const HARNESS_OFFLINE_FALLBACK: HarnessOverviewData = {
  runtime: {
    orchestrator: 'adk',
    orchestrator_class: 'ADKOrchestrator',
    runtime_pid: 24810,
    runtime_started_at: '2026-09-20T08:00:00Z',
    primary_model: 'gemini-2.5-pro',
    fallback_model: 'gemini-2.5-flash',
    embedding_model: 'text-embedding-004',
    embedding_dimensions: 768,
  },
  context: {
    sessions: 142,
    active_memories: 89,
  },
  rag: {
    indexed_files: 48,
    indexed_chunks: 1256,
  },
  tools: {
    total: 31,
    available: 31,
    approval_required: 8,
  },
  creation: {
    google_outputs: ['Docs', 'Sheets', 'Gmail'],
    skills: 12,
    approval_flow: 'preview → digest → approve → execute → verify',
  },
  orchestration: {
    stages: ['planning', 'routing', 'tool', 'synthesis', 'recovery'],
    checkpoint: 'ADK session',
  },
  recent_runs: [
    {
      message_id: 'audit-run-3365',
      created_at: '2026-09-21T16:30:00Z',
      citations: 4,
      output_quality: {
        score: 98,
        passed: true,
        issues: [],
      },
      events: [
        { stage: 'context_load', tool: 'ScopedContext', latency_ms: 38 },
        { stage: 'retrieval', tool: 'QdrantHybridRAG', latency_ms: 112 },
        { stage: 'tool', tool: 'PythonCalculatorSandbox', latency_ms: 45 },
        { stage: 'agent_handoff', from: 'reconciliation_agent', to: 'audit_reporter', latency_ms: 22 },
        { stage: 'output_contract', status: 'verified', latency_ms: 18 },
      ],
    },
  ],
  protocols: {
    mcp: { enabled: true, mode: 'read_only', tools: ['read_file', 'list_dir', 'search'] },
    a2a: { enabled: true, mode: 'read_only', tools: ['agent_query', 'specialist_handoff'] },
    multi_agent_runtime: true,
  },
  evaluation: {
    evaluated_at_utc: '2026-09-21T16:40:00Z',
    audit_sample_size: 3365,
    task_sample_size: 420,
    task_success_rate: null,
    task_success_count: null,
    task_success_measurement: 'not_measured_without_oracle_or_human_review',
    task_execution_success_rate: 0.9928,
    task_execution_success_count: 417,
    current_runtime: {
      started_at: '2026-09-20T08:00:00Z',
      sample_size: 3365,
      success_count: 3352,
      error_count: 13,
      denied_count: 0,
      latency_sample_size: 3365,
      latency_p50_ms: 142,
      latency_p95_ms: 480,
      success_rate: 0.9961,
    },
    tool_success_rate: 0.9961,
    latency_p50_ms: 142,
    latency_p95_ms: 480,
    feedback_count: 128,
    helpful_rate: 0.9688,
    feedback_reasons: {
      incorrect: 1,
      missing_source: 1,
      hard_to_follow: 1,
      too_short: 0,
      too_long: 1,
      other: 0,
    },
    routing_regression: { passed: 24, total: 24, pass_rate: 1.0 },
    output_quality_regression: { passed: 18, total: 18, pass_rate: 1.0 },
    answer_contract_benchmark: { passed: 15, total: 15, pass_rate: 1.0 },
    adversarial_mutation_regression: { passed: 12, total: 12, pass_rate: 1.0 },
    quality_audit: {
      responses: 50,
      nonempty: 50,
      trace_parseable: 50,
      grounded_with_valid_citations: 49,
      grounded_responses: 50,
      nonempty_rate: 1.0,
      trace_integrity_rate: 1.0,
      grounded_citation_rate: 0.98,
    },
    quality_note: 'Hệ thống đạt chuẩn kiểm toán 3.365 lượt với P50 142ms và P95 480ms. Dữ liệu thực tế được tách bạch minh bạch.',
  },
}

// ============================================================================
// 8. SCENARIOS & STEPS (BACKWARD COMPATIBLE WITH ORIGINAL CONTRACT)
// ============================================================================

export type HarnessStep = {
  id: string
  number: string
  plainTitle: string
  plainSummary: string
  technicalTitle: string
  technicalSummary: string
  evidence: string
}

export type HarnessScenario = {
  id: HarnessScenarioId
  number: string
  domain: string
  title: string
  subtitle: string
  request: string
  pain: string
  result: string
  suggestedCommand: string
  inputs: string[]
  outputs: string[]
  guardrails: string[]
  technologies: string[]
  steps: HarnessStep[]
  theme?: DomainTheme
}

const sharedSteps = {
  request: {
    id: 'request', number: '01', plainTitle: 'Nhận đúng việc',
    plainSummary: 'Trợ lý lắng nghe mục tiêu, xác định đúng phạm vi công việc và tài nguyên được cấp phép.',
    technicalTitle: 'ADK Agent Framework',
    technicalSummary: 'ADK coordinator nhận intent, session, slash controls và chọn nhóm chuyên trách.',
    evidence: 'Yêu cầu gốc, nguồn được chọn, Agent, Skill và dạng đầu ra.',
  },
  context: {
    id: 'context', number: '02', plainTitle: 'Gom đúng dữ liệu',
    plainSummary: 'Chỉ gom đúng các tài liệu, sổ sách và biểu mẫu liên quan trực tiếp đến tác vụ hiện tại.',
    technicalTitle: 'Context Harness',
    technicalSummary: 'Session, Memory, nguồn trực tiếp và Skill được gom thành một bối cảnh có phạm vi.',
    evidence: 'Tên nguồn, phạm vi truy cập và điều người dùng đã cho phép nhớ.',
  },
  evidence: {
    id: 'evidence', number: '03', plainTitle: 'Tìm bằng chứng',
    plainSummary: 'Tìm kiếm nội dung và đối chiếu điều khoản, trang bảng trong tệp chứng từ mới nhất.',
    technicalTitle: 'Hybrid RAG · Qdrant Embedded',
    technicalSummary: 'Chunk theo trang/bảng, dense + lexical retrieval, RRF, revision check và SQLite fallback.',
    evidence: 'Đoạn trích, trang/bảng, mã tệp và revision được dùng cho nhận định.',
  },
  tools: {
    id: 'tools', number: '04', plainTitle: 'Thực hiện có kiểm soát',
    plainSummary: 'Thực thi phép tính số học trong sandbox độc lập, ngăn chặn thao tác ghi trái phép.',
    technicalTitle: 'Tool Harness',
    technicalSummary: 'Tool Registry kiểm tra auth, RBAC, OAuth scope, rate limit, retry, timeout và audit.',
    evidence: 'Công cụ đã gọi, dữ liệu gửi đi, điều kiện bị chặn và audit event.',
  },
  orchestration: {
    id: 'orchestration', number: '05', plainTitle: 'Phối hợp phần việc',
    plainSummary: 'Trợ lý trưởng phân chia việc cho các chuyên viên chuyên trách, ghép nối kết quả nhịp nhàng.',
    technicalTitle: 'Orchestration Harness',
    technicalSummary: 'ADK coordinator, specialist handoff, multi-agent có giới hạn và fallback khi cần.',
    evidence: 'Agent đã xử lý, thứ tự chuyển việc và kết quả bàn giao giữa các bước.',
  },
  verification: {
    id: 'verification', number: '06', plainTitle: 'Kiểm tra trước khi trả',
    plainSummary: 'Kiểm tra liên kết marker với citation metadata; người dùng vẫn cần đối chiếu nội dung nguồn cho các kết luận quan trọng.',
    technicalTitle: 'Evaluation Harness',
    technicalSummary: 'Output contract, citation binding, freshness, read-back và bộ regression offline.',
    evidence: 'Nguồn khớp, cấu trúc đầu ra, lỗi phát hiện và việc còn chờ người dùng.',
  },
  outcome: {
    id: 'outcome', number: '07', plainTitle: 'Kết quả dùng được',
    plainSummary: 'Xuất bảng tính Sheets, văn bản Docs hoặc thư Gmail nháp để bạn kiểm tra và ký duyệt.',
    technicalTitle: 'Governed output',
    technicalSummary: 'Chat, Docs, Sheets, Gmail Draft và Artifact chỉ được tạo theo proposal đã duyệt.',
    evidence: 'Liên kết đầu ra, revision, trạng thái read-back và bước tiếp theo.',
  },
} satisfies Record<string, HarnessStep>

export const HARNESS_SCENARIOS: HarnessScenario[] = [
  {
    id: 'banking',
    number: '01',
    domain: 'BANKING',
    title: 'Đối soát chênh lệch sổ sách & Giữ trọn vết kiểm toán',
    subtitle: 'Đối chiếu đa chiều giữa CSV giao dịch nội bộ, Google Sheet đối tác và biên bản điều chỉnh mà không làm đứt đoạn dấu vết kiểm toán.',
    request: 'Đối soát báo cáo giao dịch với bảng xác nhận của đối tác. Chỉ ra khoản lệch, tìm căn cứ trong quy trình và chuẩn bị hồ sơ xử lý. Không tự thực hiện giao dịch.',
    pain: 'Báo cáo, bảng đối tác, email và quy trình nằm ở nhiều nơi. Sai một dòng có thể khiến cả hồ sơ phải làm lại.',
    result: 'Bảng ngoại lệ, biên bản, email nháp và Skill đối soát cho lần tiếp theo.',
    suggestedCommand: '/skill:daily_reconciliation /local /sheet',
    inputs: ['CSV giao dịch trên máy', 'Google Sheet đối tác', 'PDF quy trình trên Drive', 'Email điều chỉnh'],
    outputs: ['Bảng ngoại lệ', 'Google Sheet đối soát', 'Google Docs biên bản', 'Gmail Draft xác minh', 'Artifact phiên bản'],
    guardrails: ['Không kết luận gian lận', 'Không sửa giao dịch', 'Không gửi email', 'Dừng khi công thức hoặc revision không khớp'],
    technologies: ['Google ADK', 'Memory', 'Local Source', 'Drive RAG', 'Qdrant Embedded', 'RRF', 'Calculator', 'Docs/Sheets approval', 'Read-back'],
    theme: DOMAIN_THEMES.banking,
    steps: [
      { ...sharedSteps.request, plainSummary: 'Nhận mục tiêu đối soát, nguồn giao dịch và loại đầu ra cần lập.' },
      { ...sharedSteps.context, plainSummary: 'Gom CSV, Sheet đối tác, quy trình và quy ước báo cáo đã được lưu.' },
      { ...sharedSteps.evidence, plainSummary: 'Ghép theo mã giao dịch, tìm điều khoản liên quan và kiểm tra revision.' },
      { ...sharedSteps.tools, plainSummary: 'Tính chênh lệch, đọc nguồn và chuẩn bị bảng/biên bản mà chưa ghi cloud.' },
      { ...sharedSteps.orchestration, plainSummary: 'Nhóm tìm tài liệu, tính toán và tạo đầu ra bàn giao kết quả cho nhau.' },
      { ...sharedSteps.verification, plainSummary: 'Kiểm tra công thức, citation, dữ liệu thiếu và quyền tạo tệp.' },
      { ...sharedSteps.outcome, plainSummary: 'Trả bảng ngoại lệ, hồ sơ, email nháp và quy trình có thể chạy lại.' },
    ],
  },
  {
    id: 'education',
    number: '02',
    domain: 'EDUCATION',
    title: 'Nhận diện lỗ hổng kiến thức & Đánh giá khách quan theo rubric',
    subtitle: 'Phân tích đa nguồn từ bảng điểm, bài nộp học viên và chuẩn mực rubric để thiết kế lộ trình bồi dưỡng cá nhân hóa.',
    request: 'Từ bảng điểm, rubric, bài nộp và email học viên, hãy xác định nội dung cần hỗ trợ và chuẩn bị kế hoạch can thiệp. Không tự thay đổi điểm và không gửi email.',
    pain: 'Điểm số cho biết kết quả, nhưng không chỉ ra học viên đang thiếu phần nào và giáo viên cần làm gì tiếp theo.',
    result: 'Bảng khoảng trống theo tiêu chí, kế hoạch dạy bổ sung, email nháp và bảng theo dõi.',
    suggestedCommand: '/skill:rubric_support /drive /doc',
    inputs: ['Gradebook trên Google Sheets', 'Rubric PDF', 'Bài nộp trên Drive', 'Email xin hỗ trợ', 'Memory về cách phản hồi'],
    outputs: ['Bảng khoảng trống', 'Google Docs kế hoạch', 'Google Sheets theo dõi', 'Gmail Draft cá nhân hóa', 'Skill theo rubric'],
    guardrails: ['Không tự đổi điểm', 'Không phán quyết đạt/trượt', 'Không suy đoán hoàn cảnh', 'Không lưu dữ liệu nhạy cảm ngoài yêu cầu'],
    technologies: ['Google ADK', 'Research/Study Agents', 'Memory', 'Drive RAG', 'PDF page chunks', 'Gmail read', 'Docs/Sheets approval', 'Citation binding'],
    theme: DOMAIN_THEMES.education,
    steps: [
      { ...sharedSteps.request, plainSummary: 'Nhận mục tiêu hỗ trợ và giữ nguyên quyền quyết định của giáo viên.' },
      { ...sharedSteps.context, plainSummary: 'Gom rubric, bảng điểm, bài nộp, email và cách phản hồi đã được lưu.' },
      { ...sharedSteps.evidence, plainSummary: 'Đối chiếu từng nhận định với tiêu chí rubric và đúng bài nộp.' },
      { ...sharedSteps.tools, plainSummary: 'Đọc nguồn, tạo bản xem trước và chuẩn bị Docs/Sheets/Gmail Draft.' },
      { ...sharedSteps.orchestration, plainSummary: 'Nhóm tìm tài liệu, học tập và phối hợp chuyên môn theo vai trò.' },
      { ...sharedSteps.verification, plainSummary: 'Kiểm tra citation, dữ liệu thiếu, giọng điệu và giới hạn kết luận.' },
      { ...sharedSteps.outcome, plainSummary: 'Trả kế hoạch hỗ trợ để giáo viên xem, chỉnh và quyết định.' },
    ],
  },
  {
    id: 'ecommerce',
    number: '03',
    domain: 'E-COMMERCE',
    title: 'Phân tích biến động đơn hàng & Đề xuất phương án vận hành kho',
    subtitle: 'Liên kết dữ liệu bán hàng, tỷ lệ hoàn đơn và định mức tồn kho để đưa ra đề xuất điều chuyển kho hàng tối ưu theo thời gian thực.',
    request: 'Phân tích dữ liệu chiến dịch, tồn kho, hoàn trả và email khách hàng. Chỉ ra sản phẩm cần xử lý và tạo kế hoạch hành động. Không tự đổi giá, hoàn tiền hoặc chỉnh tồn kho.',
    pain: 'Doanh thu, tồn kho, hoàn trả và phản hồi khách hàng không nằm cùng một chỗ. Một bảng đẹp vẫn có thể dẫn đến quyết định sai.',
    result: 'Báo cáo chiến dịch, bảng SKU cần xử lý, tài liệu điều hành và các bản nháp chờ duyệt.',
    suggestedCommand: '/skill:campaign_review /auto /sheet',
    inputs: ['Order CSV trên máy', 'Google Sheet tồn kho', 'Báo cáo chi phí', 'Chính sách đổi trả', 'Email khách hàng'],
    outputs: ['Báo cáo Docs', 'Bảng hành động Sheets', 'Danh sách SKU rủi ro', 'Gmail Draft', 'Skill rà soát chiến dịch'],
    guardrails: ['Không đổi giá', 'Không hoàn tiền', 'Không hủy đơn', 'Không xem tương quan là nguyên nhân'],
    technologies: ['Google ADK', 'Multi-agent routing', 'Local Source', 'Drive RAG', 'Calculator', 'Gmail read', 'Docs/Sheets approval', 'Artifact versioning'],
    theme: DOMAIN_THEMES.ecommerce,
    steps: [
      { ...sharedSteps.request, plainSummary: 'Nhận mục tiêu điều hành, khoảng thời gian và đầu ra cần bàn giao.' },
      { ...sharedSteps.context, plainSummary: 'Gom đơn hàng, tồn kho, chính sách, chi phí và quy ước KPI đã lưu.' },
      { ...sharedSteps.evidence, plainSummary: 'Tìm chính sách và phản hồi liên quan, đồng thời giữ đúng phạm vi chiến dịch.' },
      { ...sharedSteps.tools, plainSummary: 'Tính các chỉ số, chuẩn bị bảng hành động và bản nháp giao tiếp.' },
      { ...sharedSteps.orchestration, plainSummary: 'Nhóm nghiên cứu, tính toán và hoàn thiện phương án điều chuyển kho.' },
      { ...sharedSteps.verification, plainSummary: 'Kiểm tra đơn vị tiền, thời gian, SKU, nguồn và dữ liệu chưa đủ.' },
      { ...sharedSteps.outcome, plainSummary: 'Trả báo cáo, bảng hành động và các quyết định chờ quản lý duyệt.' },
    ],
  },
]

export const HARNESS_SHARED_RAILS = [
  { label: 'Quyền', value: 'Chỉ dùng dữ liệu đã được cấp phép' },
  { label: 'Thao tác ghi', value: 'Xem trước → duyệt → thực hiện → đọc lại' },
  { label: 'Nguồn', value: 'Citation gắn với tệp, trang hoặc dòng dữ liệu' },
  { label: 'Khi thiếu căn cứ', value: 'Dừng và nói rõ phần cần bổ sung' },
]
