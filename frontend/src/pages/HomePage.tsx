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
    title: 'Chuẩn bị hồ sơ khách hàng',
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
    description: 'Hiểu cách chọn nguồn, phân công, kiểm chứng và duyệt hành động.',
    target: 'harness',
    icon: <BookOpen24Regular />,
  },
]

const quickStarts: Array<{label: string; detail: string; prompt: string; controls: ChatControls}> = [
  {label: 'Chuẩn bị đầu ngày', detail: 'Đọc thư · làm rõ yêu cầu tư vấn', prompt: 'Tổng hợp email chưa đọc hôm nay liên quan tới yêu cầu tư vấn. Nêu yêu cầu đã xác nhận, thông tin còn thiếu và việc cần phản hồi. Chỉ ghi thời hạn khi thư nêu rõ; không tự suy ra ngân sách.', controls: {source: 'gmail', agent: 'communication', output: 'chat', workflow: 'email_digest'}},
  {label: 'Chuẩn bị trước cuộc hẹn', detail: 'Lịch · thư · hồ sơ liên quan', prompt: 'Chuẩn bị cho cuộc hẹn tư vấn tôi sẽ chỉ định. Hỏi tôi tên hoặc thời điểm cuộc hẹn và tài liệu liên quan nếu chưa đủ để chọn đúng nguồn. Sau đó lập báo cáo gồm mục tiêu, dữ kiện có nguồn, điều chưa biết và câu hỏi cần xác nhận. Không tạo hoặc sửa lịch.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
  {label: 'Tiếp nối cuộc trao đổi', detail: 'Ghi chú · bản phản hồi chờ duyệt', prompt: 'Từ ghi chú cuộc trao đổi tôi sẽ cung cấp, tách quyết định, việc cần làm, người phụ trách và thời hạn. Thiếu thông tin thì ghi chưa xác nhận. Soạn phản hồi để tôi xem trước, hỏi rõ người nhận và nơi lưu; không gửi hoặc ghi Google khi chưa được duyệt.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
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
        <p className="home-kicker">Chuẩn bị tư vấn khách hàng doanh nghiệp</p>
        <h2>Từ yêu cầu khách hàng,<br />chuẩn bị cuộc hẹn rõ ràng.</h2>
        <ul className="home-hero-points">
          <li>Đối chiếu thư, lịch và tài liệu; làm rõ dữ kiện và điều còn thiếu.</li>
          <li>Chuẩn bị báo cáo và phản hồi; bạn duyệt trước khi ghi hoặc gửi.</li>
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
