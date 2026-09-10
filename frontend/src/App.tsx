import { FluentProvider, Spinner, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AppShell, type PageKey } from './components/AppShell'
import { ErrorState } from './components/AsyncState'
import { SetupGate } from './components/SetupGate'
import { ScreenBoundary } from './components/ScreenBoundary'
import type { AuthStatus, Health } from './types'

// Tải từng khu vực khi cần để màn hình đầu không phải nhận toàn bộ Fluent Table/Dialog.
const AccessPage = lazy(() => import('./pages/AccessPage').then((module) => ({ default: module.AccessPage })))
const ArtifactsPage = lazy(() => import('./pages/ArtifactsPage').then((module) => ({ default: module.ArtifactsPage })))
const LocalSourcesPage = lazy(() => import('./pages/LocalSourcesPage').then((module) => ({ default: module.LocalSourcesPage })))
const AuditPage = lazy(() => import('./pages/AuditPage').then((module) => ({ default: module.AuditPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then((module) => ({ default: module.ChatPage })))
const DrivePage = lazy(() => import('./pages/DrivePage').then((module) => ({ default: module.DrivePage })))
const MemoryPage = lazy(() => import('./pages/MemoryPage').then((module) => ({ default: module.MemoryPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })))
const HomePage = lazy(() => import('./pages/HomePage').then((module) => ({ default: module.HomePage })))
const HarnessPage = lazy(() => import('./pages/HarnessPage').then((module) => ({ default: module.HarnessPage })))
const VisualsPage = lazy(() => import('./pages/VisualsPage').then((module) => ({ default: module.VisualsPage })))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then((module) => ({ default: module.SkillsPage })))

function preferredDarkMode() {
  const saved = localStorage.getItem('drive-agent-theme')
  if (saved) return saved === 'dark'
  return true
}

export default function App() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [page, setPageState] = useState<PageKey>(() => {
    try {
      const saved = sessionStorage.getItem('drive_agent_active_page') as PageKey | null
      return saved || 'home'
    } catch {
      return 'home'
    }
  })
  const [dark, setDark] = useState(preferredDarkMode)
  const [error, setError] = useState('')
  const [isChatBusy, setIsChatBusy] = useState(false)
  const [chatCompletedNotice, setChatCompletedNotice] = useState(false)
  const prevBusy = useRef(isChatBusy)

  const setPage = (next: PageKey) => {
    setPageState(next)
    try {
      sessionStorage.setItem('drive_agent_active_page', next)
    } catch {
      // ignore
    }
  }

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
    if (isChatBusy) {
      document.title = '● Đang xử lý... | DriveAgent'
    } else if (chatCompletedNotice) {
      document.title = '✓ Có kết quả mới! | DriveAgent'
    } else {
      document.title = 'DriveAgent - Trợ lý Google Drive & Gmail'
    }
  }, [isChatBusy, chatCompletedNotice])

  async function load() {
    setError('')
    try {
      const [auth, system] = await Promise.all([
        api<AuthStatus>('/api/auth/status'),
        api<Health>('/api/health'),
      ])
      setStatus(auth)
      setHealth(system)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể kết nối backend.')
    }
  }

  useEffect(() => { void load() }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('drive-agent-theme', dark ? 'dark' : 'light')
  }, [dark])

  let content: React.ReactNode
  if (error) {
    content = <main className="fatal-state"><ErrorState message={error} retry={load} /></main>
  } else if (!status) {
    content = <main className="fatal-state"><Spinner label="Đang kiểm tra cấu hình DriveAgent" /></main>
  } else if (!status.authenticated || !status.user) {
    content = <SetupGate status={status} />
  } else {
    const pageContent: Partial<Record<PageKey, React.ReactNode>> = {
      home: <HomePage onNavigate={setPage} />,
      artifacts: <ArtifactsPage />,
      visuals: <VisualsPage />,
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
        <div
          className={`chat-tab-container ${page === 'chat' ? '' : 'chat-tab-container--hidden'}`}
          aria-hidden={page !== 'chat'}
        >
          <Suspense fallback={<Spinner label="Đang mở cuộc trò chuyện" />}>
            <ChatPage onBusyChange={setIsChatBusy} />
          </Suspense>
        </div>

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
