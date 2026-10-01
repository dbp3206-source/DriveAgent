const GOOGLE_EXPORTABLE = new Set([
  'application/vnd.google-apps.document',
  'application/vnd.google-apps.spreadsheet',
  'application/vnd.google-apps.presentation',
  'application/vnd.google-apps.drawing',
])

const SUPPORTED_BINARY = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/json',
])

export function driveFileCapability(mimeType, fileName = '') {
  if (mimeType === 'application/vnd.google-apps.folder') {
    return { readable: false, indexable: false, previewMode: 'none', reason: 'Thư mục không có nội dung để lập chỉ mục.' }
  }
  if (mimeType.startsWith('image/')) {
    return { readable: false, indexable: false, previewMode: 'none', reason: 'Ảnh chỉ được mở tại nguồn Google Drive.' }
  }
  const supported = GOOGLE_EXPORTABLE.has(mimeType)
    || mimeType.startsWith('text/')
    || SUPPORTED_BINARY.has(mimeType)
    || fileName.toLocaleLowerCase().endsWith('.ipynb')
  return supported
    ? { readable: false, indexable: true, previewMode: 'none', reason: '' }
    : {
        readable: false,
        indexable: false,
        previewMode: 'none',
        reason: 'Định dạng này chưa được Veridra hỗ trợ lập chỉ mục.',
      }
}
