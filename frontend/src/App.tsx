import { FluentProvider, Spinner, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { lazy, Suspense, useEffect, useState } from 'react'
import { api } from './api'
import { AppShell, type PageKey } from './components/AppShell'
import { ErrorState } from './components/AsyncState'
import { SetupGate } from './components/SetupGate'
import type { AuthStatus, Health } from './types'

// Tải từng khu vực khi cần để màn hình đầu không phải nhận toàn bộ Fluent Table/Dialog.
const AccessPage = lazy(() => import('./pages/AccessPage').then((module) => ({ default: module.AccessPage })))
const AuditPage = lazy(() => import('./pages/AuditPage').then((module) => ({ default: module.AuditPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then((module) => ({ default: module.ChatPage })))
const DrivePage = lazy(() => import('./pages/DrivePage').then((module) => ({ default: module.DrivePage })))
const MemoryPage = lazy(() => import('./pages/MemoryPage').then((module) => ({ default: module.MemoryPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })))

function preferredDarkMode() {
  const saved = localStorage.getItem('drive-agent-theme')
  if (saved) return saved === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export default function App() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [page, setPage] = useState<PageKey>('chat')
  const [dark, setDark] = useState(preferredDarkMode)
  const [error, setError] = useState('')

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
    const pageContent: Record<PageKey, React.ReactNode> = {
      chat: <ChatPage />,
      drive: <DrivePage />,
      memory: <MemoryPage />,
      audit: <AuditPage />,
      access: <AccessPage currentUser={status.user} />,
      settings: <SettingsPage status={status} health={health} />,
    }
    content = <AppShell user={status.user} page={page} onPageChange={setPage} dark={dark} onThemeChange={() => setDark((value) => !value)}>
      <Suspense fallback={<Spinner label="Đang mở khu vực" />}>{pageContent[page]}</Suspense>
    </AppShell>
  }

  return <FluentProvider theme={dark ? webDarkTheme : webLightTheme}>{content}</FluentProvider>
}
