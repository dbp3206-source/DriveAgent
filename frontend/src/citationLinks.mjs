/** Choose a reader from the actual source, never interpret a web URL as a Drive ID. */
export function citationHref(citation) {
  if (citation.file_id.startsWith('memory:')) {
    return { href: '/#/memory', title: 'Xem bộ nhớ đã lưu của bạn' }
  }
  const isLocal = citation.file_id.startsWith('local:')
  const isGmail = citation.web_view_link?.startsWith('https://mail.google.com/')
  const isWeb = citation.file_id.startsWith('https://')
  if (isWeb) {
    try {
      const url = new URL(citation.file_id)
      if (url.protocol === 'https:' && !url.username && !url.password) {
        return { href: url.href, title: 'Mở trang nguồn trên Internet' }
      }
    } catch { /* Invalid source stays in the guarded in-app reader. */ }
  }
  if ((isGmail || isLocal) && citation.web_view_link) {
    return {
      href: citation.web_view_link,
      title: isGmail ? 'Mở đúng chuỗi email trong Gmail' : 'Mở nội dung nguồn local',
    }
  }
  return {
    href: `/#/drive?file=${encodeURIComponent(citation.file_id)}${citation.page_number ? `&page=${citation.page_number}` : ''}`,
    title: 'Mở đúng đoạn nguồn trong trình đọc Veridra',
  }
}
