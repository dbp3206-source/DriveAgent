export type Role = 'super_admin' | 'owner' | 'editor' | 'viewer'

export interface User {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  role: Role
  scopes: string[]
}

export interface AuthStatus {
  authenticated: boolean
  oauth_configured: boolean
  gemini_configured: boolean
  demo_login_enabled: boolean
  user: User | null
}

export interface Health {
  status: 'ok' | 'degraded'
  database: boolean
  gemini_configured: boolean
  gemini_connectivity: 'not_probed'
  google_oauth_configured: boolean
  google_workspace_connectivity: 'not_probed'
  vector_store: string
  gemini_chat_model: string
  gemini_fallback_model: string
  gemini_embedding_model: string
  embedding_dimensions: number
  runtime_started_at?: string | null
  runtime_pid?: number | null
}

export interface ProviderCapacity {
  configured: boolean
  credential_source: 'user' | 'environment' | 'unconfigured'
  active_credential_id: string | null
  active_display_name: string | null
  effective_credential_id: string | null
  display_name: string | null
  project_alias: string | null
  fingerprint: string | null
  failover_active: boolean
  primary_model: string
  fallback_model: string
  local_budget: {
    bucket: string
    minute_used: number
    minute_limit: number
    minute_tokens_used: number
    minute_tokens_limit: number
    daily_used: number
    daily_limit: number
    daily_remaining: number
    resets_at: string
    scope: string
  } | null
  circuits: Array<{
    capability: string
    consecutive_failures: number
    circuit_open: boolean
    retry_after_seconds: number
    last_error_class: string | null
  }>
  provider_balance_available: false
  provider_balance_note: string
}

export interface DriveFile {
  id: string
  name: string
  mime_type: string
  modified_time: string | null
  size: string | null
  web_view_link: string | null
  owners: string[]
  indexed: boolean
  index_status: 'not_indexed' | 'fresh' | 'stale'
}

export interface Citation {
  file_id: string
  file_name: string
  chunk_index: number
  page_number?: number | null
  snippet: string
  web_view_link: string | null
  score: number
}

export interface ChatMessage {
  proposals?: import('./components/CreationProposal').Proposal[]
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  trace: Array<Record<string, unknown>>
  status?: 'running' | 'completed' | 'incomplete' | 'failed' | 'cancelled'
  created_at: string
  latency_ms?: number
}

export interface ChatSession {
  id: string
  title: string
  summary: string | null
  created_at: string
  updated_at: string
}

export type MemoryKind =
  | 'fact'
  | 'preference'
  | 'context'
  | 'episodic'
  | 'procedural'
  | 'summary'

export interface MemoryItem {
  id: string
  kind: MemoryKind
  content: string
  tags: string[]
  confidence: number
  is_archived: boolean
  created_at: string
  updated_at: string
}

export interface AuditEvent {
  id: string
  request_id: string
  user_email: string | null
  role: string | null
  tool_name: string
  arguments: Record<string, unknown>
  result: Record<string, unknown>
  status: string
  latency_ms: number | null
  error_type: string | null
  error_message: string | null
  created_at: string
}
