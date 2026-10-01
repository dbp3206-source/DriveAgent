import { Avatar, Button, Spinner, Tooltip } from '@fluentui/react-components'
import {
  Chat24Regular,
  Mail24Regular,
  Home24Regular,
  LearningApp24Regular,
  Wand24Regular,
  Database24Regular,
  DocumentBulletList24Regular,
  Folder24Regular,
  Navigation24Regular,
  People24Regular,
  Settings24Regular,
  WeatherMoon24Regular,
  WeatherSunny24Regular,
} from '@fluentui/react-icons'
import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { hasDriveReadScope, hasGmailReadScope } from '../integrationStatus.mjs'
import type { User } from '../types'
import { MascotAssistant } from './MascotAssistant'
import { VeridraMark } from './VeridraMark'
import { WorkspaceCanvas } from './WorkspaceCanvas'

export type PageKey =
  | 'home'
  | 'chat'
  | 'drive'
  | 'gmail'
  | 'local'
  | 'artifacts'
  | 'memory'
  | 'harness'
  | 'audit'
  | 'access'
  | 'settings'
  | 'skills'

type IntegrationHealth = 'authorized' | 'healthy' | 'degraded' | 'permission' | 'misconfigured'

interface NavItemDef {
  key: PageKey
  label: string
  icon: React.ReactNode
}

const navItems: NavItemDef[] = [
  { key: 'home', label: 'Bắt đầu', icon: <Home24Regular /> },
  { key: 'chat', label: 'Trò chuyện', icon: <Chat24Regular /> },
  { key: 'drive', label: 'Google Drive', icon: <Folder24Regular /> },
  { key: 'gmail', label: 'Gmail', icon: <Mail24Regular /> },
  { key: 'local', label: 'Tài liệu local', icon: <Folder24Regular /> },
  { key: 'artifacts', label: 'Kết quả đã lưu', icon: <DocumentBulletList24Regular /> },
  { key: 'skills', label: 'Skills của tôi', icon: <Wand24Regular /> },
  { key: 'memory', label: 'Bộ nhớ', icon: <Database24Regular /> },
  { key: 'harness', label: 'Cách Agent hoạt động', icon: <LearningApp24Regular /> },
  { key: 'audit', label: 'Nhật ký', icon: <DocumentBulletList24Regular /> },
  { key: 'access', label: 'Phân quyền', icon: <People24Regular /> },
  { key: 'settings', label: 'Cài đặt', icon: <Settings24Regular /> },
]

export function AppShell({
  user,
  page,
  onPageChange,
  dark,
  onThemeChange,
  isChatBusy = false,
  isChatDoneNotice = false,
  children,
}: {
  user: User
  page: PageKey
  onPageChange: (page: PageKey) => void
  dark: boolean
  onThemeChange: () => void
  isChatBusy?: boolean
  isChatDoneNotice?: boolean
  children: React.ReactNode
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [canvasMotion, setCanvasMotion] = useState(() => {
    try { return localStorage.getItem('veridra-canvas-motion') !== 'off' } catch { return false }
  })
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 980px)').matches)
  const menuRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  const [integrationHealth, setIntegrationHealth] = useState<Record<'drive' | 'gmail', IntegrationHealth>>({
    drive: 'authorized',
    gmail: 'authorized',
  })

  useEffect(() => {
    const query = window.matchMedia('(max-width: 980px)')
    const update = () => { setNarrow(query.matches); if (!query.matches) setMobileOpen(false) }
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (mobileOpen) sidebarRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [mobileOpen])

  useEffect(() => {
    // Announce SPA route changes to keyboard and screen-reader users without
    // stealing focus during ordinary content updates or when the mobile menu
    // closes. ``closeMenu`` returns focus to its trigger separately.
    document.getElementById('main-content')?.focus()
  }, [page])

  useEffect(() => {
    setIntegrationHealth({ drive: 'authorized', gmail: 'authorized' })
    const onIntegrationStatus = (event: Event) => {
      const detail = (event as CustomEvent<{ service?: string; status?: string }>).detail
      if ((detail?.service === 'drive' || detail?.service === 'gmail')
        && (detail.status === 'healthy' || detail.status === 'degraded'
          || detail.status === 'permission' || detail.status === 'misconfigured')) {
        setIntegrationHealth((current) => ({ ...current, [detail.service!]: detail.status as IntegrationHealth }))
      }
    }
    window.addEventListener('driveagent:integration-status', onIntegrationStatus)
    return () => window.removeEventListener('driveagent:integration-status', onIntegrationStatus)
  }, [user.id])

  const closeMenu = () => { setMobileOpen(false); menuRef.current?.focus() }
  const current = navItems.find((item) => item.key === page)!
  const driveConnected = hasDriveReadScope(user.scopes)
  const gmailConnected = hasGmailReadScope(user.scopes)
  const driveStatus = driveConnected ? integrationHealth.drive : 'missing'
  const gmailStatus = gmailConnected ? integrationHealth.gmail : 'missing'

  function integrationLabel(service: 'Drive' | 'Gmail', status: IntegrationHealth | 'missing') {
    if (status === 'healthy') return `${service} đã phản hồi thành công trong phiên này.`
    if (status === 'degraded') return `${service} đang tạm gián đoạn. Kiểm tra kết nối rồi thử lại.`
    if (status === 'permission') return `Google chưa cho phép đọc ${service}. Hãy kiểm tra lại quyền đã cấp.`
    if (status === 'misconfigured') return `API ${service} chưa được bật trong Google Cloud project.`
    if (status === 'authorized') return `Đã cấp quyền ${service}; chưa kiểm tra kết nối trong phiên này.`
    return `Chưa cấp đủ phạm vi đọc ${service}.`
  }

  function integrationMark(status: IntegrationHealth | 'missing') {
    if (status === 'healthy') return '●'
    if (status === 'degraded' || status === 'permission' || status === 'misconfigured') return '!'
    return '○'
  }

  const navigate = (next: PageKey) => {
    onPageChange(next)
    setMobileOpen(false)
  }

  const skipToMainContent = (event: MouseEvent<HTMLAnchorElement>) => {
    // The application route also lives in location.hash (for example #/chat),
    // so native #main-content navigation would overwrite the active route.
    event.preventDefault()
    const main = document.getElementById('main-content')
    window.requestAnimationFrame(() => {
      main?.focus({ preventScroll: true })
      main?.scrollIntoView({ block: 'start' })
    })
  }

  return (
    <div className={`app-shell app-shell--${page}`}>
      <a className="skip-link" href="#main-content" onClick={skipToMainContent}>Đến nội dung chính</a>
      <aside
        id="main-navigation"
        ref={sidebarRef}
        inert={narrow && !mobileOpen}
        className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`}
        aria-label="Điều hướng chính"
        onKeyDown={(event) => {
          if (!narrow || !mobileOpen) return
          if (event.key === 'Escape') { event.preventDefault(); closeMenu() }
          if (event.key === 'Tab') {
            const buttons = sidebarRef.current?.querySelectorAll<HTMLButtonElement>('button')
            if (!buttons?.length) return
            if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1]?.focus() }
            if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0]?.focus() }
          }
        }}
      >
        {narrow ? <Button appearance="subtle" onClick={closeMenu}>Đóng menu</Button> : null}
        <div className="brand-lockup brand-lockup--sidebar">
          <VeridraMark />
          <span>Veridra</span>
        </div>
        <div className="nav-list-wrapper">
          <nav className="nav-list" aria-label="Điều hướng chính">
            {navItems.map((item) => (
              <button
                type="button"
                key={item.key}
                className={`nav-item ${page === item.key ? 'nav-item--active' : ''}`}
                aria-current={page === item.key ? 'page' : undefined}
                aria-label={item.label}
                title={item.label}
                onClick={() => navigate(item.key)}
              >
                {item.icon}
                <span>{item.label}</span>
                {item.key === 'chat' && isChatBusy && (
                  <span className="nav-busy-pulse" title="Đang xử lý câu hỏi..." />
                )}
              </button>
            ))}
          </nav>
          <div className="nav-scroll-fade" aria-hidden="true" />
        </div>
        <div className="sidebar-user">
          <Avatar
            name={user.display_name}
            image={user.avatar_url ? { src: user.avatar_url } : undefined}
            className="sidebar-user__avatar"
          />
          <div className="sidebar-user__copy">
            <strong title={user.display_name}>{user.display_name}</strong>
            <span className="sidebar-user__badge">{user.role.replace('_', ' ')}</span>
          </div>
        </div>
      </aside>
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Đóng menu"
          className="sidebar-scrim"
          onClick={closeMenu}
        />
      ) : null}
      <section className="workspace">
        <WorkspaceCanvas animate={page === 'home' && canvasMotion} />
        <header className="topbar">
          <Button
            ref={menuRef}
            className="mobile-menu"
            appearance="subtle"
            icon={<Navigation24Regular />}
            aria-label="Mở menu"
            aria-expanded={mobileOpen}
            aria-controls="main-navigation"
            onClick={() => setMobileOpen(true)}
          />
          <div>
            <p className="topbar__context">Không gian học tập & công việc</p>
            <h1>{current.label}</h1>
          </div>
          <div className="topbar__actions">
            {page === 'home' ? <Button appearance="subtle" aria-pressed={canvasMotion} onClick={() => {
              setCanvasMotion(value => {
                const next = !value
                try { localStorage.setItem('veridra-canvas-motion', next ? 'on' : 'off') } catch { /* Optional preference storage. */ }
                return next
              })
            }}>{canvasMotion ? 'Tắt nền động' : 'Bật nền động'}</Button> : null}
            {isChatBusy && page !== 'chat' && (
              <button
                type="button"
                className="topbar-chat-indicator"
                onClick={() => onPageChange('chat')}
                title="Bấm để quay lại xem câu trả lời đang xử lý"
              >
                <Spinner size="extra-tiny" />
                <span>Đang xử lý trong Trò chuyện...</span>
              </button>
            )}
            {!isChatBusy && isChatDoneNotice && page !== 'chat' && (
              <button
                type="button"
                className="topbar-chat-indicator topbar-chat-indicator--done"
                onClick={() => onPageChange('chat')}
                title="Veridra đã hoàn thành câu trả lời. Bấm để xem"
              >
                <span className="indicator-check">✓</span>
                <span>Đã có câu trả lời mới trong Trò chuyện</span>
              </button>
            )}
            <div className="connection-badges">
              <span
                className={`connection-state ${driveStatus === 'healthy' ? 'connection-state--ok' : ''} ${['degraded', 'permission', 'misconfigured'].includes(driveStatus) ? 'connection-state--degraded' : ''} ${driveStatus === 'missing' ? 'connection-state--missing' : ''}`}
                title={integrationLabel('Drive', driveStatus)}
                aria-label={`Trạng thái Google Drive: ${integrationLabel('Drive', driveStatus)}`}
              >
                {integrationMark(driveStatus)} Drive
              </span>
              {gmailConnected ? (
                <span
                  className={`connection-state ${gmailStatus === 'healthy' ? 'connection-state--ok' : ''} ${['degraded', 'permission', 'misconfigured'].includes(gmailStatus) ? 'connection-state--degraded' : ''}`}
                  title={integrationLabel('Gmail', gmailStatus)}
                  aria-label={`Trạng thái Gmail: ${integrationLabel('Gmail', gmailStatus)}`}
                >
                  {integrationMark(gmailStatus)} Gmail
                </span>
              ) : (
                <a
                  href="/api/auth/google"
                  className="connection-state connection-state--actionable"
                  title="Chưa cấp quyền Gmail. Bấm vào đây để kết nối lại và cấp quyền Gmail"
                >
                  Cấp quyền Gmail
                </a>
              )}
            </div>
            <Tooltip content={dark ? 'Dùng giao diện sáng' : 'Dùng giao diện tối'} relationship="label">
              <Button
                appearance="subtle"
                icon={dark ? <WeatherSunny24Regular /> : <WeatherMoon24Regular />}
                onClick={onThemeChange}
              />
            </Tooltip>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="page-content">{children}</main>
        <MascotAssistant
          status={isChatBusy ? 'running' : isChatDoneNotice ? 'completed' : 'idle'}
          currentPage={page}
          onNavigateToChat={() => onPageChange('chat')}
        />
      </section>
    </div>
  )
}
