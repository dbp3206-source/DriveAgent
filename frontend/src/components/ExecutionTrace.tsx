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
  output_contract: { title: 'Kiểm tra yêu cầu đầu ra', description: 'Đối chiếu độ dài, cấu trúc và các ràng buộc rõ ràng trước khi coi câu trả lời là hoàn tất.' },
  output_guard: { title: 'Kiểm tra chất lượng đầu ra', description: 'Áp dụng ràng buộc rõ ràng của bạn trước khi hiển thị câu trả lời.' },
}
const statuses: Record<string, string> = {
  success: 'Hoàn tất', error: 'Có lỗi', fallback: 'Dùng phương án dự phòng',
  running: 'Đang chạy', tool_call: 'Yêu cầu công cụ', denied: 'Không đủ quyền',
  ready: 'Sẵn sàng', degraded: 'Chưa đạt', failed: 'Thất bại',
  corrected: 'Đã hiệu chỉnh',
}
const outputViolations: Record<string, string> = {
  below_explicit_word_minimum: 'Ngắn hơn độ dài đã yêu cầu.',
  above_explicit_word_maximum: 'Dài hơn độ dài đã yêu cầu.',
  below_explicit_bullet_minimum: 'Thiếu số gạch đầu dòng đã yêu cầu.',
  below_explicit_numbered_step_minimum: 'Thiếu số bước đã yêu cầu.',
  below_explicit_heading_minimum: 'Thiếu các mục phân tích đã yêu cầu.',
  missing_explicit_markdown_table: 'Thiếu bảng Markdown đã yêu cầu.',
  citation_markers_changed: 'Bản chỉnh sửa làm thay đổi trích dẫn.',
  numeric_claims_added: 'Bản chỉnh sửa thêm số liệu không có ở bản gốc.',
  source_sections_dropped: 'Bản chỉnh sửa bỏ phần nội dung chính.',
  rewrite_truncated: 'Bản chỉnh sửa bị cắt trước khi hoàn thành.',
  missing_action_section: 'Thiếu hành động cùng ngưỡng kích hoạt định lượng.',
  numeric_comparison_inconsistent: 'Có phép so sánh số học không nhất quán.',
}

/** Chỉ diễn giải sự kiện backend thực sự ghi nhận; không tạo điểm chất lượng giả. */
export function ExecutionTrace({ trace }: { trace: Array<Record<string, unknown>> }) {
  return <details className="trace-panel">
    <summary>Cách Agent xử lý · {trace.length} sự kiện</summary>
    <ul className="trace-explainer">
      <li>Nhật ký cho biết các sự kiện đã ghi nhận, không hiển thị suy nghĩ nội bộ của mô hình.</li>
      <li>Sự kiện được nhóm theo loại; thứ tự không đại diện chính xác cho thời gian.</li>
    </ul>
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
          {event.stage === 'output_contract' && Array.isArray(event.violations) &&
            <ul>{event.violations.filter((code): code is string => typeof code === 'string' && code in outputViolations)
              .map((code, reasonIndex) => <li key={`${code}-${reasonIndex}`}>{outputViolations[code]}</li>)}</ul>}
          {typeof event.note === 'string' && <p>{event.note}</p>}
          {typeof event.model === 'string' && <p>Model thực dùng: <code>{event.model}</code></p>}
          {typeof event.provider_code === 'number' && <p>Mã provider: <code>{event.provider_code}</code></p>}
          {typeof event.latency_ms === 'number' && <p>Thời gian: {event.latency_ms.toLocaleString('vi-VN')} ms</p>}
          {typeof event.total_token_count === 'number' && <p>Tổng token: {event.total_token_count.toLocaleString('vi-VN')}</p>}
          {event.rule === 'explicit_unsourced_claim_restriction' && typeof event.removed_lines === 'number' &&
            <p>Đã lược bỏ {event.removed_lines.toLocaleString('vi-VN')} dòng nhận định cần nguồn theo yêu cầu của bạn.</p>}
          {event.rule === 'explicit_unsourced_claim_restriction' && typeof event.affected_lines === 'number' &&
            <p>Đã hiệu chỉnh {event.affected_lines.toLocaleString('vi-VN')} dòng nhận định chưa có nguồn, đồng thời giữ nguyên cấu trúc trình bày.</p>}
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
