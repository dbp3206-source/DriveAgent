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
  google_oauth_configured: boolean
  vector_store: string
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
}

export interface Citation {
  file_id: string
  file_name: string
  chunk_index: number
  snippet: string
  web_view_link: string | null
  score: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  trace: Array<Record<string, unknown>>
  created_at: string
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
