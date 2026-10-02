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

type ApiRequestInit = RequestInit & { timeoutMs?: number }
type ResponseMode = 'json' | 'text' | 'blob'

export function api<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  return requestBounded<T>(path, init, 'json')
}

export function apiText(path: string, init: ApiRequestInit = {}): Promise<string> {
  return requestBounded<string>(path, init, 'text')
}

export function apiBlob(path: string, init: ApiRequestInit = {}): Promise<Blob> {
  return requestBounded<Blob>(path, init, 'blob')
}

/** Giới hạn cả lấy phản hồi lẫn đọc nội dung; không tự phát lại thao tác ghi. */
async function requestBounded<T>(path: string, init: ApiRequestInit, mode: ResponseMode): Promise<T> {
  const { timeoutMs, signal: callerSignal, ...requestInit } = init
  const defaultTimeout = path.startsWith('/api/auth/') || init.body instanceof FormData || init.body instanceof Blob
    ? 120_000 : 30_000
  const duration = timeoutMs ?? defaultTimeout
  if (!Number.isFinite(duration) || duration <= 0) {
    throw new RangeError('Thời hạn chờ phải là số dương hữu hạn.')
  }
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  let cancel: (() => void) | undefined
  const interrupted = new Promise<never>((_resolve, reject) => {
    cancel = () => {
      controller.abort()
      reject(new DOMException('Yêu cầu đã được hủy.', 'AbortError'))
    }
    if (callerSignal?.aborted) cancel()
    else callerSignal?.addEventListener('abort', cancel, { once: true })
    timer = setTimeout(() => {
      controller.abort()
      reject(new ApiError(
        'Ứng dụng chưa phản hồi kịp. Hãy kiểm tra trạng thái tác vụ trước khi thử lại; thao tác vừa rồi có thể vẫn đang xử lý.',
        0, 'request_timeout',
      ))
    }, duration)
  })
  try {
    if (callerSignal?.aborted) return await interrupted
    return await Promise.race([
      interrupted,
      executeApi<T>(path, { ...requestInit, signal: controller.signal }, mode),
    ])
  } finally {
    clearTimeout(timer)
    if (cancel) callerSignal?.removeEventListener('abort', cancel)
  }
}

async function executeApi<T>(path: string, init: RequestInit, mode: ResponseMode): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Requested-With', 'XMLHttpRequest')
  if (init.body && !(init.body instanceof FormData) && !(init.body instanceof Blob) && !headers.has('Content-Type')) {
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
  if (mode === 'text') return response.text() as Promise<T>
  if (mode === 'blob') return response.blob() as Promise<T>
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
