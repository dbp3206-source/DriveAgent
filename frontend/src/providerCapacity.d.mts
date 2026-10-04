export function effectiveCredentialLabel(capacity: {
  credential_source?: string | null
  display_name?: string | null
  failover_active?: boolean
} | null | undefined): string

export function capacityPillLabel(capacity: {
  credential_source?: string | null
  display_name?: string | null
  failover_active?: boolean
  local_budget?: {
    daily_remaining: number
    daily_limit: number
  } | null
} | null | undefined): string | null

export const CAPACITY_HELP_TEXT: string

