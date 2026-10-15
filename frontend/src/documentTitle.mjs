/** A proposed filename is editable, never authoritative model metadata. */
export function suggestedDocumentTitle(content) {
  const first = String(content ?? '').split('\n').find(line => line.trim()) ?? ''
  const text = first.replace(/^#+\s*/, '').replace(/[*_`]/g, '').trim().slice(0, 150)
  return text ? `Veridra: ${text}` : 'Tài liệu Veridra'
}

export function validatedDocumentTitle(value) {
  const title = String(value ?? '').trim()
  if (!title || title.length > 200 || /[\x00-\x1f\x7f]/.test(title)) {
    throw new Error('Tên tài liệu cần từ 1 đến 200 ký tự, trên một dòng.')
  }
  return title
}
