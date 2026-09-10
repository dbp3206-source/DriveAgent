import { Avatar, Button, Spinner, Tooltip } from '@fluentui/react-components'
import {
  Chat24Regular,
  Home24Regular,
  LearningApp24Regular,
  Wand24Regular,
  Image24Regular,
  Database24Regular,
  DocumentBulletList24Regular,
  Folder24Regular,
  Navigation24Regular,
  People24Regular,
  Settings24Regular,
  WeatherMoon24Regular,
  WeatherSunny24Regular,
} from '@fluentui/react-icons'
import { useEffect, useRef, useState } from 'react'
import type { User } from '../types'

export type PageKey =
  | 'home'
  | 'chat'
  | 'drive'
  | 'local'
  | 'artifacts'
  | 'visuals'
  | 'memory'
  | 'harness'
  | 'audit'
  | 'access'
  | 'settings'
  | 'skills'

const navItems: Array<{ key: PageKey; label: string; icon: React.ReactNode }> = [
  { key: 'home', label: 'Bắt đầu', icon: <Home24Regular /> },
  { key: 'chat', label: 'Trò chuyện', icon: <Chat24Regular /> },
  { key: 'drive', label: 'Google Drive', icon: <Folder24Regular /> },
  { key: 'local', label: 'Tài liệu local', icon: <Folder24Regular /> },
  { key: 'artifacts', label: 'Kết quả đã lưu', icon: <DocumentBulletList24Regular /> },
  { key: 'visuals', label: 'Visual Studio', icon: <Image24Regular /> },
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
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 980px)').matches)
  const menuRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 980px)')
    const update = () => { setNarrow(query.matches); if (!query.matches) setMobileOpen(false) }
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (mobileOpen) sidebarRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [mobileOpen])
  const closeMenu = () => { setMobileOpen(false); menuRef.current?.focus() }
  const current = navItems.find((item) => item.key === page)!
  const driveConnected = user.scopes.some(s => s.includes('drive'))
  const gmailConnected = user.scopes.some(s => s.includes('gmail'))

  const navigate = (next: PageKey) => {
    onPageChange(next)
    setMobileOpen(false)
  }

  return (
    <div className={`app-shell app-shell--${page}`}>
      <a className="skip-link" href="#main-content">Đến nội dung chính</a>
      <aside id="main-navigation" ref={sidebarRef} inert={narrow && !mobileOpen}
        className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`} aria-label="Điều hướng chính"
        onKeyDown={(event) => {
          if (!narrow || !mobileOpen) return
          if (event.key === 'Escape') { event.preventDefault(); closeMenu() }
          if (event.key === 'Tab') {
            const buttons = sidebarRef.current?.querySelectorAll<HTMLButtonElement>('button')
            if (!buttons?.length) return
            if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1]?.focus() }
            if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0]?.focus() }
          }
        }}>
        {narrow ? <Button appearance="subtle" onClick={closeMenu}>Đóng menu</Button> : null}
        <div className="brand-lockup brand-lockup--sidebar">
          <div className="brand-mark" aria-hidden="true">DA</div>
          <span>DriveAgent</span>
        </div>
        <nav className="nav-list">
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
        <div className="sidebar-user">
          <Avatar name={user.display_name} image={user.avatar_url ? { src: user.avatar_url } : undefined} />
          <div className="sidebar-user__copy">
            <strong>{user.display_name}</strong>
            <span>{user.role.replace('_', ' ')}</span>
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
                title="DriveAgent đã hoàn thành câu trả lời! Bấm để xem"
              >
                <span className="indicator-check">✓</span>
                <span>Đã có câu trả lời mới trong Trò chuyện</span>
              </button>
            )}
            <div className="connection-badges">
              <span className={`connection-state ${driveConnected ? 'connection-state--ok' : 'connection-state--missing'}`}>
                {driveConnected ? '● Drive' : '○ Drive'}
              </span>
              {gmailConnected ? (
                <span className="connection-state connection-state--ok" title="Gmail đã kết nối">
                  ● Gmail
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
      </section>
    </div>
  )
}
