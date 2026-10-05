// Only opaque request identifiers are retained; never document text or credentials.
function slot(ownerId, messageId) {
  if (!ownerId || !messageId) throw new Error('Chưa xác định được tài khoản. Hãy đăng nhập lại.')
  return `veridra:doc-preview:${encodeURIComponent(ownerId)}:${encodeURIComponent(messageId)}`
}

export function documentPreviewKey(storage, ownerId, messageId) {
  const name = slot(ownerId, messageId)
  const key = storage.getItem(name) ?? `doc-export-${messageId}`
  if (!/^[A-Za-z0-9_-]{8,100}$/.test(key)) throw new Error('Mã bản xem trước không hợp lệ.')
  return key
}

export async function renewDocumentPreviewKey(storage, ownerId, messageId, operationId, readStatus) {
  const status = await readStatus(operationId)
  if (status.state !== 'expired') {
    throw new Error('Bản xem trước chưa được xác nhận hết hạn. Hãy kiểm tra trạng thái; không tạo lại để tránh ghi trùng.')
  }
  if (!/^[a-f0-9-]{36}$/.test(operationId)) throw new Error('Mã thao tác không hợp lệ.')
  // All retries/tabs renewing the same expired operation use the same server key.
  const key = `doc-repreview-${operationId}`
  const name = slot(ownerId, messageId)
  storage.setItem(name, key)
  if (storage.getItem(name) !== key) throw new Error('Chưa lưu được mã phục hồi. Không tạo bản mới; hãy thử lại.')
  return key
}
