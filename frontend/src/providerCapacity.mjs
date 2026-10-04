const SOURCE_LABELS = {
  user: 'khóa người dùng',
  environment: 'khóa môi trường',
  unconfigured: 'chưa cấu hình',
}

/**
 * Return the credential name represented by the latest capacity snapshot.
 * This is deliberately phrased as a snapshot: it does not claim that the
 * credential served a particular request.
 */
export function effectiveCredentialLabel(capacity) {
  if (!capacity) return 'chưa có thông tin'
  const name = String(capacity.display_name || SOURCE_LABELS[capacity.credential_source] || 'khóa hiệu lực')
  return `${name}${capacity.failover_active ? ' · dự phòng' : ''}`
}

/**
 * Compact label for the composer. The count is Veridra's local model-call
 * safety ledger, not Google's remaining quota or a count of user questions.
 */
export function capacityPillLabel(capacity) {
  const budget = capacity?.local_budget
  if (!budget) return null
  return `${effectiveCredentialLabel(capacity)} · ${budget.daily_remaining}/${budget.daily_limit} lượt mô hình`
}

export const CAPACITY_HELP_TEXT =
  'Ngân sách bảo vệ của Veridra, không phải số dư Google. Một câu hỏi có thể dùng nhiều lượt mô hình.'
