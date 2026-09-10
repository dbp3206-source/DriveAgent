const stages: Record<string, { title: string; description: string }> = {
  context: { title: 'Ngữ cảnh hội thoại', description: 'Thông tin về phiên xử lý và giới hạn ngữ cảnh.' },
  usage: { title: 'Tài nguyên model', description: 'Số token provider báo cho bước này; không phải điểm chất lượng.' },
  plan: { title: 'Kế hoạch dự kiến', description: 'Các bước dự kiến, không phải bằng chứng đã hoàn thành.' },
  model: { title: 'Xử lý yêu cầu', description: 'Mô hình chọn công cụ hoặc tạo câu trả lời.' },
  planning: { title: 'Lập kế hoạch', description: 'Chia yêu cầu thành các bước có thể thực hiện.' },
  agent: { title: 'Xử lý yêu cầu', description: 'Chọn công cụ hoặc chuẩn bị câu trả lời.' },
  tool: { title: 'Sử dụng công cụ', description: 'Thực thi qua lớp kiểm tra quyền và ghi nhật ký.' },
  synthesis: { title: 'Tổng hợp kết quả', description: 'Tạo câu trả lời từ kết quả đã thu thập.' },
  multi_agent: { title: 'Nhóm Agent chuyên trách', description: 'Coordinator chuẩn bị các Agent theo từng nhóm công việc.' },
  agent_handoff: { title: 'Chuyển giao nhiệm vụ', description: 'Yêu cầu được chuyển tới Agent có đúng chuyên môn và bộ công cụ.' },
}
const statuses: Record<string, string> = {
  success: 'Hoàn tất', error: 'Có lỗi', fallback: 'Dùng phương án dự phòng',
  running: 'Đang chạy', tool_call: 'Yêu cầu công cụ', denied: 'Không đủ quyền',
  ready: 'Sẵn sàng',
}

/** Chỉ diễn giải sự kiện backend thực sự ghi nhận; không tạo điểm chất lượng giả. */
export function ExecutionTrace({ trace }: { trace: Array<Record<string, unknown>> }) {
  return <details className="trace-panel">
    <summary>Cách Agent xử lý · {trace.length} sự kiện</summary>
    <p>Các sự kiện thực thi giúp bạn hiểu cách Agent làm việc. Đây không phải suy nghĩ nội bộ của mô hình; thứ tự hiển thị được nhóm theo nhật ký, không phải dòng thời gian chính xác.</p>
    <ol className="execution-list">
      {trace.map((event, index) => {
        const stage = stages[String(event.stage)]
        return <li key={index}>
          <div><strong>{stage?.title ?? String(event.stage ?? 'Sự kiện')}</strong>
            <span className={`execution-status execution-status--${String(event.status)}`}>
              {statuses[String(event.status)] ?? String(event.status ?? (event.stage === 'plan' ? 'Dự kiến' : 'Chưa rõ'))}
            </span>
          </div>
          <p>{stage?.description}</p>
          {typeof event.note === 'string' && <p>{event.note}</p>}
          {typeof event.model === 'string' && <p>Model thực dùng: <code>{event.model}</code></p>}
          {typeof event.latency_ms === 'number' && <p>Thời gian: {event.latency_ms.toLocaleString('vi-VN')} ms</p>}
          {typeof event.total_token_count === 'number' && <p>Tổng token: {event.total_token_count.toLocaleString('vi-VN')}</p>}
          {typeof event.from === 'string' && typeof event.to === 'string' && <p>Từ <code>{event.from}</code> sang <code>{event.to}</code></p>}
          {Array.isArray(event.agents) ? <p>Agent khả dụng: {event.agents.filter((agent): agent is string => typeof agent === 'string').join(', ')}</p> : null}
          {Array.isArray(event.steps) ? <ul>{event.steps.filter((step): step is string => typeof step === 'string').map((step, stepIndex) => <li key={stepIndex}>{step}</li>)}</ul> : null}
          {typeof event.tool === 'string' ? <code>{event.tool}</code> : null}
          {typeof event.error === 'string' ? <p className="execution-error">{event.error}</p> : null}
        </li>
      })}
    </ol>
    <details><summary>Dữ liệu kỹ thuật</summary><pre>{JSON.stringify(trace, null, 2)}</pre></details>
  </details>
}
