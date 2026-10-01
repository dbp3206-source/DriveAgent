export type EmailAction = 'draft' | 'send'

export interface EmailActionConfig {
  prepareEndpoint: string
  approveEndpoint: string
  pendingLabel: string
  actionLabel: string
  busyLabel: string
  successLabel: string
}

export const EMAIL_ACTIONS: Readonly<Record<EmailAction, Readonly<EmailActionConfig>>>
export function emailActionConfig(action: EmailAction): Readonly<EmailActionConfig>
export function roleCanCreateDraft(role: string): boolean
export function roleCanSendEmail(role: string): boolean
