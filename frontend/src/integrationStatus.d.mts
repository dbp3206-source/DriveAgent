export type GoogleIntegration = 'drive' | 'gmail'
export type IntegrationFailureStatus = 'degraded' | 'permission' | 'misconfigured'

export function integrationFor(path: string): GoogleIntegration | null
export function hasDriveReadScope(scopes: string[] | undefined): boolean
export function hasGmailReadScope(scopes: string[] | undefined): boolean
export function integrationFailureStatus(
  service: GoogleIntegration,
  code: unknown,
  status: number,
): IntegrationFailureStatus | null
