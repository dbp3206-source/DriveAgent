import {
  ArrowRight20Regular,
  BookOpen24Regular,
  Chat24Regular,
  Database24Regular,
  Folder24Regular,
  Mail24Regular,
  Wand24Regular,
} from '@fluentui/react-icons'
import type { ReactNode } from 'react'
import type { PageKey } from '../components/AppShell'
import type { ChatControls } from '../chatControls'

const journeys: Array<{
  title: string
  description: string
  target: PageKey
  icon: ReactNode
}> = [
  {
    title: 'Hỏi từ tài liệu',
    description: 'Tìm, đọc và trả lời có trích nguồn từ Drive hoặc tài liệu local.',
    target: 'chat',
    icon: <Chat24Regular />,
  },
  {
    title: 'Chuẩn bị tài liệu học',
    description: 'Chọn tệp, kiểm tra nội dung và lập chỉ mục để dùng lại lâu dài.',
    target: 'drive',
    icon: <Folder24Regular />,
  },
  {
    title: 'Xử lý email cần chú ý',
    description: 'Tìm, đọc và chuẩn bị phản hồi Gmail. Xem trước rồi lưu nháp; Agent không tự gửi.',
    target: 'gmail',
    icon: <Mail24Regular />,
  },
  {
    title: 'Dạy Agent một quy trình',
    description: 'Lưu cách làm của riêng bạn thành Skill và dùng lại với dữ liệu mới.',
    target: 'skills',
    icon: <Wand24Regular />,
  },
  {
    title: 'Quản lý điều Agent nhớ',
    description: 'Xem, sửa hoặc lưu trữ sở thích và ngữ cảnh của riêng bạn.',
    target: 'memory',
    icon: <Database24Regular />,
  },
  {
    title: 'Hiểu cách Agent làm việc',
    description: 'Theo dõi Context, RAG, Tool, Orchestration và Evaluation bằng dữ liệu thật.',
    target: 'harness',
    icon: <BookOpen24Regular />,
  },
]

const quickStarts: Array<{label: string; detail: string; prompt: string; controls: ChatControls}> = [
  {label: 'Dọn hộp thư hôm nay', detail: 'Gmail · ưu tiên việc cần phản hồi', prompt: 'Tổng hợp email chưa đọc từ hôm nay. Nhóm thành cần trả lời, cần theo dõi và chỉ để biết; chỉ nêu deadline khi email ghi rõ.', controls: {source: 'gmail', agent: 'communication', output: 'chat', workflow: 'email_digest'}},
  {label: 'Ôn một chủ đề từ tài liệu', detail: 'RAG · cheatsheet và câu tự kiểm tra', prompt: 'Từ các tài liệu đã lập chỉ mục, hãy tạo cheatsheet dễ hiểu về chủ đề tôi sẽ cung cấp, kèm ví dụ và 5 câu tự kiểm tra.', controls: {source: 'rag', agent: 'research', output: 'chat', workflow: 'source_summary'}},
  {label: 'Soạn báo cáo có nguồn', detail: 'RAG → bản xem trước Google Docs', prompt: 'Tổng hợp các nguồn liên quan thành báo cáo có mục tiêu, bằng chứng, bảng đối chiếu, kết luận và việc cần làm. Tạo bản xem trước Google Docs để tôi duyệt.', controls: {source: 'rag', agent: 'research', output: 'document', workflow: 'compare_sources'}},
  {label: 'Tạo bảng theo dõi ngân sách', detail: 'Google Sheets · công thức an toàn', prompt: 'Tạo bản xem trước bảng theo dõi ngân sách tháng với nhóm chi phí, ngân sách, thực chi, chênh lệch và tổng. Dùng dữ liệu mẫu và ghi rõ đó là dữ liệu mẫu.', controls: {source: 'general', agent: 'workspace', output: 'spreadsheet', workflow: 'budget_tracker'}},
]

export function HomePage({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  function launch(prompt: string, controls: ChatControls) {
    const detail = {prompt, controls}
    sessionStorage.setItem('drive_agent_chat_launch', JSON.stringify(detail))
    window.dispatchEvent(new CustomEvent('driveagent:chat-launch', {detail}))
    onNavigate('chat')
  }
  return (
    <section className="home-page">
      <header className="home-hero">
        <p className="home-kicker">Study & Work Command Center</p>
        <h2>Từ một tài liệu,<br />đi đến việc cần làm.</h2>
        <ul className="home-hero-points">
          <li>Tìm nguồn và hiểu nội dung từ Drive, Gmail hoặc tài liệu bạn chọn.</li>
          <li>Tạo kết quả; bạn xem lại trước khi ghi vào Google Workspace.</li>
        </ul>
        <button className="home-primary-action" type="button" onClick={() => onNavigate('chat')}>
          Bắt đầu một câu hỏi <ArrowRight20Regular />
        </button>
        <div className="home-orbit" aria-hidden="true">
          <span>Nguồn</span><i /><span>Hiểu</span><i /><span>Hành động</span><i /><span>Kiểm chứng</span>
        </div>
        <section className="home-quick-starts" aria-label="Quy trình bắt đầu nhanh">
          <p>Bắt đầu nhanh. Bạn vẫn xem lại câu hỏi trước khi chạy.</p>
          <div>{quickStarts.map((item, index) => <button type="button" key={item.label} onClick={() => launch(item.prompt, item.controls)}>
            <span>{String(index + 1).padStart(2, '0')}</span><strong>{item.label}</strong><small>{item.detail}</small><ArrowRight20Regular />
          </button>)}</div>
        </section>
      </header>

      <div className="journey-list" aria-label="Các việc có thể bắt đầu">
        <p className="journey-list__label">Bạn muốn làm gì hôm nay?</p>
        {journeys.map((journey, index) => (
          <button key={journey.title} type="button" onClick={() => onNavigate(journey.target)}>
            <span className="journey-list__number">0{index + 1}</span>
            <span className="journey-list__icon">{journey.icon}</span>
            <span className="journey-list__copy">
              <strong>{journey.title}</strong>
              <small>{journey.description}</small>
            </span>
            <ArrowRight20Regular aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  )
}
