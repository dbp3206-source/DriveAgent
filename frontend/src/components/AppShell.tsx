import { Avatar, Button, Tooltip } from '@fluentui/react-components'
import {
  Chat24Regular,
  Database24Regular,
  DocumentBulletList24Regular,
  Folder24Regular,
  Navigation24Regular,
  People24Regular,
  Settings24Regular,
  WeatherMoon24Regular,
  WeatherSunny24Regular,
} from '@fluentui/react-icons'
import { useState } from 'react'
import type { User } from '../types'

export type PageKey = 'chat' | 'drive' | 'memory' | 'audit' | 'access' | 'settings'

const navItems: Array<{ key: PageKey; label: string; icon: React.ReactNode }> = [
  { key: 'chat', label: 'Trò chuyện', icon: <Chat24Regular /> },
  { key: 'drive', label: 'Google Drive', icon: <Folder24Regular /> },
  { key: 'memory', label: 'Bộ nhớ', icon: <Database24Regular /> },
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
  children,
}: {
  user: User
  page: PageKey
  onPageChange: (page: PageKey) => void
  dark: boolean
  onThemeChange: () => void
  children: React.ReactNode
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const current = navItems.find((item) => item.key === page)!
  const driveConnected = user.scopes.includes('https://www.googleapis.com/auth/drive.readonly')

  const navigate = (next: PageKey) => {
    onPageChange(next)
    setMobileOpen(false)
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`} aria-label="Điều hướng chính">
        <div className="brand-lockup brand-lockup--sidebar">
          <div className="brand-mark" aria-hidden="true">D</div>
          <span>DriveAgent</span>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.key}
              className={`nav-item ${page === item.key ? 'nav-item--active' : ''}`}
              aria-current={page === item.key ? 'page' : undefined}
              onClick={() => navigate(item.key)}
            >
              {item.icon}
              <span>{item.label}</span>
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
          onClick={() => setMobileOpen(false)}
        />
      ) : null}
      <section className="workspace">
        <header className="topbar">
          <Button
            className="mobile-menu"
            appearance="subtle"
            icon={<Navigation24Regular />}
            aria-label="Mở menu"
            onClick={() => setMobileOpen(true)}
          />
          <div>
            <p className="topbar__context">Không gian của bạn</p>
            <h1>{current.label}</h1>
          </div>
          <div className="topbar__actions">
            <span className={driveConnected ? 'connection-state' : 'connection-state connection-state--missing'}>
              {driveConnected ? 'Drive đã kết nối' : 'Drive chưa cấp quyền'}
            </span>
            <Tooltip content={dark ? 'Dùng giao diện sáng' : 'Dùng giao diện tối'} relationship="label">
              <Button
                appearance="subtle"
                icon={dark ? <WeatherSunny24Regular /> : <WeatherMoon24Regular />}
                onClick={onThemeChange}
              />
            </Tooltip>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </section>
    </div>
  )
}
