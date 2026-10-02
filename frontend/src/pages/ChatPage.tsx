import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
  Textarea,
} from '@fluentui/react-components'
import {
  ArrowReset20Regular,
  ArrowTrendingLines20Regular,
  Bot16Regular,
  Brain16Regular,
  Calculator16Regular,
  Chat16Regular,
  Checkmark16Regular,
  ChevronUp16Regular,
  Copy20Regular,
  Delete16Regular,
  Dismiss16Regular,
  DismissCircle24Regular,
  DocumentBulletList20Regular,
  DocumentLink24Regular,
  DocumentText16Regular,
  Mail16Regular,
  Mail20Regular,
  Search20Regular,
  Send24Regular,
  Sparkle16Regular,
  Table16Regular,
  WeatherSunny16Regular,
} from '@fluentui/react-icons'
import { FormEvent, isValidElement, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, ApiError } from '../api'
import { waitForChatTask } from '../chatTaskPolling.mjs'
import { EmptyState, ErrorState } from '../components/AsyncState'
import { ExecutionTrace } from '../components/ExecutionTrace'
import { CreationProposal, type Proposal } from '../components/CreationProposal'
import {
  DocumentExportApproval,
  type PreparedDocumentExport,
} from '../components/DocumentExportApproval'
import { AVAILABLE_MODELS, type ModelOption } from '../modelOptions'
import { markdownToDocumentBlocks as parseMarkdownDocument } from '../documentMarkdown.js'
import { normalizeMathNotation } from '../markdownPresentation.mjs'
import { citationHref } from '../citationLinks.mjs'
import {
  DEFAULT_CHAT_CONTROLS,
  displaySessionTitle,
  filterSlashOptions,
  mergeChatControls,
  normalizeChatControls,
  slashOptions,
  type ChatControls,
  type SlashOption,
} from '../chatControls'
import { useResizable } from '../hooks/useResizable'
import { MermaidDiagram } from '../components/MermaidDiagram'

function formatRelativeTime(isoDate: string): string {
  if (!isoDate) return ''
  try {
    let normalized = isoDate.replace(' ', 'T')
    if (!normalized.endsWith('Z') && !/[+-]\d{2}(?::?\d{2})?$/.test(normalized)) {
      normalized += 'Z'
    }
    const time = new Date(normalized).getTime()
    if (Number.isNaN(time)) return ''
    const now = Date.now()
    const diff = Math.max(0, Math.floor((now - time) / 1000))
    if (diff < 60) return 'Vừa xong'
    if (diff < 3600) return `${Math.floor(diff / 60)}m`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`
    if (diff < 2592000) return `${Math.floor(diff / 86400)}d`
    return `${Math.floor(diff / 2592000)}mo`
  } catch {
    return ''
  }
}

import type { ChatMessage, ChatSession, Citation, ProviderCapacity } from '../types'

interface SessionTopicMeta {
  type: 'briefing' | 'mail' | 'sheets' | 'docs' | 'compute' | 'chat'
  label: string
  icon: React.ComponentType<{ className?: string }>
  accentClass: 'amber' | 'emerald' | 'cyan' | 'indigo' | 'violet'
}

function getSessionTopicMeta(title: string, id: string): SessionTopicMeta {
  const lower = (title || '').toLowerCase()
  if (/bản tin|briefing|thời tiết|tin tức/i.test(lower)) {
    return {
      type: 'briefing',
      label: 'Bản tin sáng',
      icon: WeatherSunny16Regular,
      accentClass: 'amber',
    }
  }
  if (/gmail|hộp thư|email|thư điện tử|quét thư/i.test(lower)) {
    return {
      type: 'mail',
      label: 'Gmail & Thư',
      icon: Mail16Regular,
      accentClass: 'amber',
    }
  }
  if (/sheet|bảng tính|excel|csv|xlsx|xls|bảng biểu/i.test(lower)) {
    return {
      type: 'sheets',
      label: 'Bảng tính',
      icon: Table16Regular,
      accentClass: 'emerald',
    }
  }
  if (/doc|tài liệu|drive|tệp|file|văn bản|pdf|hợp đồng/i.test(lower)) {
    return {
      type: 'docs',
      label: 'Tài liệu',
      icon: DocumentText16Regular,
      accentClass: 'cyan',
    }
  }
  if (/giả lập|mô phỏng|simulation/i.test(lower)) {
    return {
      type: 'compute',
      label: 'Giả lập AI',
      icon: Brain16Regular,
      accentClass: 'indigo',
    }
  }
  if (/tính toán|tính|toán|công thức|phân tích|thuật toán|kịch bản/i.test(lower)) {
    return {
      type: 'compute',
      label: 'Tính & Công thức',
      icon: Calculator16Regular,
      accentClass: 'indigo',
    }
  }

  // Fallback: deterministic variety based on session id or title
  const seed = (id || title || 'chat').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  const variants: SessionTopicMeta[] = [
    { type: 'chat', label: 'Hội thoại AI', icon: Sparkle16Regular, accentClass: 'cyan' },
    { type: 'chat', label: 'Trợ lý Veridra', icon: Bot16Regular, accentClass: 'violet' },
    { type: 'chat', label: 'Hỏi đáp AI', icon: Chat16Regular, accentClass: 'indigo' },
  ]
  return variants[seed % variants.length]!
}

interface ChatResult {
  proposals?: Proposal[]
  session_id: string
  message_id: string
  answer: string
  status: 'completed' | 'incomplete'
  citations: Citation[]
  trace: Array<Record<string, unknown>>
}

const prompts = [
  'Tìm hồ sơ khách hàng trong Drive; hỏi tên khách hàng nếu chưa đủ thông tin',
  'Tóm tắt tệp mới chỉnh sửa gần đây nhất',
  'Quét thư Gmail chưa đọc từ tối qua và tóm tắt',
  'Tôi đã lưu sở thích trình bày nào?',
]


interface ChatPageProps {
  onBusyChange?: (busy: boolean) => void
  isActive?: boolean
}

type FeedbackReason = 'incorrect' | 'missing_source' | 'hard_to_follow' | 'too_short' | 'too_long' | 'other'
const feedbackReasons: Array<{id: FeedbackReason; label: string}> = [
  {id: 'incorrect', label: 'Có thông tin sai'},
  {id: 'missing_source', label: 'Thiếu hoặc sai nguồn'},
  {id: 'hard_to_follow', label: 'Khó đọc, khó theo dõi'},
  {id: 'too_short', label: 'Quá ngắn hoặc thiếu ý'},
  {id: 'too_long', label: 'Quá dài, lặp ý'},
  {id: 'other', label: 'Vấn đề khác'},
]

type ChatSkill = {name: string; title: string}
type ChatLaunch = {prompt: string; controls: ChatControls}
type PreparedGmailDraft = {
  operation_id: string
  digest: string
  state: string
  error_code?: string | null
  result?: {draft_id?: string; gmail_draft_url?: string} | null
  preview: {
    recipient: string
    subject: string
    body: string
    cc?: string
    bcc?: string
  }
}

function sanitizeMarkdown(content: string): string {
  if (!content) return ''
  return normalizeMathNotation(content)
    .replace(/(?:\r?\n){3,}/g, '\n\n')
    .replace(/^[ \t]*•\s+/gm, '- ')
}

function cleanProps<T extends Record<string, unknown>>(props: T): Omit<T, 'node'> {
  const copy = { ...props }
  delete copy.node
  return copy as Omit<T, 'node'>
}

function markdownToDocumentBlocks(markdown: string) {
  return parseMarkdownDocument(markdown)
}
const controlLabels = {
  source: {drive: 'Drive', rag: 'RAG', gmail: 'Gmail', local: 'Tài liệu local', memory: 'Memory', general: 'Không dữ liệu riêng'},
  agent: {research: 'Research Agent', communication: 'Communication Agent', study: 'Study Agent', workspace: 'Workspace Agent'},
  output: {document: 'Google Docs', spreadsheet: 'Google Sheets'},
  workflow: {source_summary: 'Tóm tắt có nguồn', email_digest: 'Tổng hợp hộp thư', meeting_notes: 'Biên bản họp', study_plan: 'Lộ trình học', budget_tracker: 'Theo dõi ngân sách', compare_sources: 'So sánh nguồn'},
} as const

export function ChatPage({ onBusyChange, isActive = true }: ChatPageProps = {}) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionCursor, setSessionCursor] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showAllSessions, setShowAllSessions] = useState(false)
  const [sessionId, setSessionIdState] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('drive_agent_session_id') || null
    } catch {
      return null
    }
  })
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messageCursor, setMessageCursor] = useState<string | null>(null)
  const [input, setInputState] = useState<string>(() => {
    try {
      return sessionStorage.getItem('drive_agent_draft_input') || ''
    } catch {
      return ''
    }
  })
  const [busy, setBusy] = useState(false)
  const [liveProgress, setLiveProgress] = useState<Array<Record<string, unknown>>>([])
  const [briefingBusy, setBriefingBusy] = useState(false)
  const [error, setError] = useState('')
  const [savedMessages, setSavedMessages] = useState<Set<string>>(new Set())
  const [savingMessage, setSavingMessage] = useState<string | null>(null)
  const [exportingDoc, setExportingDoc] = useState<string | null>(null)
  const [preparedDocs, setPreparedDocs] = useState<Record<string, PreparedDocumentExport>>({})
  const [preparedDrafts, setPreparedDrafts] = useState<Record<string, PreparedGmailDraft>>({})
  const [createdDrafts, setCreatedDrafts] = useState<Record<string, { draft_id: string; url: string }>>({})
  const [draftingMessage, setDraftingMessage] = useState<string | null>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [feedbackByMessage, setFeedbackByMessage] = useState<Record<string, 'helpful' | 'not_helpful'>>({})
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const freshlyCreatedSession = useRef<string | null>(null)
  const [lastUserPrompt, setLastUserPrompt] = useState('')
  const [selectedModel, setSelectedModel] = useState<ModelOption>(AVAILABLE_MODELS[0]!)
  const [modelMenuOpen, setModelMenuOpen] = useState(false)
  const [usageDialogOpen, setUsageDialogOpen] = useState(false)
  const [capacity, setCapacity] = useState<ProviderCapacity | null>(null)
  const capacityRequestVersion = useRef(0)
  const [feedbackTarget, setFeedbackTarget] = useState<string | null>(null)
  const [feedbackReasonSelection, setFeedbackReasonSelection] = useState<FeedbackReason[]>([])
  const [feedbackComment, setFeedbackComment] = useState('')
  const [controls, setControls] = useState<ChatControls>(DEFAULT_CHAT_CONTROLS)
  const [skills, setSkills] = useState<ChatSkill[]>([])
  const [slashMenuOpen, setSlashMenuOpen] = useState(false)
  const [slashIndex, setSlashIndex] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const timerRef = useRef<number | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const activeTaskRef = useRef<string | null>(null)
  const submissionInFlightRef = useRef(false)
  const stopRequestedRef = useRef(false)

  async function stopGeneration() {
    if (!activeTaskRef.current && submissionInFlightRef.current) {
      // Do not abort creation and falsely claim the persisted task stopped.
      // Once its identifier arrives, cancel that exact task before polling.
      stopRequestedRef.current = true
      setError('Đang chờ máy chủ xác nhận yêu cầu để dừng an toàn.')
      return
    }
    if (activeTaskRef.current) {
      try {
        const task = await api<{status: string}>(
          `/api/chat/tasks/${activeTaskRef.current}/cancel`, {method: 'POST'},
        )
        if (task.status === 'completed') return // Let polling show the completed checkpoint.
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Chưa xác nhận dừng trên server.')
        return
      }
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    // An active submit releases its guard in finally. Allowing a new submit
    // before its cancellation settles lets the old cleanup clear the new run.
    if (!submissionInFlightRef.current) setBusy(false)
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (abortControllerRef.current) abortControllerRef.current.abort()
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    // A reload discovers owner-scoped pending tasks from SQL, not localStorage.
    api<{items: Array<{id: string; session_id: string}>}>('/api/chat/tasks', {signal: controller.signal})
      .then(async ({items}) => {
        const task = items[0]
        if (!task || controller.signal.aborted || activeTaskRef.current) return
        activeTaskRef.current = task.id
        abortControllerRef.current = controller
        setSessionId(task.session_id)
        setBusy(true)
        try {
          await waitForChatTask<ChatResult>(
            () => api(`/api/chat/tasks/${task.id}`, {signal: controller.signal}), controller.signal,
          )
          const page = await api<{items: ChatMessage[]; next_cursor: string | null}>(
            `/api/chat/sessions/${task.session_id}/messages-page`, {signal: controller.signal},
          )
          if (!controller.signal.aborted) { setMessages(page.items); setMessageCursor(page.next_cursor) }
        } catch (caught) {
          if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Chưa tải được kết quả.')
        } finally {
          if (activeTaskRef.current === task.id) activeTaskRef.current = null
          if (!controller.signal.aborted) setBusy(false)
        }
      })
      .catch(() => { /* History remains accessible if discovery is unavailable. */ })
    return () => controller.abort()
  }, [])

  const estimatedSessionTokens = useMemo(() => {
    const charCount = messages.reduce((acc, m) => acc + m.content.length, 0)
    return Math.round(charCount / 3.5)
  }, [messages])

  async function loadCapacity() {
    const version = ++capacityRequestVersion.current
    try {
      const next = await api<ProviderCapacity>('/api/settings/providers/gemini/status')
      if (version === capacityRequestVersion.current) setCapacity(next)
    } catch {
      if (version === capacityRequestVersion.current) setCapacity(null)
    }
  }

  useEffect(() => {
    if (!isActive) return
    void loadCapacity()
    const timer = window.setInterval(() => void loadCapacity(), 60_000)
    const changing = () => { capacityRequestVersion.current++; setCapacity(null) }
    const changed = () => { void loadCapacity() }
    window.addEventListener('veridra-credential-changing', changing)
    window.addEventListener('veridra-credential-changed', changed)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('veridra-credential-changing', changing)
      window.removeEventListener('veridra-credential-changed', changed)
    }
  }, [isActive])


  useEffect(() => {
    const applyLaunch = (detail: ChatLaunch) => {
      if (!detail?.prompt || !detail?.controls) return
      setInputState(detail.prompt)
      setControls(normalizeChatControls(detail.controls))
      setSlashMenuOpen(false)
      try {
        sessionStorage.setItem('drive_agent_draft_input', detail.prompt)
        sessionStorage.removeItem('drive_agent_chat_launch')
      } catch { /* storage is optional */ }
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
    const onLaunch = (event: Event) => applyLaunch((event as CustomEvent<ChatLaunch>).detail)
    window.addEventListener('driveagent:chat-launch', onLaunch)
    try {
      const stored = sessionStorage.getItem('drive_agent_chat_launch')
      if (stored) applyLaunch(JSON.parse(stored) as ChatLaunch)
    } catch { /* malformed or unavailable storage is ignored */ }
    return () => window.removeEventListener('driveagent:chat-launch', onLaunch)
  }, [])

  const { size: railWidth, isDragging: isRailDragging, resizerProps: railResizerProps } = useResizable({
    initialSize: 280,
    minSize: 200,
    maxSize: 480,
    direction: 'horizontal',
    storageKey: 'driveagent_chat_rail_width',
  })
  const [zoomedDiagram, setZoomedDiagram] = useState<string | null>(null)
  const [zoomedImage, setZoomedImage] = useState<{ src: string; alt: string } | null>(null)

  const allSlashOptions = useMemo(() => slashOptions(skills), [skills])
  const slashQuery = input.startsWith('/') ? input.slice(1) : ''
  const visibleSlashOptions = useMemo(
    () => filterSlashOptions(allSlashOptions, slashQuery),
    [allSlashOptions, slashQuery],
  )

  const setInput = (val: string) => {
    setInputState(val)
    try {
      if (val) {
        sessionStorage.setItem('drive_agent_draft_input', val)
      } else {
        sessionStorage.removeItem('drive_agent_draft_input')
      }
    } catch {
      // ignore
    }
  }

  function setSessionId(id: string | null) {
    setSessionIdState(id)
    // Errors belong to the request/session that produced them. Do not carry a
    // stale RAG/Drive error into a different conversation.
    setError('')
    try {
      if (id) {
        sessionStorage.setItem('drive_agent_session_id', id)
      } else {
        sessionStorage.removeItem('drive_agent_session_id')
      }
    } catch {
      // ignore
    }
  }

  const [isPickerOpen, setIsPickerOpen] = useState(false)
  const pickerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isPickerOpen) return
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (pickerRef.current && e.target && !pickerRef.current.contains(e.target as Node)) {
        setIsPickerOpen(false)
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsPickerOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('touchstart', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('touchstart', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isPickerOpen])

  useEffect(() => {
    if (isPickerOpen) {
      requestAnimationFrame(() => {
        const activeItem = pickerRef.current?.querySelector<HTMLButtonElement>('.session-picker-item--active')
        const firstItem = pickerRef.current?.querySelector<HTMLButtonElement>('.session-picker-item')
        ;(activeItem || firstItem)?.focus()
      })
    }
  }, [isPickerOpen])

  const currentSession = useMemo(() => sessions.find((s) => s.id === sessionId), [sessions, sessionId])
  const currentSessionTitle = sessionId
    ? (currentSession ? displaySessionTitle(currentSession.title) : 'Cuộc trò chuyện')
    : 'Cuộc trò chuyện mới'

  const handleSelectSession = (id: string | null) => {
    if (busy) return
    if (id === null) {
      setSessionId(null)
      setMessages([])
      setError('')
    } else if (id !== sessionId) {
      setSessionId(id)
      setMessages([])
      setError('')
    }
    setIsPickerOpen(false)
    triggerRef.current?.focus()
  }

  const handleSelectRailSession = (id: string) => {
    if (busy) return
    if (id !== sessionId) {
      setSessionId(id)
      setMessages([])
      setError('')
    }
  }

  const handleMenuKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      setIsPickerOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const focusableItems = Array.from(
        e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
      )
      if (focusableItems.length === 0) return
      const activeEl = document.activeElement as HTMLButtonElement | null
      const currentIndex = activeEl ? focusableItems.indexOf(activeEl) : -1
      let nextIndex = 0
      if (e.key === 'ArrowDown') {
        nextIndex = currentIndex < focusableItems.length - 1 ? currentIndex + 1 : 0
      } else {
        nextIndex = currentIndex > 0 ? currentIndex - 1 : focusableItems.length - 1
      }
      focusableItems[nextIndex]?.focus()
      return
    }
    if (e.key === 'Home') {
      e.preventDefault()
      const focusableItems = Array.from(
        e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
      )
      focusableItems[0]?.focus()
      return
    }
    if (e.key === 'End') {
      e.preventDefault()
      const focusableItems = Array.from(
        e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
      )
      focusableItems[focusableItems.length - 1]?.focus()
      return
    }
  }

  useEffect(() => {
    onBusyChange?.(busy || briefingBusy)
  }, [busy, briefingBusy, onBusyChange])

  useEffect(() => {
    let mounted = true
    api<{items: ChatSession[]; next_cursor: string | null}>('/api/chat/sessions-page')
      .then(data => { if (mounted) { setSessions(data.items); setSessionCursor(data.next_cursor) } })
      .catch(() => { if (mounted) setError('Chưa tải được lịch sử. Bạn vẫn có thể bắt đầu cuộc trò chuyện mới.') })
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!isActive) return
    let active = true
    api<{data: {items: ChatSkill[]}}>('/api/skills')
      .then(response => { if (active) setSkills(response.data.items) })
      .catch(() => { if (active) setSkills([]) })
    return () => { active = false }
  }, [isActive])

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      setMessageCursor(null)
      return
    }
    if (freshlyCreatedSession.current === sessionId) {
      freshlyCreatedSession.current = null
      return
    }
    let active = true
    api<{items: ChatMessage[]; next_cursor: string | null}>(`/api/chat/sessions/${sessionId}/messages-page`)
      .then((page) => { if (active) { setMessages(page.items); setMessageCursor(page.next_cursor) } })
      .catch((caught: ApiError) => { if (active) setError(caught.message) })
    return () => { active = false }
  }, [sessionId])

  async function loadOlderMessages() {
    if (!sessionId || !messageCursor) return
    try {
      const page = await api<{items: ChatMessage[]; next_cursor: string | null}>(
        `/api/chat/sessions/${sessionId}/messages-page?cursor=${encodeURIComponent(messageCursor)}`,
      )
      setMessages((current) => [...page.items, ...current])
      setMessageCursor(page.next_cursor)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được tin nhắn cũ hơn.')
    }
  }

  async function loadOlderSessions() {
    if (!sessionCursor) return
    try {
      const page = await api<{items: ChatSession[]; next_cursor: string | null}>(
        `/api/chat/sessions-page?cursor=${encodeURIComponent(sessionCursor)}`,
      )
      setSessions((current) => [...current, ...page.items])
      setSessionCursor(page.next_cursor)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được lịch sử cũ hơn.')
    }
  }

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'auto', block: 'nearest' })
  }, [messages, busy])

  async function submit(event?: FormEvent, customText?: string) {
    if (event) event.preventDefault()
    const content = (customText !== undefined ? customText : input).trim()
    if (!content || busy || submissionInFlightRef.current) return
    submissionInFlightRef.current = true
    stopRequestedRef.current = false
    setLastUserPrompt(content)
    setInput('')
    setError('')
    setBusy(true)
    const startTime = Date.now()
    setElapsedSeconds(0)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      setElapsedSeconds(Number(((Date.now() - startTime) / 1000).toFixed(1)))
    }, 100)

    const controller = new AbortController()
    abortControllerRef.current = controller
    let executionId: string = crypto.randomUUID()
    setLiveProgress([])
    let progressPending = false
    const progressTimer = window.setInterval(() => {
      if (progressPending || controller.signal.aborted) return
      progressPending = true
      api<{events: Array<Record<string, unknown>>}>(`/api/chat/progress/${executionId}`, {signal: controller.signal})
        .then(data => { if (!controller.signal.aborted) setLiveProgress(data.events) })
        .catch(() => { /* Progress outage must not fail the user's chat. */ })
        .finally(() => { progressPending = false })
    }, 1200)

    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content,
      citations: [],
      trace: [],
      status: 'running',
      created_at: new Date().toISOString(),
    }
    setMessages((current) => [...current, optimistic])
    try {
      const task = await api<{id: string; session_id: string}>('/api/chat/tasks', {
        method: 'POST',
        headers: {'X-Request-ID': executionId},
        signal: controller.signal,
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
          model: selectedModel.id,
          controls,
          client_key: executionId,
        }),
      })
      executionId = task.id
      activeTaskRef.current = task.id
      if (!sessionId) freshlyCreatedSession.current = task.session_id
      setSessionId(task.session_id)
      if (stopRequestedRef.current) {
        const stopped = await api<{status: string}>(
          `/api/chat/tasks/${task.id}/cancel`, {method: 'POST'},
        )
        if (stopped.status !== 'completed') {
          controller.abort()
          throw new DOMException('Yêu cầu đã được dừng.', 'AbortError')
        }
      }
      const result = await waitForChatTask<ChatResult>(
        () => api(`/api/chat/tasks/${task.id}`, {signal: controller.signal}), controller.signal,
      )
      if (controller.signal.aborted) return
      const durationMs = Date.now() - startTime
      if (!sessionId) freshlyCreatedSession.current = result.session_id
      setSessionId(result.session_id)
      setMessages((current) => [
          ...current.map(m => m.id === optimistic.id ? { ...m, status: 'completed' as const } : m),
        {
          id: result.message_id,
          role: 'assistant',
          content: result.answer,
          status: result.status,
          citations: result.citations,
          trace: result.trace,
          proposals: result.proposals,
          created_at: new Date().toISOString(),
          latency_ms: durationMs,
        },
      ])
      api<{items: ChatSession[]; next_cursor: string | null}>('/api/chat/sessions-page')
        .then((page) => { setSessions(page.items); setSessionCursor(page.next_cursor) })
        .catch(() => setError('Đã nhận câu trả lời, nhưng chưa cập nhật được danh sách lịch sử.'))
    } catch (caught) {
      const isAborted = controller.signal.aborted ||
        (caught instanceof Error && caught.name === 'AbortError') ||
        (caught instanceof DOMException && caught.name === 'AbortError')
      if (isAborted) {
        setMessages((current) => current.filter(message => message.id !== optimistic.id))
        setInput(content)
        setError('Đã dừng. Nội dung đã được giữ lại trong ô nhập.')
      } else {
        setMessages((current) => current.map(message =>
          message.id === optimistic.id ? {...message, status: 'failed'} : message
        ))
        setInput(content)
        setError(caught instanceof Error ? caught.message : 'Không thể gửi câu hỏi.')
      }
    } finally {
      clearInterval(progressTimer)
      controller.abort()
      abortControllerRef.current = null
      activeTaskRef.current = null
      submissionInFlightRef.current = false
      stopRequestedRef.current = false
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setBusy(false)
      void loadCapacity()
    }
  }

  function selectSlashOption(option: SlashOption) {
    setControls(current => mergeChatControls(current, option.patch))
    if (input.startsWith('/')) setInput('')
    setSlashMenuOpen(false)
    setSlashIndex(0)
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  function clearControl(key: keyof ChatControls) {
    setControls(current => {
      if (key === 'skill_name') {
        const next = {...current}
        delete next.skill_name
        return next
      }
      return {...current, [key]: DEFAULT_CHAT_CONTROLS[key]}
    })
  }

  const activeControls: Array<{key: keyof ChatControls; label: string}> = []
  if (controls.source !== 'auto') activeControls.push({key: 'source', label: controlLabels.source[controls.source]})
  if (controls.agent !== 'auto') activeControls.push({key: 'agent', label: controlLabels.agent[controls.agent]})
  if (controls.workflow !== 'auto') activeControls.push({key: 'workflow', label: controlLabels.workflow[controls.workflow]})
  if (controls.output !== 'chat') activeControls.push({key: 'output', label: controlLabels.output[controls.output]})
  if (controls.skill_name) {
    const names = controls.skill_name.split('+')
    activeControls.push({
      key: 'skill_name',
      label: names.length > 1 ? `Chuỗi ${names.length} Skill: ${names.join(' → ')}` : `Skill: ${names[0]}`,
    })
  }

  async function deleteSession(id: string) {
    if (!window.confirm('Bạn có chắc muốn xóa cuộc trò chuyện này?')) return
    try {
      await api(`/api/chat/sessions/${id}`, { method: 'DELETE' })
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (sessionId === id) {
        setSessionId(null)
        setMessages([])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể xóa phiên trò chuyện.')
    }
  }

  async function fetchMorningBriefing() {
    setBriefingBusy(true)
    setError('')
    try {
      const result = await api<{
        session_id: string
        title: string
        summary?: string
        answer?: string
        message_id: string
      }>('/api/chat/morning-briefing', { method: 'POST' })
      const content = result.answer || result.summary || ''
      freshlyCreatedSession.current = result.session_id
      setSessionId(result.session_id)
      setMessages([
        {
          id: result.message_id,
          role: 'assistant',
          content,
          citations: [],
          trace: [],
          created_at: new Date().toISOString(),
        },
      ])
      api<{items: ChatSession[]; next_cursor: string | null}>('/api/chat/sessions-page')
        .then((page) => { setSessions(page.items); setSessionCursor(page.next_cursor) }).catch(() => {})
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể tạo bản tin sáng.')
    } finally {
      setBriefingBusy(false)
    }
  }

  async function exportToGoogleDoc(message: ChatMessage) {
    setExportingDoc(message.id)
    setError('')
    try {
      const firstLine = (message.content.split('\n')[0] ?? '').replace(/^#+\s*/, '').slice(0, 50).trim()
      const title = firstLine ? `Veridra: ${firstLine}` : `Tài liệu Veridra - ${new Date().toLocaleDateString('vi-VN')}`
      const result = await api<{
        data: { operation_id: string; digest: string; state: string }
      }>(
        '/api/documents/prepare',
        {
          method: 'POST',
          body: JSON.stringify({
            request_key: `doc-export-${message.id}`,
            action: 'create',
            document: {
              title,
              blocks: [
                ...markdownToDocumentBlocks(message.content),
                ...(message.citations.length ? [
                  {kind: 'paragraph' as const, text: 'Nguồn', style: 'HEADING_2' as const, list_style: 'none' as const},
                  ...message.citations.map((citation, index) => ({
                    kind: 'paragraph' as const,
                    text: `[${index + 1}] ${citation.file_name}${citation.web_view_link ? ` — ${citation.web_view_link}` : ''}`,
                    style: 'NORMAL_TEXT' as const,
                    list_style: 'bullet' as const,
                  })),
                ] : []),
              ],
            },
          }),
        }
      )
      setPreparedDocs(prev => ({
        ...prev,
        [message.id]: { ...result.data, title },
      }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể xuất Google Doc.')
    } finally {
      setExportingDoc(null)
    }
  }

  async function createDraftFromMessage(message: ChatMessage) {
    setDraftingMessage(message.id)
    setError('')
    try {
      const firstLine = (message.content.split('\n')[0] ?? '').replace(/^#+\s*/, '').slice(0, 60).trim()
      const subject = firstLine ? `Veridra: ${firstLine}` : `Thông tin trao đổi - ${new Date().toLocaleDateString('vi-VN')}`
      const requestKey = `chat-draft-${crypto.randomUUID()}`
      const res = await api<{data: PreparedGmailDraft}>('/api/gmail/draft', {
        method: 'POST',
        body: JSON.stringify({
          request_key: requestKey,
          draft: {recipient: '', subject, body: message.content},
        }),
      })
      if (res.data.state === 'succeeded' && res.data.result?.draft_id) {
        setCreatedDrafts(prev => ({
          ...prev,
          [message.id]: {
            draft_id: res.data.result!.draft_id!,
            url: res.data.result!.gmail_draft_url ?? 'https://mail.google.com/mail/u/0/#drafts',
          },
        }))
      } else {
        setPreparedDrafts(prev => ({...prev, [message.id]: res.data}))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể chuẩn bị thư nháp Gmail.')
    } finally {
      setDraftingMessage(null)
    }
  }

  async function approveDraftFromMessage(message: ChatMessage) {
    const prepared = preparedDrafts[message.id]
    if (!prepared) return
    setDraftingMessage(message.id)
    setError('')
    try {
      const res = await api<{draft_id: string; gmail_draft_url: string}>(
        '/api/gmail/draft/approve',
        {
          method: 'POST',
          body: JSON.stringify({
            operation_id: prepared.operation_id,
            approved_digest: prepared.digest,
          }),
        },
      )
      setCreatedDrafts(prev => ({
        ...prev,
        [message.id]: {draft_id: res.draft_id, url: res.gmail_draft_url},
      }))
      setPreparedDrafts(prev => {
        const next = {...prev}
        delete next[message.id]
        return next
      })
    } catch (e) {
      try {
        const status = await api<{
          state: string
          error_code?: string | null
          result?: {draft_id?: string; gmail_draft_url?: string} | null
        }>(`/api/gmail/operations/${prepared.operation_id}`)
        if (status.state === 'succeeded' && status.result?.draft_id) {
          setCreatedDrafts(prev => ({
            ...prev,
            [message.id]: {
              draft_id: status.result!.draft_id!,
              url: status.result!.gmail_draft_url ?? 'https://mail.google.com/mail/u/0/#drafts',
            },
          }))
          setPreparedDrafts(prev => {
            const next = {...prev}
            delete next[message.id]
            return next
          })
          return
        }
        setPreparedDrafts(prev => ({
          ...prev,
          [message.id]: {...prepared, state: status.state, error_code: status.error_code},
        }))
        setError(
          status.state === 'uncertain'
            ? 'Gmail chưa xác nhận kết quả. Không bấm tạo lại; hãy kiểm tra thư nháp trong Gmail.'
            : (e instanceof Error ? e.message : 'Không thể xác nhận thao tác Gmail.'),
        )
      } catch {
        setError(
          'Không nhận được xác nhận từ Gmail và chưa kiểm tra được trạng thái. Hãy kiểm tra Gmail trước khi thử lại.',
        )
      }
    } finally {
      setDraftingMessage(null)
    }
  }

  function copyMessageContent(message: ChatMessage) {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopiedMessageId(message.id)
      setTimeout(() => setCopiedMessageId(null), 2000)
    }).catch(() => {
      setError('Không thể sao chép vào bộ nhớ tạm.')
    })
  }

  async function saveAnswer(message: ChatMessage) {
    setSavingMessage(message.id); setError('')
    const sources = message.citations.map((citation, index) =>
      `[${index + 1}] ${citation.file_name}: ${citation.web_view_link ?? 'Không có liên kết'}`).join('\n')
    try {
      await api('/api/artifacts', {method:'POST', body:JSON.stringify({
        title:message.content.slice(0, 80).trim(), content:message.content + (sources ? `\n\n## Nguồn\n\n${sources}` : ''),
        kind:'note', creation_key:message.id,
      })})
      setSavedMessages(previous => new Set([...previous, message.id]))
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Không lưu được câu trả lời.') }
    finally { setSavingMessage(null) }
  }

  async function rateAnswer(
    messageId: string,
    rating: 'helpful' | 'not_helpful',
    reasons: FeedbackReason[] = [],
    comment = '',
  ) {
    setError('')
    try {
      await api(`/api/harness/feedback/${messageId}`, {
        method: 'POST',
        body: JSON.stringify({rating, reasons, comment: comment.trim() || undefined}),
      })
      setFeedbackByMessage(current => ({...current, [messageId]: rating}))
      setFeedbackTarget(null)
      setFeedbackReasonSelection([])
      setFeedbackComment('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa lưu được đánh giá.')
    }
  }

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.trim().toLowerCase())
  )
  const displayedSessions = showAllSessions ? filteredSessions : filteredSessions.slice(0, 10)
  const remainingCount = filteredSessions.length - 10

  return (
    <div
      className="chat-layout"
      style={{ ['--chat-rail-width' as string]: `${railWidth}px` }}
    >
      <aside className="session-rail" aria-label="Lịch sử trò chuyện" style={{ width: `${railWidth}px` }}>
        <div className="rail-top-actions">
          <p className="rail-heading">Góc làm việc</p>
          <button
            type="button"
            className="new-chat-btn"
            disabled={busy || briefingBusy}
            onClick={() => { setSessionId(null); setMessages([]); setError('') }}
          >
            <span className="new-chat-btn__icon">✦</span>
            Cuộc trò chuyện mới
          </button>
          <button
            type="button"
            className={`briefing-btn${briefingBusy ? ' briefing-btn--busy' : ''}`}
            disabled={busy || briefingBusy}
            onClick={() => void fetchMorningBriefing()}
            title="Tự động quét Gmail chưa đọc và tài liệu Drive mới cập nhật tối qua"
          >
            {briefingBusy ? (
              <Spinner size="tiny" />
            ) : (
              <span className="briefing-btn__sparkle">✨</span>
            )}
            {briefingBusy ? 'Đang tổng hợp…' : 'Bản tin sáng'}
          </button>
          <Input
            className="session-search-input"
            aria-label="Tìm kiếm trò chuyện"
            placeholder="Tìm kiếm trò chuyện…"
            value={searchQuery}
            onChange={(_, data) => setSearchQuery(data.value)}
            contentBefore={<Search20Regular />}
            style={{ width: '100%' }}
          />
        </div>

        <div className="session-list">
          <div className="rail-caption-row">
            <span className="rail-caption">Trò chuyện gần đây</span>
            <span className="rail-caption-count">{filteredSessions.length}</span>
          </div>

          {filteredSessions.length === 0 ? (
            <p className="rail-empty">
              {searchQuery ? 'Không tìm thấy cuộc trò chuyện nào.' : 'Các cuộc trò chuyện sẽ được lưu ở đây.'}
            </p>
          ) : null}

          {displayedSessions.map((session) => {
            const meta = getSessionTopicMeta(session.title, session.id)
            const MetaIcon = meta.icon
            const isActive = sessionId === session.id

            return (
              <div
                key={session.id}
                className={`session-card session-card--${meta.accentClass} ${isActive ? 'session-card--active' : ''}`}
                onClick={() => handleSelectRailSession(session.id)}
                role="button"
                tabIndex={0}
                aria-current={isActive ? 'true' : undefined}
                onKeyDown={(e) => {
                  if (e.target !== e.currentTarget) return
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleSelectRailSession(session.id)
                  }
                }}
              >
                <div className="session-card__body">
                  <div className="session-card__top">
                    <span className="session-card__title" title={displaySessionTitle(session.title)}>
                      {displaySessionTitle(session.title)}
                    </span>
                    <span className="session-card__time">
                      {formatRelativeTime(session.updated_at)}
                    </span>
                  </div>
                  <div className="session-card__bottom">
                    <span className={`session-card__tag session-card__tag--${meta.accentClass}`}>
                      <MetaIcon className="session-card__tag-icon" /> {meta.label}
                    </span>
                    {isActive ? (
                      <span className="session-card__active-dot" title="Đang mở" aria-label="Đang mở" />
                    ) : null}
                  </div>
                </div>
                <button
                  type="button"
                  className="session-card__delete"
                  title="Xóa cuộc trò chuyện này"
                  aria-label={`Xóa ${displaySessionTitle(session.title)}`}
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation()
                    void deleteSession(session.id)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.stopPropagation()
                    }
                  }}
                >
                  <Delete16Regular />
                </button>
              </div>
            )
          })}

          {filteredSessions.length > 10 ? (
            <Button
              appearance="subtle"
              size="small"
              className="session-expand-btn"
              onClick={() => setShowAllSessions((prev) => !prev)}
            >
              {showAllSessions ? 'Thu gọn (chỉ hiện 10 phiên gần nhất)' : `Xem thêm (${remainingCount} cuộc trò chuyện cũ hơn)`}
            </Button>
          ) : null}
          {sessionCursor ? <Button appearance="subtle" size="small" className="session-expand-btn" onClick={() => void loadOlderSessions()}>
            Tải thêm lịch sử
          </Button> : null}
        </div>
      </aside>

      <div
        className={`split-resizer ${isRailDragging ? 'split-resizer--dragging' : ''}`}
        title="Kéo sang trái/phải để thay đổi kích thước danh sách trò chuyện. Bấm đúp để đặt lại."
        aria-label="Thanh kéo điều chỉnh độ rộng lịch sử trò chuyện"
        {...railResizerProps}
      />

      <section className="chat-main" aria-label="Nội dung trò chuyện">
        <div className="session-picker-wrap" ref={pickerRef}>
          <button
            ref={triggerRef}
            type="button"
            className={`session-picker-trigger ${isPickerOpen ? 'session-picker-trigger--open' : ''}`}
            aria-label="Chọn cuộc trò chuyện"
            aria-haspopup="listbox"
            aria-expanded={isPickerOpen}
            aria-controls="session-picker-menu"
            disabled={busy}
            onClick={() => {
              if (!busy) setIsPickerOpen((prev) => !prev)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault()
                if (!busy) setIsPickerOpen(true)
              }
            }}
          >
            <span className="session-picker-icon">
              {sessionId ? <Chat16Regular /> : <ArrowTrendingLines20Regular />}
            </span>
            <span className="session-picker-title" title={currentSessionTitle}>
              {currentSessionTitle}
            </span>
            <span
              className={`session-picker-chevron ${isPickerOpen ? 'session-picker-chevron--open' : ''}`}
              aria-hidden="true"
            >
              ⌄
            </span>
          </button>

          {isPickerOpen && (
            <div
              id="session-picker-menu"
              className="session-picker-menu"
              role="listbox"
              aria-label="Danh sách cuộc trò chuyện"
              aria-activedescendant={sessionId ? `session-picker-opt-${sessionId}` : 'session-picker-opt-new'}
              onKeyDown={handleMenuKeyDown}
            >
              <div className="session-picker-menu__header" role="presentation">
                <span className="session-picker-menu__header-title">Chọn cuộc trò chuyện</span>
                <span className="session-picker-menu__header-count">{sessions.length} phiên</span>
              </div>

              <button
                id="session-picker-opt-new"
                type="button"
                className={`session-picker-item session-picker-item--new ${sessionId === null ? 'session-picker-item--active' : ''}`}
                role="option"
                aria-selected={sessionId === null}
                disabled={busy}
                onClick={() => handleSelectSession(null)}
              >
                <span className="session-picker-item-icon session-picker-item-icon--new">✦</span>
                <div className="session-picker-item-content">
                  <div className="session-picker-item-title">+ Cuộc trò chuyện mới</div>
                  <div className="session-picker-item-sub">Khởi tạo ngữ cảnh trò chuyện hoàn toàn mới</div>
                </div>
                {sessionId === null && <span className="session-picker-item-active-dot" title="Đang mở" />}
              </button>

              <div className="session-picker-divider" role="separator" />

              <div className="session-picker-list" role="presentation">
                {sessions.length === 0 ? (
                  <div className="session-picker-empty" role="presentation">Chưa có lịch sử cuộc trò chuyện nào</div>
                ) : (
                  sessions.map((session) => {
                    const isSelected = sessionId === session.id
                    return (
                      <button
                        id={`session-picker-opt-${session.id}`}
                        type="button"
                        key={session.id}
                        className={`session-picker-item ${isSelected ? 'session-picker-item--active' : ''}`}
                        role="option"
                        aria-selected={isSelected}
                        disabled={busy}
                        onClick={() => handleSelectSession(session.id)}
                      >
                        <span className="session-picker-item-icon">
                          <Chat16Regular />
                        </span>
                        <div className="session-picker-item-content">
                          <div className="session-picker-item-title" title={displaySessionTitle(session.title)}>
                            {displaySessionTitle(session.title)}
                          </div>
                          <div className="session-picker-item-sub">
                            <span className="session-picker-item-time">{formatRelativeTime(session.updated_at) || 'Vừa xong'}</span>
                            <span className="session-picker-item-bullet">•</span>
                            <span className="session-picker-item-tag">Veridra</span>
                          </div>
                        </div>
                        {isSelected && <span className="session-picker-item-active-dot" title="Đang mở" />}
                      </button>
                    )
                  })
                )}
                {sessionCursor ? (
                  <button
                    type="button"
                    className="session-picker-load-more"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation()
                      void loadOlderSessions()
                    }}
                  >
                    Tải thêm cuộc trò chuyện cũ hơn…
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </div>

        <div className="message-scroll" aria-live="polite">
          {messageCursor ? <Button appearance="subtle" size="small" className="message-load-older" onClick={() => void loadOlderMessages()}>
            Tải tin nhắn cũ hơn
          </Button> : null}
          {messages.length === 0 ? (
            <EmptyState
              title="Bạn muốn bắt đầu từ đâu?"
              description="Nêu việc bạn cần hoàn thành hoặc chọn một gợi ý. Veridra sẽ tìm nguồn, giải thích và xin bạn duyệt trước mọi thao tác ghi."
              action={
                <div className="prompt-grid">
                  {prompts.map((prompt, index) => (
                    <button type="button" key={prompt} className={`prompt-card prompt-card--${index}`} onClick={() => { setInput(prompt); inputRef.current?.focus() }}>
                      {prompt}
                    </button>
                  ))}
                </div>
              }
            />
          ) : (
            messages.map((message) => (
              <article key={message.id} className={`message message--${message.role}`}>
                <div className="message__meta">
                  <span>{message.role === 'assistant' ? 'Veridra' : 'Bạn'}</span>
                  {message.status === 'running' ? ' · Đang xử lý' : ''}
                  {message.status === 'cancelled' ? ' · Đã dừng' : ''}
                  {message.status === 'failed' ? ' · Chưa hoàn tất' : ''}
                  {message.status === 'incomplete' ? ' · Bản nháp chưa đạt yêu cầu định dạng' : ''}
                </div>
                <div className="message__content">
                  {message.role === 'assistant' ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      skipHtml
                      components={{
                        img: ({ src, alt }) => src
                          ? (
                            <span
                              className="image-preview-wrapper"
                              onClick={() => setZoomedImage({ src: src || '', alt: alt || '' })}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => { if (e.key === 'Enter') setZoomedImage({ src: src || '', alt: alt || '' }) }}
                              title="Nhấp để phóng to hình ảnh"
                            >
                              <img src={src} alt={alt || 'Hình ảnh trong tài liệu'} loading="lazy" />
                              <span className="image-zoom-hint">🔍 Nhấp phóng to</span>
                            </span>
                          )
                          : <span className="omitted-image">[Hình ảnh không có đường dẫn]</span>,
                        a: ({ href, children }) => {
                          const url = href ?? ''
                          if (/^https?:\/\//i.test(url)) {
                            return <a href={url} target="_blank" rel="noopener noreferrer">{children}</a>
                          }
                          if (/^(?:\/#|\/?#|\/drive|\/api\/drive)/i.test(url)) {
                            return <a href={url} className="citation-deep-link">{children}</a>
                          }
                          return <span>{children}</span>
                        },
                        table: ({ children, ...props }) => (
                          <div className="table-container">
                            <table className="markdown-table" {...cleanProps(props)}>{children}</table>
                          </div>
                        ),
                        th: ({ children, ...props }) => <th className="markdown-th" {...cleanProps(props)}>{children}</th>,
                        td: ({ children, ...props }) => <td className="markdown-td" {...cleanProps(props)}>{children}</td>,
                        pre: ({ children, ...props }) => {
                          const childArr = Array.isArray(children) ? children : [children]
                          const isMermaid = childArr.some((c) => isValidElement<{ className?: string }>(c) && typeof c.props?.className === 'string' && c.props.className.includes('language-mermaid'))
                          if (isMermaid) {
                            return <div className="mermaid-pre-wrapper">{children}</div>
                          }
                          return <pre className="markdown-pre" {...cleanProps(props)}>{children}</pre>
                        },
                        code: ({ className, children, ...props }) => {
                          const match = /language-mermaid/.exec(className || '')
                          if (match) {
                            return <MermaidDiagram chart={String(children)} onZoom={setZoomedDiagram} />
                          }
                          return (
                            <code className={className ? `markdown-code ${className}` : 'markdown-inline-code'} {...cleanProps(props)}>
                              {children}
                            </code>
                          )
                        },
                      }}
                    >
                      {sanitizeMarkdown(message.content)}
                    </ReactMarkdown>
                  ) : message.content}
                </div>

                {message.role === 'user' && message.status === 'failed' ? (
                  <div className="message-retry-draft">
                    <Button
                      appearance="outline"
                      size="small"
                      icon={<ArrowReset20Regular />}
                      onClick={() => { setInput(message.content); inputRef.current?.focus() }}
                    >
                      Đưa lại vào ô nhập
                    </Button>
                    <span>Kiểm tra Skill, nguồn và model trước khi gửi lại.</span>
                  </div>
                ) : null}

                {message.citations.length > 0 ? (
                  <div className="citations" aria-label="Nguồn trích dẫn">
                    {message.citations.map((citation, index) => (
                      <a
                        key={`${citation.file_id}-${citation.chunk_index}`}
                        href={citationHref(citation).href}
                        target="_blank"
                        rel="noreferrer"
                        className="citation-link"
                        title={citationHref(citation).title}
                      >
                        <DocumentLink24Regular />
                        <span>
                          [{index + 1}] {citation.file_name}
                          {citation.page_number ? ` · trang ${citation.page_number}` : ''}
                        </span>
                      </a>
                    ))}
                  </div>
                ) : null}

                {message.trace.length > 0 ? (
                  <ExecutionTrace trace={message.trace} />
                ) : null}

                {message.status !== 'incomplete' ? message.proposals?.map(proposal => <CreationProposal key={proposal.id} proposal={proposal} />) : null}

                {preparedDrafts[message.id] ? (
                  <section className="gmail-draft-review" aria-label="Xem trước thư nháp Gmail">
                    <div className="gmail-draft-review__heading">Kiểm tra trước khi lưu vào Gmail</div>
                    <dl>
                      <div><dt>Người nhận</dt><dd>{preparedDrafts[message.id]!.preview.recipient || 'Chưa đặt người nhận'}</dd></div>
                      <div><dt>Tiêu đề</dt><dd>{preparedDrafts[message.id]!.preview.subject}</dd></div>
                    </dl>
                    <pre>{preparedDrafts[message.id]!.preview.body}</pre>
                    {preparedDrafts[message.id]!.state !== 'pending' ? (
                      <p role="status">
                        Trạng thái: {preparedDrafts[message.id]!.state}
                        {preparedDrafts[message.id]!.error_code
                          ? ` · ${preparedDrafts[message.id]!.error_code}`
                          : ''}
                      </p>
                    ) : null}
                    <div className="gmail-draft-review__actions">
                      <Button
                        appearance="primary"
                        disabled={draftingMessage === message.id || preparedDrafts[message.id]!.state !== 'pending'}
                        onClick={() => void approveDraftFromMessage(message)}
                      >
                        {draftingMessage === message.id ? 'Đang lưu nháp…' : 'Xác nhận lưu thư nháp'}
                      </Button>
                      <Button
                        disabled={draftingMessage === message.id}
                        onClick={() => setPreparedDrafts(prev => {
                          const next = {...prev}
                          delete next[message.id]
                          return next
                        })}
                      >
                        Hủy
                      </Button>
                      {['failed', 'expired'].includes(preparedDrafts[message.id]!.state) ? (
                        <Button
                          disabled={draftingMessage === message.id}
                          onClick={() => void createDraftFromMessage(message)}
                        >
                          Chuẩn bị yêu cầu mới
                        </Button>
                      ) : null}
                    </div>
                  </section>
                ) : null}

                {createdDrafts[message.id] ? (
                  <div className="gmail-draft-badge-card">
                    <div className="gmail-draft-badge-content">
                      <Mail20Regular primaryFill="var(--colorBrandForeground1)" />
                      <span>Đã tạo Thư nháp trong Gmail của bạn (Mã: <code>{createdDrafts[message.id]!.draft_id}</code>)</span>
                    </div>
                    <a
                      href={createdDrafts[message.id]!.url}
                      target="_blank"
                      rel="noreferrer"
                      className="gmail-draft-link-button"
                    >
                      Mở trong Gmail ↗
                    </a>
                  </div>
                ) : null}

                {message.role === 'assistant' && (
                  <div className="message-action-toolbar">
                    <Button
                      appearance="subtle"
                      size="small"
                      disabled={message.status === 'incomplete' || savingMessage !== null || savedMessages.has(message.id)}
                      onClick={() => void saveAnswer(message)}
                    >
                      {savedMessages.has(message.id) ? 'Đã lưu ghi chú' : savingMessage === message.id ? 'Đang lưu…' : 'Lưu ghi chú'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<DocumentBulletList20Regular />}
                      disabled={message.status === 'incomplete' || exportingDoc === message.id || Boolean(preparedDocs[message.id])}
                      onClick={() => void exportToGoogleDoc(message)}
                    >
                      {exportingDoc === message.id ? 'Đang chuẩn bị…' : 'Xuất Google Doc'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<Mail20Regular />}
                      disabled={message.status === 'incomplete' || draftingMessage === message.id || Boolean(createdDrafts[message.id]) || Boolean(preparedDrafts[message.id])}
                      onClick={() => void createDraftFromMessage(message)}
                    >
                      {draftingMessage === message.id ? 'Đang chuẩn bị…' : createdDrafts[message.id] ? 'Đã tạo nháp Gmail' : 'Chuẩn bị lưu thư nháp'}
                    </Button>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={copiedMessageId === message.id ? <Checkmark16Regular /> : <Copy20Regular />}
                      onClick={() => copyMessageContent(message)}
                    >
                      {copiedMessageId === message.id ? 'Đã chép' : 'Sao chép'}
                    </Button>
                    {message.latency_ms ? (
                      <span className="message-latency-pill" title={`Thời gian xử lý: ${(message.latency_ms / 1000).toFixed(1)} giây`}>
                        ⏱️ {(message.latency_ms / 1000).toFixed(1)}s
                      </span>
                    ) : null}
                    <span className="message-feedback" aria-label="Đánh giá câu trả lời">
                      <button
                        type="button"
                        aria-pressed={feedbackByMessage[message.id] === 'helpful'}
                        onClick={() => void rateAnswer(message.id, 'helpful')}
                      >
                        Hữu ích
                      </button>
                      <button
                        type="button"
                        aria-pressed={feedbackByMessage[message.id] === 'not_helpful'}
                        onClick={() => {
                          setFeedbackTarget(message.id)
                          setFeedbackReasonSelection([])
                          setFeedbackComment('')
                        }}
                      >
                        Chưa ổn
                      </button>
                    </span>
                  </div>
                )}
                {preparedDocs[message.id] ? (
                  <DocumentExportApproval prepared={preparedDocs[message.id]!} />
                ) : null}
              </article>
            ))
          )}

          {busy ? (
            <div className="agent-working" role="status" aria-live="polite">
              <div className="agent-working-header">
                <div className="agent-working-stopwatch-badge">
                  <Spinner size="tiny" />
                  <span className="agent-working-stopwatch-text">⏱️ {elapsedSeconds.toFixed(1)}s</span>
                </div>
                <Button
                  appearance="subtle"
                  size="small"
                  icon={<Dismiss16Regular />}
                  onClick={stopGeneration}
                  className="agent-stop-button"
                  title="Dừng yêu cầu trên server; lời gọi provider đã bắt đầu vẫn có thể tiêu quota"
                >
                  Dừng yêu cầu
                </Button>
              </div>
              <span className="agent-working-status-text">
                {elapsedSeconds < 30
                  ? 'Đang chờ Agent trả lời…'
                  : 'Yêu cầu đang mất nhiều thời gian hơn. Bạn có thể tiếp tục chờ hoặc ngừng chờ phản hồi.'}
              </span>
              {liveProgress.length > 0 ? <div className="agent-working-events">
                <strong>Sự kiện thực thi thực tế</strong>
                <ol>{liveProgress.slice(-6).map((item, index) => <li key={index}>
                  {item.stage === 'agent_handoff'
                    ? `${String(item.from)} → ${String(item.to)}: được điều phối`
                    : item.stage === 'tool'
                      ? `${String(item.tool)}: ${item.status === 'running' ? 'đang chạy' : String(item.status)}`
                      : 'Điều phối yêu cầu đang chạy'}
                </li>)}</ol>
                <small>Đây là trạng thái agent/tool, không phải suy nghĩ nội bộ. Không có sự kiện A2A nếu yêu cầu không dùng A2A.</small>
              </div> : null}
            </div>
          ) : null}
          <div ref={endRef} />
        </div>

        {error ? (
          <div className="chat-error-banner">
            <ErrorState message={error} />
            {error.includes('Google chưa cấp quyền cần thiết') ? (
              <a className="gmail-draft-link-button" href="/api/auth/google?capability=gmail">
                Cấp quyền tạo thư nháp Gmail
              </a>
            ) : null}
            {lastUserPrompt && (
              <Button
                appearance="outline"
                size="small"
                icon={<ArrowReset20Regular />}
                onClick={() => void submit(undefined, lastUserPrompt)}
                disabled={busy}
              >
                Thử lại câu hỏi vừa rồi
              </Button>
            )}
            {/quota|API key|Gemini/i.test(error) ? (
              <Button appearance="subtle" size="small" onClick={() => { window.location.hash = '#/settings' }}>
                Xem năng lực AI và key
              </Button>
            ) : null}
          </div>
        ) : null}

        <form className="composer-container" onSubmit={(e) => void submit(e)}>
          {slashMenuOpen ? (
            <div id="slash-command-menu" className="slash-menu" role="listbox" aria-label="Khả năng nhanh của Veridra">
              <header>
                <strong>Chọn cách Agent làm việc</strong>
                <span>Gõ để lọc · ↑↓ để di chuyển · Enter để chọn</span>
              </header>
              <div className="slash-menu__options">
                {visibleSlashOptions.length ? visibleSlashOptions.map((option, index) => {
                  const previous = visibleSlashOptions[index - 1]
                  return <div key={option.id}>
                    {previous?.group !== option.group ? <p className="slash-menu__group">{option.group}</p> : null}
                    <button
                      type="button"
                      id={`slash-option-${option.id}`}
                      role="option"
                      aria-selected={index === slashIndex}
                      className={`slash-option${option.group === 'Skill của bạn' ? ' slash-option--skill' : ''}${index === slashIndex ? ' slash-option--active' : ''}`}
                      onMouseEnter={() => setSlashIndex(index)}
                      onClick={() => selectSlashOption(option)}
                    >
                      <code>{option.command}</code>
                      <span><strong>{option.label}</strong><small>{option.description}</small></span>
                    </button>
                  </div>
                }) : <p className="slash-menu__empty">Không có lệnh phù hợp. Thử /drive, /gmail hoặc /doc.</p>}
              </div>
            </div>
          ) : null}
          {activeControls.length ? <div className="composer-controls" aria-label="Điều khiển đang chọn">
            {activeControls.map(item => <button type="button" key={item.key} onClick={() => clearControl(item.key)} title="Bỏ lựa chọn này">
              {item.label}<span aria-hidden="true">×</span>
            </button>)}
          </div> : null}
          <Textarea
            ref={inputRef}
            id="chat-input"
            name="message"
            className="composer-textarea"
            resize="vertical"
            value={input}
            onChange={(_, data) => {
              setInput(data.value)
              const commandMode = data.value.startsWith('/') && !/\s/.test(data.value)
              setSlashMenuOpen(commandMode)
              setSlashIndex(0)
            }}
            placeholder="Nêu việc cần làm, hoặc gõ / để chọn nguồn, agent, skill…"
            aria-label="Nội dung câu hỏi"
            aria-controls={slashMenuOpen ? 'slash-command-menu' : undefined}
            aria-activedescendant={slashMenuOpen && visibleSlashOptions[slashIndex] ? `slash-option-${visibleSlashOptions[slashIndex]!.id}` : undefined}
            onKeyDown={(event) => {
              if (slashMenuOpen) {
                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  setSlashIndex(current => Math.min(current + 1, Math.max(0, visibleSlashOptions.length - 1)))
                  return
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  setSlashIndex(current => Math.max(0, current - 1))
                  return
                }
                if (event.key === 'Escape') {
                  event.preventDefault()
                  setSlashMenuOpen(false)
                  return
                }
                if (event.key === 'Enter' && visibleSlashOptions[slashIndex]) {
                  event.preventDefault()
                  selectSlashOption(visibleSlashOptions[slashIndex]!)
                  return
                }
              }
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />

          <div className="composer-bottom-bar">
            <button
              type="button"
              className="slash-trigger"
              aria-expanded={slashMenuOpen}
              onClick={() => {
                setSlashMenuOpen(current => !current)
                setSlashIndex(0)
                inputRef.current?.focus()
              }}
              title="Chọn nhanh nguồn, agent, quy trình hoặc đầu ra"
            >
              <span>/</span> Khả năng
            </button>
            <div className="model-selector-wrapper">
              <button
                type="button"
                className="model-selector-btn"
                onClick={() => setModelMenuOpen((prev) => !prev)}
                aria-expanded={modelMenuOpen}
                aria-haspopup="true"
              title="Chọn model trả lời"
              >
                <span className="model-plus-icon">+</span>
                <span className="model-btn-name">{selectedModel.name}</span>
                <ChevronUp16Regular className={`model-chevron ${modelMenuOpen ? 'model-chevron--open' : ''}`} />
              </button>

              {modelMenuOpen && (
                <div className="model-selector-popover" role="menu">
                  <div className="model-popover-header">Model</div>
                  <div className="model-popover-list">
                    {AVAILABLE_MODELS.map((m) => (
                      <div
                        key={m.id}
                        className={`model-option-item ${selectedModel.id === m.id ? 'model-option-item--active' : ''}`}
                        onClick={() => {
                          setSelectedModel(m)
                          setModelMenuOpen(false)
                        }}
                        role="menuitem"
                        title={m.description}
                      >
                        <div className="model-option-left">
                          <span className="model-option-name">{m.name}</span>
                          <div className="model-option-badges">
                            <span className="model-badge model-badge--context">{m.availability}</span>
                            <span className="model-badge model-badge--speed">{m.speed}</span>
                          </div>
                        </div>
                        {selectedModel.id === m.id && <Checkmark16Regular className="model-check-icon" />}
                      </div>
                    ))}
                  </div>
                  <div className="model-popover-divider" />
                  <button
                    type="button"
                    className="model-view-usage-btn"
                    onClick={() => {
                      setModelMenuOpen(false)
                      setUsageDialogOpen(true)
                    }}
                  >
                    <ArrowTrendingLines20Regular />
                    <span>Thông tin model</span>
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              className="composer-quota-pill"
              onClick={() => setUsageDialogOpen(true)}
              title="Mở trạng thái model và ngân sách an toàn local"
            >
              <span className="composer-quota-label">
                {capacity?.local_budget
                  ? <>Năng lực AI <strong className="composer-quota-val">{capacity.local_budget.daily_remaining}/{capacity.local_budget.daily_limit} lượt local</strong></>
                  : <>Ngữ cảnh <strong className="composer-quota-val">~{estimatedSessionTokens.toLocaleString('vi-VN')} token</strong></>}
              </span>
            </button>

            {busy ? (
              <Button
                type="button"
                appearance="secondary"
                className="composer-send-btn composer-stop-btn"
                icon={<DismissCircle24Regular primaryFill="#ea4335" />}
                onClick={stopGeneration}
                title="Dừng yêu cầu trên server; lời gọi provider đã bắt đầu vẫn có thể tiêu quota"
              >
                Dừng yêu cầu
              </Button>
            ) : (
              <Button
                type="submit"
                appearance="primary"
                className="composer-send-btn"
                icon={<Send24Regular />}
                disabled={!input.trim()}
              >
                Gửi
              </Button>
            )}
          </div>
        </form>

        <Dialog open={usageDialogOpen} onOpenChange={(_, data) => setUsageDialogOpen(data.open)}>
          <DialogSurface>
            <DialogBody>
              <DialogTitle>Model đang dùng</DialogTitle>
              <DialogContent>
                <div className="usage-dialog-content">
                  <p><strong>Model hiện tại:</strong> {selectedModel.name} (<code>{selectedModel.id}</code>)</p>
                  <p>{selectedModel.description}</p>
                  {capacity?.local_budget ? (
                    <div className="usage-budget-grid">
                      <p><strong>Key đã chọn:</strong> {capacity.active_display_name || capacity.credential_source}</p>
                      <p><strong>Project/key hiệu lực:</strong> {capacity.display_name || capacity.credential_source}{capacity.failover_active ? ' (dự phòng)' : ''}</p>
                      <p><strong>Ledger hôm nay:</strong> {capacity.local_budget.daily_used}/{capacity.local_budget.daily_limit} lượt đã ghi nhận</p>
                      <p><strong>Cửa sổ 60 giây:</strong> {capacity.local_budget.minute_used}/{capacity.local_budget.minute_limit} lượt</p>
                      <p><strong>Reset:</strong> {new Date(capacity.local_budget.resets_at).toLocaleString('vi-VN')}</p>
                      <p><strong>Model dự phòng:</strong> <code>{capacity.fallback_model}</code></p>
                    </div>
                  ) : null}
                  <p className="usage-dialog-note">
                    {capacity?.provider_balance_note || 'Veridra chưa đọc được trạng thái năng lực AI. Hãy kiểm tra key trong Cài đặt.'}
                  </p>
                </div>
              </DialogContent>
              <DialogActions>
                <Button appearance="primary" onClick={() => setUsageDialogOpen(false)}>Đóng</Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>

        <Dialog open={Boolean(feedbackTarget)} onOpenChange={(_, data) => { if (!data.open) setFeedbackTarget(null) }}>
          <DialogSurface>
            <DialogBody>
              <DialogTitle>Câu trả lời chưa ổn ở điểm nào?</DialogTitle>
              <DialogContent>
                <p>Chọn các vấn đề bạn gặp. Phản hồi này chỉ được dùng để đo và cải thiện chất lượng trên tài khoản của bạn.</p>
                <div className="feedback-reason-grid">
                  {feedbackReasons.map(reason => <button type="button" key={reason.id}
                    aria-pressed={feedbackReasonSelection.includes(reason.id)}
                    onClick={() => setFeedbackReasonSelection(current => current.includes(reason.id)
                      ? current.filter(item => item !== reason.id) : [...current, reason.id])}>
                    {reason.label}
                  </button>)}
                </div>
                <label className="feedback-comment-label" htmlFor="feedback-comment">Ghi chú thêm (không bắt buộc)</label>
                <Textarea id="feedback-comment" rows={4} value={feedbackComment} onChange={(_, data) => setFeedbackComment(data.value)} placeholder="Ví dụ: bảng thiếu tiêu chí chi phí và citation [2] mở sai file…" />
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setFeedbackTarget(null)}>Hủy</Button>
                <Button appearance="primary" disabled={!feedbackTarget || feedbackReasonSelection.length === 0}
                  onClick={() => feedbackTarget && void rateAnswer(feedbackTarget, 'not_helpful', feedbackReasonSelection, feedbackComment)}>
                  Gửi đánh giá
                </Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>

        <MessageBar intent="info">
          <MessageBarBody>
            Tất cả thao tác ghi và gửi email đều yêu cầu xác nhận 2 pha từ bạn (Human-in-the-Loop).
          </MessageBarBody>
        </MessageBar>
      </section>

      {zoomedDiagram ? (
        <div className="diagram-lightbox-backdrop" onClick={() => setZoomedDiagram(null)}>
          <div className="diagram-lightbox-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontWeight: 600 }}>Sơ đồ trực quan</span>
              <Button appearance="subtle" icon={<Dismiss16Regular />} onClick={() => setZoomedDiagram(null)} aria-label="Đóng" />
            </div>
            <div dangerouslySetInnerHTML={{ __html: zoomedDiagram }} style={{ overflow: 'auto', display: 'flex', justifyContent: 'center' }} />
          </div>
        </div>
      ) : null}

      {zoomedImage ? (
        <div className="diagram-lightbox-backdrop" onClick={() => setZoomedImage(null)}>
          <div className="diagram-lightbox-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontWeight: 600 }}>{zoomedImage.alt || 'Hình ảnh tài liệu'}</span>
              <Button appearance="subtle" icon={<Dismiss16Regular />} onClick={() => setZoomedImage(null)} aria-label="Đóng" />
            </div>
            <img src={zoomedImage.src} alt={zoomedImage.alt} style={{ maxWidth: '100%', maxHeight: '75vh', objectFit: 'contain', borderRadius: '8px' }} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
