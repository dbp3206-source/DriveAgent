const supportedModes = new Set(['faithful_text', 'readable_text', 'safe_html', 'calendar_text'])

export function canRenderGmailThread(messages) {
  return Array.isArray(messages) && messages.length > 0 && messages.every((message) =>
    (supportedModes.has(message?.presentation_mode) && (
      (typeof message?.body === 'string' && message.body.trim().length > 0) ||
      (message?.presentation_mode === 'safe_html' && typeof message?.html_body === 'string' && message.html_body.trim().length > 0)
    )) || (message?.presentation_mode === 'unsupported' && (
      Boolean(message?.body?.trim()) || Boolean(message?.attachments?.length)
    ))
  )
}

export function attachmentUrl(messageId, attachmentId, inline = false) {
  const base = `/api/gmail/messages/${encodeURIComponent(messageId)}/attachments/${encodeURIComponent(attachmentId)}`
  return inline ? `${base}?inline=true` : base
}

export function normalizeContentId(value) {
  let contentId = String(value ?? '').trim().replace(/^cid:/i, '').trim().replace(/^<|>$/g, '').trim()
  try {
    contentId = decodeURIComponent(contentId)
  } catch {
    // Keep malformed provider values literal; they will simply fail to match.
  }
  return contentId.toLowerCase()
}

export function rewriteEmailCssImageUrls(source, inlineVariableForContentId) {
  let remoteImageCount = 0
  const css = String(source ?? '').replace(
    /url\(\s*(?:(['"])(.*?)\1|([^)]*?))\s*\)/gi,
    (original, _quote, quotedValue, bareValue) => {
      const url = String(quotedValue ?? bareValue ?? '').trim()
      if (/^cid:/i.test(url)) {
        const variable = inlineVariableForContentId(normalizeContentId(url))
        return variable ? `var(${variable})` : 'none'
      }
      if (/^(?:https?:)?\/\//i.test(url)) remoteImageCount += 1
      return original
    },
  )
  return { css, remoteImageCount }
}

export function inlineImageFetchPlan(attachments) {
  const seen = new Set()
  return (attachments || []).flatMap((item) => {
    const contentId = normalizeContentId(item?.content_id)
    const attachmentId = item?.attachment_id
    if (!item?.inline || !contentId || !attachmentId || item?.data_base64 ||
      !/^image\/(png|jpeg|gif|webp|avif|bmp)$/i.test(item?.mime_type || '') || seen.has(contentId)) return []
    seen.add(contentId)
    return [{ contentId, attachmentId }]
  })
}
