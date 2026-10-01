import { FluentProvider, Spinner, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AppShell, type PageKey } from './components/AppShell'
import { ErrorState } from './components/AsyncState'
import { SetupGate } from './components/SetupGate'
import { ScreenBoundary } from './components/ScreenBoundary'
import { hashForPage, pageFromHash } from './pageRoute.mjs'
import { roleCanCreateDraft, roleCanSendEmail } from './emailWorkflow.mjs'
import type { AuthStatus, Health } from './types'

const PAGE_KEYS: readonly PageKey[] = [
  'home', 'chat', 'drive', 'gmail', 'local', 'artifacts', 'memory',
  'harness', 'audit', 'access', 'settings', 'skills',
]

/**
 * A running tab can outlive a local rebuild.  In that case the old app shell
 * may request a hashed lazy chunk that the new build has replaced.  Reload one
 * time to pick up the new entrypoint; leave the boundary's explicit retry in
 * place for a real offline/network failure instead of creating a reload loop.
 */
type LazyLoader = Parameters<typeof lazy>[0]

function lazyWithChunkRecovery(loader: LazyLoader) {
  return lazy(async () => {
    try {
      return await loader()
    } catch (error) {
      let hasRetried = false
      try {
        hasRetried = sessionStorage.getItem('drive-agent-chunk-reload') === '1'
        if (!hasRetried) sessionStorage.setItem('drive-agent-chunk-reload', '1')
      } catch {
        // Storage may be unavailable; the boundary below remains the fallback.
      }
      if (!hasRetried) window.location.reload()
      throw error
    }
  })
}

function isPageKey(value: string | null): value is PageKey {
  return value !== null && PAGE_KEYS.includes(value as PageKey)
}

// Tải từng khu vực khi cần để màn hình đầu không phải nhận toàn bộ Fluent Table/Dialog.
const AccessPage = lazyWithChunkRecovery(() => import('./pages/AccessPage').then((module) => ({ default: module.AccessPage })))
const ArtifactsPage = lazyWithChunkRecovery(() => import('./pages/ArtifactsPage').then((module) => ({ default: module.ArtifactsPage })))
const LocalSourcesPage = lazyWithChunkRecovery(() => import('./pages/LocalSourcesPage').then((module) => ({ default: module.LocalSourcesPage })))
const AuditPage = lazyWithChunkRecovery(() => import('./pages/AuditPage').then((module) => ({ default: module.AuditPage })))
const ChatPage = lazyWithChunkRecovery(() => import('./pages/ChatPage').then((module) => ({ default: module.ChatPage })))
const DrivePage = lazyWithChunkRecovery(() => import('./pages/DrivePage').then((module) => ({ default: module.DrivePage })))
const GmailPage = lazyWithChunkRecovery(() => import('./pages/GmailPage').then((module) => ({ default: module.GmailPage })))
const MemoryPage = lazyWithChunkRecovery(() => import('./pages/MemoryPage').then((module) => ({ default: module.MemoryPage })))
const SettingsPage = lazyWithChunkRecovery(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })))
const HomePage = lazyWithChunkRecovery(() => import('./pages/HomePage').then((module) => ({ default: module.HomePage })))
const HarnessPage = lazyWithChunkRecovery(() => import('./pages/HarnessPage').then((module) => ({ default: module.HarnessPage })))
const SkillsPage = lazyWithChunkRecovery(() => import('./pages/SkillsPage').then((module) => ({ default: module.SkillsPage })))

function preferredDarkMode() {
  const saved = localStorage.getItem('drive-agent-theme')
  if (saved) return saved === 'dark'
  return true
}

export default function App() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [page, setPageState] = useState<PageKey>(() => {
    const routed = pageFromHash(window.location.hash)
    if (isPageKey(routed)) return routed
    try {
      const saved = sessionStorage.getItem('drive_agent_active_page')
      return isPageKey(saved) ? saved : 'home'
    } catch {
      return 'home'
    }
  })
  const [dark, setDark] = useState(preferredDarkMode)
  const [chatOpened, setChatOpened] = useState(page === 'chat')
  const [error, setError] = useState('')
  const [isChatBusy, setIsChatBusy] = useState(false)
  const [chatCompletedNotice, setChatCompletedNotice] = useState(false)
  const prevBusy = useRef(isChatBusy)

  const setPage = (next: PageKey) => {
    if (next === 'chat') setChatOpened(true)
    setPageState(next)
    const nextHash = hashForPage(next)
    if (window.location.hash !== nextHash) {
      window.history.pushState({ driveAgentPage: next }, '', nextHash)
    }
    try {
      sessionStorage.setItem('drive_agent_active_page', next)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    const restoreRoute = () => {
      const routed = pageFromHash(window.location.hash)
      if (isPageKey(routed)) {
        if (routed === 'chat') setChatOpened(true)
        setPageState(routed)
        try {
          sessionStorage.setItem('drive_agent_active_page', routed)
        } catch {
          // Storage is an enhancement; URL navigation must keep working without it.
        }
      }
    }
    window.addEventListener('popstate', restoreRoute)
    window.addEventListener('hashchange', restoreRoute)
    return () => {
      window.removeEventListener('popstate', restoreRoute)
      window.removeEventListener('hashchange', restoreRoute)
    }
  }, [])

  useEffect(() => {
    // Make the current workspace bookmarkable even when it was restored from
    // sessionStorage after opening the bare localhost URL.
    if (!pageFromHash(window.location.hash)) {
      window.history.replaceState({ driveAgentPage: page }, '', hashForPage(page))
    }
  }, [page])

  useEffect(() => {
    if (prevBusy.current && !isChatBusy && page !== 'chat') {
      setChatCompletedNotice(true)
    }
    prevBusy.current = isChatBusy
  }, [isChatBusy, page])

  useEffect(() => {
    if (page === 'chat') {
      setChatCompletedNotice(false)
    }
  }, [page])

  useEffect(() => {
    // Each workspace area behaves like a separate screen. Keeping the previous
    // page's scroll offset can hide the new heading and primary actions.
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [page])

  useEffect(() => {
    if (isChatBusy) {
      document.title = '● Đang xử lý... | Veridra'
    } else if (chatCompletedNotice) {
      document.title = '✓ Có kết quả mới! | Veridra'
    } else {
      document.title = 'Veridra | Verified intelligence in action'
    }
  }, [isChatBusy, chatCompletedNotice])

  async function load() {
    setError('')
    try {
      void api<Health>('/api/health').then(setHealth).catch(() => setHealth(null))
      const auth = await api<AuthStatus>('/api/auth/status')
      setStatus(auth)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chưa kết nối được máy chủ. Hãy thử lại.')
    }
  }

  useEffect(() => { void load() }, [])
  useEffect(() => {
    // A successful shell mount means any previous chunk recovery completed.
    try { sessionStorage.removeItem('drive-agent-chunk-reload') } catch {
      // Storage is optional; routing remains usable without it.
    }
  }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('drive-agent-theme', dark ? 'dark' : 'light')
  }, [dark])

  let content: React.ReactNode
  if (error) {
    content = <main className="fatal-state"><ErrorState message={error} retry={load} /></main>
  } else if (!status) {
    content = <main className="fatal-state"><Spinner label="Đang kiểm tra cấu hình Veridra" /></main>
  } else if (!status.authenticated || !status.user) {
    content = <SetupGate status={status} />
  } else {
    const pageContent: Partial<Record<PageKey, React.ReactNode>> = {
      home: <HomePage onNavigate={setPage} />,
      artifacts: <ArtifactsPage />,
      gmail: <GmailPage
        canCreateDraft={roleCanCreateDraft(status.user.role)}
        canSend={roleCanSendEmail(status.user.role)}
      />,
      skills: <SkillsPage />,
      local: <LocalSourcesPage />,
      drive: <DrivePage />,
      memory: <MemoryPage />,
      harness: <HarnessPage />,
      audit: <AuditPage />,
      access: <AccessPage currentUser={status.user} />,
      settings: <SettingsPage status={status} health={health} />,
    }
    content = (
      <AppShell
        user={status.user}
        page={page}
        onPageChange={setPage}
        dark={dark}
        onThemeChange={() => setDark((value) => !value)}
        isChatBusy={isChatBusy}
        isChatDoneNotice={chatCompletedNotice}
      >
        {chatOpened && <div
          className={`chat-tab-container ${page === 'chat' ? '' : 'chat-tab-container--hidden'}`}
          aria-hidden={page !== 'chat'}
        >
          <Suspense fallback={<Spinner label="Đang mở cuộc trò chuyện" />}>
            <ChatPage onBusyChange={setIsChatBusy} isActive={page === 'chat'} />
          </Suspense>
        </div>}

        {page !== 'chat' && pageContent[page] && (
          <ScreenBoundary key={page}>
            <Suspense fallback={<Spinner label="Đang mở khu vực" />}>
              {pageContent[page]}
            </Suspense>
          </ScreenBoundary>
        )}
      </AppShell>
    )
  }

  const theme = {
    ...(dark ? webDarkTheme : webLightTheme),
    fontFamilyBase: '"Be Vietnam Pro", sans-serif',
    borderRadiusSmall: '8px',
    borderRadiusMedium: '12px',
    borderRadiusLarge: '16px',
    borderRadiusXLarge: '20px',
    colorBrandBackground: dark ? '#2563eb' : '#1e40af',
    colorBrandBackgroundHover: dark ? '#3b82f6' : '#1d4ed8',
    colorBrandBackgroundPressed: dark ? '#1d4ed8' : '#172554',
    colorBrandForeground1: dark ? '#60a5fa' : '#1e40af',
    colorCompoundBrandStroke: dark ? '#3b82f6' : '#1e40af',
  }
  return <FluentProvider theme={theme}>{content}</FluentProvider>
}
