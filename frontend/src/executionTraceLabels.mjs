const agents = {
  user: 'Bạn',
  drive_coordinator: 'Trợ lý điều phối', Coordinator: 'Trợ lý điều phối',
  web_research_agent: 'Trợ lý tìm và đối chiếu nguồn', email_agent: 'Trợ lý thư điện tử',
  company_info_agent: 'Trợ lý thông tin doanh nghiệp', calendar_agent: 'Trợ lý lịch hẹn',
  report_generation_agent: 'Trợ lý báo cáo', memory_agent: 'Trợ lý bộ nhớ',
  human_approval_agent: 'Trợ lý xin duyệt', skill_agent: 'Trợ lý quy trình cá nhân',
}

const tools = {
  local_source_search: 'Tìm tài liệu đã tải lên', local_source_read: 'Đọc tài liệu đã tải lên',
  web_research: 'Tìm nguồn trên Internet', calculate: 'Tính toán',
  drive_file_metadata: 'Kiểm tra thông tin tài liệu', drive_list_files: 'Liệt kê tài liệu trên Drive',
  drive_search_files: 'Tìm tài liệu trên Drive', drive_read_file: 'Đọc tài liệu trên Drive',
  gmail_list_messages: 'Liệt kê thư', gmail_read_matching_messages: 'Đọc các thư phù hợp',
  gmail_read_thread: 'Đọc cuộc trao đổi', gmail_get_attachment: 'Tải tệp đính kèm',
  gmail_summarize_thread: 'Tóm tắt cuộc trao đổi', gmail_create_draft: 'Tạo thư nháp',
  gmail_prepare_native_draft: 'Chuẩn bị thư nháp', gmail_prepare_draft: 'Chuẩn bị nội dung thư',
  gmail_reconcile_draft: 'Kiểm tra lại thư nháp', gmail_send: 'Gửi thư đã duyệt',
  calendar_list_upcoming: 'Đọc lịch hẹn sắp tới', company_search: 'Tìm thông tin doanh nghiệp',
  company_upsert: 'Lưu thông tin doanh nghiệp', docs_prepare: 'Chuẩn bị tài liệu để duyệt',
  docs_execute: 'Tạo hoặc sửa tài liệu đã duyệt', docs_reconcile: 'Kiểm tra lại thao tác tài liệu',
  sheets_prepare: 'Chuẩn bị bảng tính để duyệt', sheets_execute: 'Tạo bảng tính đã duyệt',
  sheets_reconcile: 'Kiểm tra lại thao tác bảng tính', memory_search: 'Tìm thông tin đã nhớ',
  memory_save: 'Lưu thông tin được yêu cầu ghi nhớ',
  rag_index_drive_file: 'Lập chỉ mục tài liệu trên Drive',
  rag_unindex_drive_file: 'Gỡ tài liệu trên Drive khỏi chỉ mục',
  rag_search: 'Tìm trong nội dung tài liệu đã lập chỉ mục',
  artifact_list: 'Đọc các ghi chú và kế hoạch đã lưu', artifact_save: 'Lưu kết quả đã duyệt',
  skill_save: 'Tạo hoặc cập nhật quy trình cá nhân', skill_run: 'Nạp quy trình và điền đầu vào',
  skill_list: 'Liệt kê quy trình cá nhân', skill_archive: 'Lưu trữ quy trình cá nhân',
}

const knownLabel = (labels, value) => Object.hasOwn(labels, value) ? labels[value] : undefined

export function executionAgentLabel(value) { return knownLabel(agents, value) ?? 'Trợ lý khác' }
export function executionToolLabel(value) { return knownLabel(tools, value) ?? 'Công cụ khác' }

/** Chỉ thay tên nội bộ đã biết trong bản hiển thị, không sửa dữ liệu sự kiện. */
export function executionTextLabel(value) {
  return value.replace(/\b[A-Za-z][A-Za-z0-9_]*\b/g, (word) => knownLabel(agents, word) ?? knownLabel(tools, word) ?? word)
}

export function executionModelLabel(value) {
  const match = /^gemini-(\d+(?:\.\d+)?)-(flash-lite|flash|pro)(-.*)?$/i.exec(value)
  if (!match) return 'Mô hình được ghi trong dữ liệu kỹ thuật'
  const family = { 'flash-lite': 'Flash Lite', flash: 'Flash', pro: 'Pro' }[match[2].toLowerCase()]
  // Giữ cả biến thể/phiên bản hậu tố; không suy ra năng lực chỉ từ tên dòng model.
  return `Gemini ${match[1]} ${family}${match[3] ?? ''}`
}
