export const EMAIL_ACTIONS = Object.freeze({
  draft: Object.freeze({
    prepareEndpoint: '/api/gmail/draft',
    approveEndpoint: '/api/gmail/draft/approve',
    pendingLabel: 'Chờ xác nhận lưu nháp (2-Phase)',
    actionLabel: 'Lưu bản nháp vào Gmail',
    busyLabel: 'Đang lưu bản nháp…',
    successLabel: 'Bản nháp đã được lưu trong Gmail. Chưa có email nào được gửi.',
  }),
  send: Object.freeze({
    prepareEndpoint: '/api/gmail/prepare',
    approveEndpoint: '/api/gmail/approve',
    pendingLabel: 'Chờ xác nhận gửi (2-Phase)',
    actionLabel: 'Xác nhận gửi email này',
    busyLabel: 'Đang gửi email…',
    successLabel: 'Email đã được gửi thành công qua tài khoản Gmail của bạn.',
  }),
})

export function emailActionConfig(action) {
  return EMAIL_ACTIONS[action] ?? EMAIL_ACTIONS.draft
}

export function roleCanCreateDraft(role) {
  return role === 'editor' || role === 'owner' || role === 'super_admin'
}

export function roleCanSendEmail(role) {
  return role === 'owner' || role === 'super_admin'
}
