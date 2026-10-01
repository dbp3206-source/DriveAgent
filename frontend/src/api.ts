import { integrationFailureStatus, integrationFor } from './integrationStatus.mjs'

/** Fetch wrapper duy nhất để cookie, JSON và lỗi API được xử lý nhất quán. */
export class ApiError extends Error {
  status: number
  code?: string
  requestId?: string

  constructor(
    message: string,
    status: number,
    code?: string,
    requestId?: string,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

type IntegrationStatus = 'healthy' | 'degraded' | 'permission' | 'misconfigured'

function publishIntegrationStatus(path: string, status: IntegrationStatus) {
  const service = integrationFor(path)
  if (!service || typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('driveagent:integration-status', { detail: { service, status } }))
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Requested-With', 'XMLHttpRequest')
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  let response: Response
  try {
    response = await fetch(path, { ...init, headers, credentials: 'include' })
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') throw caught
    // This failure is between the browser and the local app. It does not prove
    // that Google itself is degraded; provider status changes only from a
    // response carrying a recognized Google-specific error code.
    throw new ApiError('Chưa kết nối được ứng dụng. Máy chủ có thể đang khởi động lại; hãy thử lại sau ít phút.', 0, 'network_error')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const service = integrationFor(path)
    const integrationStatus = service
      ? integrationFailureStatus(service, body.code, response.status)
      : null
    if (integrationStatus) publishIntegrationStatus(path, integrationStatus)
    const validationDetail = Array.isArray(body.detail)
      ? body.detail.map((item: { loc?: unknown[]; msg?: string }) => {
          const location = Array.isArray(item.loc) ? item.loc.filter(Boolean).join('.') : ''
          return location ? `${location}: ${item.msg ?? 'không hợp lệ'}` : (item.msg ?? 'Dữ liệu không hợp lệ')
        }).join('; ')
      : ''
    const detail = typeof body.detail === 'string' ? body.detail
      : validationDetail || (typeof body.message === 'string' ? body.message : '')
        || (response.status === 422 ? 'Dữ liệu chưa hợp lệ. Hãy kiểm tra các trường rồi thử lại.'
          : `Yêu cầu không thành công (HTTP ${response.status}).`)
    const rawRequestId = response.headers.get('X-Request-ID')
    const requestId = rawRequestId && /^[A-Za-z0-9_-]{1,64}$/.test(rawRequestId)
      ? rawRequestId
      : undefined
    const message = requestId ? `${detail} (Mã yêu cầu: ${requestId})` : detail
    throw new ApiError(message, response.status, body.code, requestId)
  }
  publishIntegrationStatus(path, 'healthy')
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function formatDate(value: string | null): string {
  if (!value) return 'Không rõ'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không rõ'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function humanFileSize(value: string | null): string {
  const bytes = Number(value)
  if (!value || Number.isNaN(bytes)) return 'Không rõ'
  const units = ['B', 'KB', 'MB', 'GB']
  let amount = bytes
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024
    unit += 1
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}
