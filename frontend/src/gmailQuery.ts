export const GMAIL_STATUSES = [
  {id: 'all', label: 'Tất cả', query: ''},
  {id: 'unread', label: 'Chưa đọc', query: 'is:unread'},
  {id: 'read', label: 'Đã đọc', query: 'is:read'},
] as const

export const GMAIL_PERIODS = [
  {id: '1d', label: '1 ngày', query: 'newer_than:1d'},
  {id: '3d', label: '3 ngày', query: 'newer_than:3d'},
  {id: '7d', label: '1 tuần', query: 'newer_than:7d'},
  {id: '30d', label: '1 tháng', query: 'newer_than:30d'},
  {id: 'all', label: 'Mọi thời điểm', query: ''},
] as const

export const GMAIL_SCOPES = [
  {id: 'inbox', label: 'Hộp thư đến', query: 'in:inbox'},
  {id: 'sent', label: 'Đã gửi', query: 'in:sent'},
  {id: 'everywhere', label: 'Toàn bộ thư', query: ''},
] as const

type QueryOptions = {status?: string; period?: string; scope?: string; userQuery?: string; attachments?: boolean}

export function buildGmailQuery({status = 'all', period = '7d', scope = 'inbox', userQuery = '', attachments = false}: QueryOptions = {}) {
  const parts: string[] = []
  const selectedStatus = GMAIL_STATUSES.find(item => item.id === status)
  const selectedPeriod = GMAIL_PERIODS.find(item => item.id === period)
  const selectedScope = GMAIL_SCOPES.find(item => item.id === scope)
  for (const value of [selectedScope?.query, selectedStatus?.query, selectedPeriod?.query]) if (value) parts.push(value)
  if (attachments) parts.push('has:attachment')
  const cleanUserQuery = String(userQuery || '').trim()
  if (cleanUserQuery) parts.push(cleanUserQuery)
  return parts.join(' ').trim() || 'newer_than:7d'
}

export function filterLabel({status = 'all', period = '7d', scope = 'inbox', attachments = false}: QueryOptions = {}) {
  const labels = [GMAIL_SCOPES.find(item => item.id === scope)?.label, GMAIL_STATUSES.find(item => item.id === status)?.label, GMAIL_PERIODS.find(item => item.id === period)?.label].filter(Boolean) as string[]
  if (attachments) labels.push('Có tệp')
  return labels.join(' · ')
}
