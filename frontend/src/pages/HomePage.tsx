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
    description: 'Tìm, đọc và trả lời có trích nguồn từ tài liệu bạn chọn.',
    target: 'chat',
    icon: <Chat24Regular />,
  },
  {
    title: 'Chọn tài liệu trên Drive',
    description: 'Xem gần đây, lọc nhanh và chọn đúng tài liệu cần dùng.',
    target: 'drive',
    icon: <Folder24Regular />,
  },
  {
    title: 'Xử lý email cần chú ý',
    description: 'Tìm, đọc chuỗi thư và chuẩn bị nội dung phản hồi.',
    target: 'gmail',
    icon: <Mail24Regular />,
  },
  {
    title: 'Lưu cách làm để dùng lại',
    description: 'Giữ mẫu công việc của riêng bạn và dùng với dữ liệu mới.',
    target: 'skills',
    icon: <Wand24Regular />,
  },
  {
    title: 'Quản lý điều trợ lý nhớ',
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
  {label: 'Hiểu tài liệu', detail: 'Tra cứu · đối chiếu · chỉ rõ nguồn', prompt: 'Giúp tôi hiểu hướng dẫn hoặc đối chiếu hai tài liệu. Nếu tôi chưa chọn nguồn và câu hỏi, hỏi ngắn để chọn đúng. Trả lời trực tiếp, nêu nguồn, điểm khác biệt hoặc phần chưa rõ; phân biệt bản có hiệu lực với bản nháp. Không ghi dữ liệu.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
  {label: 'Nắm tình hình', detail: 'Đã chốt · còn chờ · cần xác nhận', prompt: 'Giúp tôi tổng hợp tình hình từ thư hoặc cập nhật tôi sẽ chọn. Nếu chưa đủ để chọn đúng nguồn, hỏi ngắn. Tách điều đã chốt, còn mở và cần xác nhận; chỉ ghi người phụ trách hoặc thời hạn khi nguồn nêu rõ. Không gửi thư hoặc ghi dữ liệu.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
  {label: 'Phân tích và đề xuất', detail: 'So phương án · đánh đổi · hướng ưu tiên', prompt: 'Giúp tôi phân tích một vấn đề hoặc chọn phương án. Tôi sẽ cung cấp mục tiêu, dữ kiện và ràng buộc. Làm phần đã đủ thông tin, chỉ hỏi điểm thiếu làm đổi kết quả. Nêu các hướng khả thi, đánh đổi, hướng ưu tiên có lý do và một hoặc hai bước tiếp hữu ích. Không bịa số liệu hoặc tự thực hiện hành động.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
  {label: 'Chuẩn bị cuộc họp', detail: 'Mục tiêu · câu hỏi · điểm cần quyết định', prompt: 'Giúp tôi chuẩn bị cho cuộc họp tôi sẽ chỉ định. Nếu chưa đủ để chọn đúng cuộc họp hoặc tài liệu, hỏi ngắn. Nêu mục tiêu, dữ kiện có nguồn, câu hỏi và điểm cần quyết định. Khi tôi cung cấp ghi chú sau họp, cập nhật quyết định và việc còn mở. Không gửi thư, tạo hoặc sửa lịch.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
  {label: 'Soạn và hoàn thiện', detail: 'Bản nháp · chỉnh sửa · bàn giao', prompt: 'Giúp tôi soạn hoặc chỉnh một báo cáo, đề xuất hay phản hồi từ thông tin tôi cung cấp. Hỏi mục đích, người nhận hoặc nguồn nếu thiếu chi tiết cần thiết. Soạn bản nháp để tôi xem, giữ dữ kiện đã xác nhận; không gửi hoặc tạo tài liệu bên ngoài khi chưa được duyệt.', controls: {source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto'}},
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
        <p className="home-kicker">Trợ lý AI cho công việc nội bộ</p>
        <h2>Bạn cần làm gì<br />hôm nay?</h2>
        <ul className="home-hero-points">
          <li>Hiểu tài liệu, nắm tình hình và chọn hướng giải quyết.</li>
          <li>Chuẩn bị cuộc họp, hoàn thiện nội dung; bạn duyệt trước khi tạo tài liệu bên ngoài.</li>
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
