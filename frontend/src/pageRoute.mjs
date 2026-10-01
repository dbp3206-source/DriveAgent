export const PAGE_KEYS = Object.freeze([
  'home', 'chat', 'drive', 'gmail', 'local', 'artifacts', 'memory',
  'harness', 'audit', 'access', 'settings', 'skills',
])

export function pageFromHash(hash) {
  const candidate = String(hash || '')
    .replace(/^#\/?/, '')
    .split(/[/?]/, 1)[0]
    .trim()
  return PAGE_KEYS.includes(candidate) ? candidate : null
}

export function hashForPage(page) {
  if (!PAGE_KEYS.includes(page)) throw new Error(`Unknown DriveAgent page: ${page}`)
  return `#/${page}`
}
