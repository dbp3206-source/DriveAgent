export function canRenderGmailThread(messages: Array<{
  presentation_mode?: string
  body?: string
  html_body?: string
  attachments?: unknown[]
}>): boolean
export function attachmentUrl(messageId: string, attachmentId: string, inline?: boolean): string
export function externalImageFetchPlan(messageId: string, sources?: Record<string, string>): Array<[string, string]>
export function normalizeContentId(value: string): string
export function rewriteEmailCssImageUrls(
  source: string,
  inlineVariableForContentId: (contentId: string) => string | null | undefined,
): { css: string; remoteImageCount: number }
export function inlineImageFetchPlan(attachments: Array<{
  inline?: boolean
  content_id?: string | null
  attachment_id?: string | null
  data_base64?: string
  mime_type?: string
}>): Array<{ contentId: string; attachmentId: string }>
