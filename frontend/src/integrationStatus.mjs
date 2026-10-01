const GOOGLE_INTEGRATIONS = new Set(['drive', 'gmail'])
const DRIVE_READ_SCOPES = new Set([
  'https://www.googleapis.com/auth/drive.readonly',
  'https://www.googleapis.com/auth/drive',
])
const GMAIL_READ_SCOPES = new Set([
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/gmail.modify',
  'https://mail.google.com/',
])

/** Resolve only Workspace API paths; a similar-looking path must not affect badges. */
export function integrationFor(path) {
  const pathname = path.split(/[?#]/, 1)[0] ?? path
  if (pathname.startsWith('/api/drive/')) return 'drive'
  if (pathname === '/api/gmail' || pathname.startsWith('/api/gmail/')) return 'gmail'
  return null
}

/**
 * Distinguish Google/provider failures from app authentication and RBAC failures.
 * A bare HTTP 401/403 is not proof that Google itself is unavailable.
 */
export function hasDriveReadScope(scopes) {
  return Array.isArray(scopes) && scopes.some((scope) => DRIVE_READ_SCOPES.has(scope))
}

export function hasGmailReadScope(scopes) {
  return Array.isArray(scopes) && scopes.some((scope) => GMAIL_READ_SCOPES.has(scope))
}

/** Classify only known provider failures; bare HTTP status codes may be app/RBAC errors. */
export function integrationFailureStatus(service, code, _httpStatus) {
  if (!GOOGLE_INTEGRATIONS.has(service) || typeof code !== 'string') return null
  if (code === 'google_connection_error') return 'degraded'
  if (code === 'google_workspace_permission_denied') return 'permission'
  if (service === 'gmail') {
    if (code === 'gmail_insufficient_permissions') return 'permission'
    if (code === 'gmail_api_disabled') return 'misconfigured'
    if (code === 'gmail_error' || /^gmail_(408|429|5\d\d)$/.test(code)) return 'degraded'
    return null
  }
  if (code === 'google_drive_401' || code === 'google_drive_403') return 'permission'
  if (/^google_drive_(408|429|5\d\d)$/.test(code)) return 'degraded'
  return null
}
