import {
  ArrowRight20Regular,
  BookOpen24Regular,
  Chat24Regular,
  Database24Regular,
  Folder24Regular,
  Image24Regular,
  Wand24Regular,
} from '@fluentui/react-icons'
import type { ReactNode } from 'react'
import type { PageKey } from '../components/AppShell'

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
    title: 'Tạo visual trên máy',
    description: 'Dựng infographic, flowchart hoặc timeline thành PNG và SVG, không tốn API ảnh.',
    target: 'visuals',
    icon: <Image24Regular />,
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

export function HomePage({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  return (
    <section className="home-page">
      <header className="home-hero">
        <p className="home-kicker">Study & Work Command Center</p>
        <h2>Từ một tài liệu,<br />đi đến việc cần làm.</h2>
        <p className="home-lede">
          DriveAgent giúp bạn tìm nguồn, hiểu nội dung, tạo kết quả và kiểm tra từng bước
          trước khi dữ liệu được ghi ra Google Workspace.
        </p>
        <button className="home-primary-action" type="button" onClick={() => onNavigate('chat')}>
          Bắt đầu một câu hỏi <ArrowRight20Regular />
        </button>
        <div className="home-orbit" aria-hidden="true">
          <span>Nguồn</span><i /><span>Hiểu</span><i /><span>Hành động</span><i /><span>Kiểm chứng</span>
        </div>
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
