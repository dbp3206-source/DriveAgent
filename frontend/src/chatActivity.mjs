/** UI-only task metadata. Never persist prompts, answers, or credentials here. */
export const CHAT_OPEN_EVENT = 'driveagent:chat-open'
export const CHAT_OPEN_KEY = 'drive_agent_chat_open'
const phases = new Set(['running', 'completed', 'incomplete', 'failed', 'cancelled', 'waiting'])
const uuid = /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i

export function validChatActivity(value, ownerId) {
  return Boolean(value && value.ownerId === ownerId && uuid.test(value.taskId)
    && (value.sessionId === null || uuid.test(value.sessionId)) && phases.has(value.phase))
}
export function reduceChatActivity(current, event, ownerId, viewingConversation) {
  if (!validChatActivity(event, ownerId)) return current
  if (current && event.taskId !== current.taskId && event.phase !== 'running') return current
  if (current?.taskId === event.taskId && current.phase === event.phase
    && current.sessionId === event.sessionId) return current
  if (current?.taskId === event.taskId && ['completed', 'incomplete', 'failed', 'cancelled'].includes(current.phase)
    && event.phase === 'running') return current
  return {ownerId, taskId: event.taskId, sessionId: event.sessionId, phase: event.phase,
    unread: event.phase !== 'running' && !viewingConversation}
}
export function readChatActivity(storage, ownerId) {
  if (!ownerId) return null
  try {
    const value = JSON.parse(storage.getItem(`veridra-chat-activity:${ownerId}`) || 'null')
    return validChatActivity(value, ownerId) ? {ownerId, taskId: value.taskId,
      sessionId: value.sessionId, phase: value.phase, unread: value.unread === true} : null
  } catch { return null }
}
export function saveChatActivity(storage, value) {
  if (!value || !validChatActivity(value, value.ownerId)) return
  const {ownerId, taskId, sessionId, phase, unread} = value
  try { storage.setItem(`veridra-chat-activity:${ownerId}`, JSON.stringify({ownerId, taskId, sessionId, phase, unread})) } catch { /* Optional. */ }
}
export function chatActivityCopy(phase) {
  return ({
    running: {title: 'Đang xử lý câu hỏi', text: 'Bạn cứ làm việc khác. Mình sẽ báo khi có kết quả.', action: 'Xem tiến độ'},
    completed: {title: 'Có câu trả lời mới', text: 'Mình đã nhận được kết quả. Bạn có thể mở lại để xem.', action: 'Xem câu trả lời'},
    incomplete: {title: 'Bản nháp cần kiểm tra', text: 'Đã có nội dung, nhưng còn điểm chưa được xác nhận.', action: 'Xem bản nháp'},
    failed: {title: 'Yêu cầu chưa hoàn tất', text: 'Có lỗi khi xử lý. Mở cuộc trò chuyện để xem chi tiết.', action: 'Xem lỗi'},
    cancelled: {title: 'Yêu cầu đã dừng', text: 'Bạn đã dừng yêu cầu. Có thể xem lại nội dung trong trò chuyện.', action: 'Mở cuộc trò chuyện'},
    waiting: {title: 'Chưa xác nhận được kết quả', text: 'Chưa nhận đủ trạng thái từ máy chủ. Không cần gửi lại ngay.', action: 'Kiểm tra yêu cầu'},
  })[phase] || {title: 'Sẵn sàng hỗ trợ', text: 'Chọn việc bạn muốn làm.', action: 'Mở trò chuyện'}
}
