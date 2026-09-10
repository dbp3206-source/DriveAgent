/** Fetch wrapper duy nhất để cookie, JSON và lỗi API được xử lý nhất quán. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message)
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  let response: Response
  try {
    response = await fetch(path, { ...init, headers, credentials: 'include' })
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') throw caught
    throw new ApiError('Mất kết nối với ứng dụng. Kiểm tra server local còn chạy rồi thử lại.', 0, 'network_error')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail
      : response.status === 422 ? 'Dữ liệu chưa hợp lệ. Hãy kiểm tra các trường rồi thử lại.'
        : `Yêu cầu không thành công (HTTP ${response.status}).`
    throw new ApiError(detail, response.status, body.code)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function formatDate(value: string | null): string {
  if (!value) return 'Không rõ'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
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
