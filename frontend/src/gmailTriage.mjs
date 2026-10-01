const AUTOMATED = /(?:no[-_. ]?reply|do[-_. ]?not[-_. ]?reply|notification|newsletter|digest|mailer-daemon|updates?@)/i
// Newsletter platforms often use a human-looking local part (for example
// bytebytego@substack.com), so sender-name/no-reply checks alone are not enough.
const BULK_SENDER_HOST = /@(?:[a-z0-9-]+\.)*(?:substack\.com|medium\.com|redditmail\.com|morningbrew\.com)>?$/i
const BULK_CONTENT = /(?:unsubscribe|hủy đăng ký|bản tin|newsletter|weekly digest|khuyến mãi|promotion|thông báo tự động)/i
const ACTION_LANGUAGE = /(?:\?|vui lòng|xin bạn|bạn có thể|phản hồi|trả lời|xác nhận|duyệt|góp ý|deadline|hạn chót|action required|please reply|please confirm|review requested)/i

/** Conservative deterministic triage: false positives are more costly than omissions. */
export function classifyReplyNeed(message) {
  const sender = String(message?.sender || '')
  const content = `${message?.subject || ''} ${message?.snippet || ''}`
  if (AUTOMATED.test(sender) || BULK_SENDER_HOST.test(sender) || BULK_CONTENT.test(content)) {
    return {needsReply: false, reason: 'Email tự động hoặc bản tin'}
  }
  if (ACTION_LANGUAGE.test(content)) {
    return {needsReply: true, reason: 'Có câu hỏi hoặc yêu cầu hành động trực tiếp'}
  }
  return {needsReply: false, reason: 'Chưa thấy yêu cầu phản hồi rõ ràng'}
}
