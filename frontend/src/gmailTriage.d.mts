export function classifyReplyNeed(message: {
  sender?: string
  subject?: string
  snippet?: string
}): {needsReply: boolean; reason: string}
