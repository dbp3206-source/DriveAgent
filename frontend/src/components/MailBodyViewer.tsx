import DOMPurify from 'dompurify'
import { Button, Tooltip } from '@fluentui/react-components'
import { Checkmark16Regular, Copy16Regular, Open16Regular } from '@fluentui/react-icons'
import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { attachmentUrl, inlineImageFetchPlan, normalizeContentId, rewriteEmailCssImageUrls } from '../gmailPresentation.mjs'

export function SenderAvatar({ sender }: { sender: string }) {
  const clean = sender.replace(/<.*?>/, '').trim()
  return <div className="sender-avatar" aria-hidden="true">{(clean[0] || '?').toUpperCase()}</div>
}

type MailAttachment = {
  filename: string
  mime_type: string
  size: number
  attachment_id?: string | null
  content_id?: string | null
  inline?: boolean
  data_base64?: string
}

function safeHtmlDocument(
  source: string,
  messageId: string,
  attachments: MailAttachment[],
  allowExternalImages: boolean,
  inlineImageData: Record<string, string>,
) {
  const sanitized = DOMPurify.sanitize(source, {
    USE_PROFILES: { html: true },
    ADD_TAGS: ['style'],
    WHOLE_DOCUMENT: true,
    ADD_ATTR: ['style', 'align', 'valign', 'bgcolor', 'width', 'height', 'border', 'cellpadding', 'cellspacing', 'colspan', 'rowspan', 'target', 'rel'],
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'meta', 'base', 'link', 'svg', 'math', 'audio', 'video', 'canvas'],
    FORBID_ATTR: ['srcset', 'onerror', 'onload'],
    // DOMPurify's default FORBID_CONTENTS removes all <style> text, including
    // harmless email layout CSS. Keep its dangerous-content defaults explicitly
    // (excluding only style) so email layout survives sanitization.
    FORBID_CONTENTS: ['annotation-xml', 'audio', 'colgroup', 'desc', 'foreignobject', 'head', 'iframe', 'math', 'mi', 'mn', 'mo', 'ms', 'mtext', 'noembed', 'noframes', 'noscript', 'plaintext', 'script', 'selectedcontent', 'svg', 'template', 'thead', 'title', 'video', 'xmp'],
  }).toString()
  const doc = new DOMParser().parseFromString(sanitized, 'text/html')
  const inlineAttachments = attachments.filter(item => item.inline && item.content_id)
  const cssVariables = new Map<string, string>()
  const cssVariableValues: string[] = []
  const inlineImageSource = (cid: string) => {
    const match = inlineAttachments.find(item => normalizeContentId(item.content_id || '') === cid)
    if (!/^image\/(png|jpeg|gif|webp|avif|bmp)$/i.test(match?.mime_type || '')) return ''
    if (match?.data_base64) return `data:${match.mime_type};base64,${match.data_base64}`
    return inlineImageData[cid] || ''
  }
  const inlineCssVariable = (cid: string) => {
    const source = inlineImageSource(cid)
    if (!source) return ''
    const previous = cssVariables.get(cid)
    if (previous) return previous
    const variable = `--driveagent-inline-image-${cssVariables.size}`
    cssVariables.set(cid, variable)
    cssVariableValues.push(`${variable}: url("${source}")`)
    return variable
  }
  let remoteCssImageCount = 0
  for (const image of Array.from(doc.querySelectorAll('img'))) {
    image.removeAttribute('srcset')
    const original = (image.getAttribute('src') || '').trim()
    if (/^cid:/i.test(original)) {
      const cid = normalizeContentId(original)
      const source = inlineImageSource(cid)
      if (source) {
        image.setAttribute('src', source)
      } else {
        image.removeAttribute('src')
        image.setAttribute('alt', image.getAttribute('alt') || 'Ảnh đính kèm chưa tải được; mở Gmail để xem ảnh gốc')
      }
    } else if (/^https:\/\//i.test(original) || /^http:\/\//i.test(original) || original.startsWith('//')) {
      const remote = original.startsWith('//') ? `https:${original}` : original
      if (/^https:\/\//i.test(remote)) image.setAttribute('data-remote-src', remote)
      image.removeAttribute('src')
    } else if (/^data:image\/(?:png|jpeg|gif|webp|avif|bmp);base64,/i.test(original)) {
      image.setAttribute('src', original)
    } else {
      image.removeAttribute('src')
    }
    if (image.hasAttribute('data-remote-src') && allowExternalImages) {
      image.setAttribute('src', image.getAttribute('data-remote-src') || '')
    }
    // The sandboxed srcDoc is a fixed-height nested viewport. Lazy-loaded
    // newsletter images beyond its initial viewport can otherwise remain blank
    // indefinitely, so request every approved image as soon as the mail opens.
    image.setAttribute('loading', 'eager')
    image.setAttribute('referrerpolicy', 'no-referrer')
  }
  for (const element of Array.from(doc.querySelectorAll('[style], style'))) {
    const currentCss = element.tagName.toLowerCase() === 'style'
      ? element.textContent || ''
      : element.getAttribute('style') || ''
    const rewritten = rewriteEmailCssImageUrls(currentCss, inlineCssVariable)
    remoteCssImageCount += rewritten.remoteImageCount
    if (element.tagName.toLowerCase() === 'style') element.textContent = rewritten.css
    else element.setAttribute('style', rewritten.css)
  }
  for (const style of Array.from(doc.querySelectorAll('style'))) {
    if (style.parentElement !== doc.body) doc.body.insertBefore(style, doc.body.firstChild)
  }
  if (cssVariableValues.length) {
    const style = doc.createElement('style')
    style.textContent = `:root { ${cssVariableValues.join('; ')}; }`
    doc.body.insertBefore(style, doc.body.firstChild)
  }
  if (remoteCssImageCount) doc.body.setAttribute('data-remote-css-image-count', String(remoteCssImageCount))
  for (const link of Array.from(doc.querySelectorAll('a'))) {
    link.setAttribute('target', '_blank')
    link.setAttribute('rel', 'noopener noreferrer')
  }

  const messagePath = `/api/gmail/messages/${encodeURIComponent(messageId)}/attachments/`
  const imageSource = `${window.location.origin}${messagePath}`
  const csp = [
    "default-src 'none'",
    `img-src data: ${imageSource}${allowExternalImages ? ' https:' : ''}`,
    "style-src 'unsafe-inline'",
    "font-src data:",
    "connect-src 'none'",
    "frame-src 'none'",
    "object-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
  ].join('; ')
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${csp}"><meta name="referrer" content="no-referrer"></head><body${remoteCssImageCount ? ` data-remote-css-image-count="${remoteCssImageCount}"` : ''}>${doc.body.innerHTML}</body></html>`
}

function ReadableLink({ href = '', children }: { href?: string; children?: React.ReactNode }) {
  const raw = typeof children === 'string' ? children.trim() : ''
  const label = raw || href
  return <Tooltip content={`Mở liên kết: ${href}`} relationship="description">
    <a href={href} target="_blank" rel="noopener noreferrer" className="mail-inline-link">
      {label.length > 72 ? `${label.slice(0, 72)}…` : label}
      <Open16Regular style={{ marginLeft: 4, fontSize: 12, opacity: .75 }} aria-hidden="true" />
    </a>
  </Tooltip>
}

export interface MailBodyViewerProps {
  body: string
  plainBody?: string
  htmlBody?: string
  mode?: 'faithful_text' | 'readable_text' | 'safe_html' | 'calendar_text' | 'unsupported'
  messageId: string
  attachments?: MailAttachment[]
}

export function MailBodyViewer({ body, plainBody = '', htmlBody = '', mode = 'readable_text', messageId, attachments = [] }: MailBodyViewerProps) {
  const hasHtml = Boolean(htmlBody.trim())
  const [viewMode, setViewMode] = useState<'html' | 'readable_text' | 'faithful_text'>(hasHtml ? 'html' : 'readable_text')
  // Gmail-like default: render external images on open; the reader still offers
  // a per-message block control because remote hosts can observe image requests.
  const [allowExternalImages, setAllowExternalImages] = useState(true)
  const [copied, setCopied] = useState(false)
  const inlinePlanKey = JSON.stringify(inlineImageFetchPlan(attachments))
  const inlineResultKey = `${messageId}:${inlinePlanKey}`
  const [inlineImageResult, setInlineImageResult] = useState<{ key: string; images: Record<string, string> }>({ key: '', images: {} })

  useEffect(() => {
    const plan = JSON.parse(inlinePlanKey) as Array<{ contentId: string; attachmentId: string }>
    if (!hasHtml || !plan.length) return
    const controller = new AbortController()
    void Promise.all(plan.map(async ({ contentId, attachmentId }) => {
      try {
        // Fetch from the authenticated parent page. A sandboxed srcDoc has an
        // opaque origin, so SameSite=Lax session cookies may not accompany its
        // own subresource requests to the otherwise same-origin attachment API.
        const response = await fetch(attachmentUrl(messageId, attachmentId, true), {
          credentials: 'same-origin',
          signal: controller.signal,
        })
        const mime = response.headers.get('content-type')?.split(';', 1)[0]?.trim() || ''
        if (!response.ok || !/^image\/(png|jpeg|gif|webp|avif|bmp)$/i.test(mime)) return null
        const blob = await response.blob()
        const dataUrl = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(String(reader.result || ''))
          reader.onerror = () => reject(reader.error)
          reader.readAsDataURL(blob)
        })
        return { contentId, dataUrl }
      } catch {
        return null
      }
    })).then(results => {
      if (controller.signal.aborted) return
      setInlineImageResult({
        key: inlineResultKey,
        images: Object.fromEntries(results
          .filter((item): item is { contentId: string; dataUrl: string } => Boolean(item))
          .map(item => [item.contentId, item.dataUrl])),
      })
    })
    return () => controller.abort()
  }, [hasHtml, inlinePlanKey, inlineResultKey, messageId])

  const inlineFetchCount = inlineImageFetchPlan(attachments).length
  const inlineReady = !inlineFetchCount || inlineImageResult.key === inlineResultKey
  const inlineFailedCount = inlineReady && inlineImageResult.key === inlineResultKey
    ? Math.max(0, inlineFetchCount - Object.keys(inlineImageResult.images).length)
    : 0

  const htmlDocument = useMemo(() => {
    if (!hasHtml) return ''
    return safeHtmlDocument(htmlBody, messageId, attachments, allowExternalImages, inlineImageResult.images)
  }, [allowExternalImages, attachments, hasHtml, htmlBody, inlineImageResult.images, messageId])
  const remoteImageCount = useMemo(() => {
    if (!htmlDocument) return 0
    const doc = new DOMParser().parseFromString(htmlDocument, 'text/html')
    const cssImages = Number.parseInt(doc.body.getAttribute('data-remote-css-image-count') || '0', 10)
    return doc.querySelectorAll('[data-remote-src]').length + (Number.isFinite(cssImages) ? cssImages : 0)
  }, [htmlDocument])

  const htmlTextFallback = useMemo(() => {
    if (!htmlDocument) return ''
    const doc = new DOMParser().parseFromString(htmlDocument, 'text/html')
    doc.querySelectorAll('style,script,meta').forEach(node => node.remove())
    return (doc.body.innerText || doc.body.textContent || '').replace(/\s+/g, ' ').trim()
  }, [htmlDocument])
  const textSource = plainBody.trim() || body.trim() || htmlTextFallback
  const normalizedBody = useMemo(() => textSource.replace(/\r\n?/g, '\n').trim(), [textSource])
  const rawBody = plainBody || body

  async function copyBody() {
    await navigator.clipboard.writeText(textSource || htmlBody)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const readableMime = mode === 'calendar_text' ? 'Lời mời lịch (iCalendar)' : 'Văn bản'
  return <div className="mail-body-viewer">
    <div className="mail-body-toolbar">
      <div className="mail-view-mode-tabs" role="tablist" aria-label="Định dạng email">
        {hasHtml ? <Button size="small" appearance={viewMode === 'html' ? 'primary' : 'subtle'} role="tab" aria-selected={viewMode === 'html'} onClick={() => setViewMode('html')}>HTML</Button> : null}
        <Button size="small" appearance={viewMode === 'readable_text' ? 'primary' : 'subtle'} role="tab" aria-selected={viewMode === 'readable_text'} onClick={() => setViewMode('readable_text')}>{readableMime}</Button>
        {hasHtml && Boolean(plainBody.trim()) ? <Button size="small" appearance={viewMode === 'faithful_text' ? 'primary' : 'subtle'} role="tab" aria-selected={viewMode === 'faithful_text'} onClick={() => setViewMode('faithful_text')}>Bản thô</Button> : null}
      </div>
      <Tooltip content={copied ? 'Đã sao chép vào bộ nhớ đệm' : 'Sao chép nội dung'} relationship="label">
        <Button size="small" appearance="subtle" icon={copied ? <Checkmark16Regular /> : <Copy16Regular />} onClick={() => void copyBody()}>{copied ? 'Đã chép' : 'Sao chép'}</Button>
      </Tooltip>
    </div>
    {viewMode === 'html' && hasHtml ? <>
      <div className="mail-security-banner">Bản HTML email đã được làm sạch và cô lập để chặn mã chủ động. Ảnh trong thư và ảnh ngoài được tải khi mở thư.</div>
      {inlineFailedCount > 0 ? <p className="mail-image-warning" role="alert">{inlineFailedCount} ảnh đính kèm chưa tải được. Mở thư gốc trong Gmail để xem đầy đủ.</p> : null}
      {remoteImageCount > 0 ? <Button className="mail-load-images" appearance="subtle" onClick={() => setAllowExternalImages(value => !value)}>{allowExternalImages ? 'Chặn ảnh ngoài' : `Tải ${remoteImageCount} ảnh ngoài`}</Button> : null}
      {allowExternalImages && remoteImageCount > 0 ? <p className="mail-image-warning" role="status">Ảnh ngoài đang được tải; máy chủ gửi ảnh có thể ghi nhận lượt xem.</p> : null}
      {inlineReady
        ? <iframe className="mail-html-frame" title="Nội dung HTML của email" sandbox="allow-popups" referrerPolicy="no-referrer" srcDoc={htmlDocument} />
        : <p className="mail-empty-note" role="status">Đang tải ảnh trong thư…</p>}
    </> : viewMode === 'faithful_text' ? <>
      <div className="mail-security-banner">Văn bản thuần nguyên bản do Gmail cung cấp; giữ nguyên chữ và xuống dòng.</div>
      <pre className="mail-faithful-text">{rawBody || '(Email không có phần văn bản thuần.)'}</pre>
    </> : <>
      <div className="mail-security-banner">{mode === 'calendar_text' ? 'Lời mời lịch iCalendar đã được chuyển thành các trường dễ đọc.' : hasHtml ? (plainBody.trim() ? 'Đang hiển thị phần văn bản thuần của email.' : 'Email này không có phần text/plain riêng; văn bản được trích xuất từ HTML để bạn đọc nhanh.') : mode === 'unsupported' ? 'Không có nội dung thân thư ở định dạng có thể hiển thị; hãy tải tệp đính kèm hoặc mở thư gốc trong Gmail.' : 'Văn bản trích xuất từ email; dùng Gmail để xem bố cục gốc đầy đủ.'}</div>
      {normalizedBody ? mode === 'calendar_text'
        ? <pre className="mail-faithful-text mail-calendar-text">{normalizedBody}</pre>
        : <div className="mail-readable-text markdown-body"><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={{ a: ({ href, children }) => <ReadableLink href={href}>{children}</ReadableLink> }}>{normalizedBody}</ReactMarkdown></div>
        : <p className="mail-empty-note">(Email không có phần văn bản để hiển thị.)</p>}
    </>}
    {attachments.length ? <div className="mail-attachments" aria-label="Tệp đính kèm">
      <strong>Tệp đính kèm ({attachments.length})</strong>
      {attachments.map((item, index) => {
        const details = <><span>{item.filename}</span><small>{item.mime_type} · {Math.max(1, Math.round(item.size / 1024))} KB{item.inline ? ' · ảnh trong thư' : ''}</small></>
        const previewableImage = !item.inline && /^image\/(png|jpeg|gif|webp|avif|bmp)$/i.test(item.mime_type)
        if (previewableImage && item.attachment_id) {
          return <div key={`${messageId}-${item.attachment_id}-${index}`} className="mail-attachment-card">
            <img src={attachmentUrl(messageId, item.attachment_id, true)} alt={`Ảnh đính kèm: ${item.filename}`} loading="lazy" referrerPolicy="no-referrer" />
            <a href={attachmentUrl(messageId, item.attachment_id)} className="mail-attachment-link">{details}</a>
          </div>
        }
        return item.attachment_id
          ? <a key={`${messageId}-${item.attachment_id}-${index}`} href={attachmentUrl(messageId, item.attachment_id)} className="mail-attachment-link">{details}</a>
          : <span key={`${messageId}-${item.content_id || item.filename}-${index}`} className="mail-attachment-link">{details}</span>
      })}
    </div> : null}
  </div>
}
