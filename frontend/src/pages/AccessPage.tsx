import {
  Badge,
  Button,
  Dropdown,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components'
import {
  ArrowClockwise20Regular,
  CheckmarkCircle20Regular,
  Person20Regular,
  ShieldCheckmark24Regular,
  Warning20Regular,
} from '@fluentui/react-icons'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { Role, User } from '../types'

const roleLabels: Record<Role, string> = {
  super_admin: 'Super admin',
  owner: 'Owner',
  editor: 'Editor',
  viewer: 'Viewer',
}

export function AccessPage({ currentUser }: { currentUser: User }) {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Record<string, string[]>>({})
  const [loading, setLoading] = useState(currentUser.role === 'super_admin')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (currentUser.role !== 'super_admin') return
    setLoading(true)
    setError('')
    try {
      const [userRows, roleMap] = await Promise.all([
        api<User[]>('/api/admin/users'),
        api<Record<string, string[]>>('/api/admin/roles'),
      ])
      setUsers(userRows)
      setRoles(roleMap)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải phân quyền.')
    } finally {
      setLoading(false)
    }
  }, [currentUser.role])

  useEffect(() => {
    void load()
  }, [load])

  async function updateRole(user: User, role: Role) {
    await api(`/api/admin/users/${user.id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) })
    await load()
  }

  if (currentUser.role !== 'super_admin') {
    return (
      <EmptyState
        title="Khu vực dành cho Super admin"
        description={`Bạn đang đăng nhập với vai trò ${roleLabels[currentUser.role]}. Bạn vẫn có toàn quyền kiểm soát dữ liệu tài liệu cá nhân.`}
      />
    )
  }

  return (
    <section className="stack-page access-page-v2">
      {/* Header with artistic typography */}
      <div className="page-heading">
        <div>
          <div className="page-heading-kicker-row">
            <span className="home-kicker">RBAC & OAuth Security Matrix</span>
            <Badge appearance="filled" color="brand">Dual-Layer Security</Badge>
          </div>
          <h2 className="artistic-page-title">Vai trò & Phân quyền ứng dụng</h2>
          <p>
            Mỗi thao tác cần được cho phép trong Veridra và được Google cấp quyền.
          </p>
        </div>
        <div className="page-heading__actions">
          <Button icon={<ArrowClockwise20Regular />} onClick={load}>Làm mới quyền</Button>
        </div>
      </div>

      {/* Security Architecture Explainer Banner */}
      <div className="access-security-banner">
        <ShieldCheckmark24Regular style={{ color: '#3b82f6', fontSize: '28px', flexShrink: 0 }} />
        <div className="banner-content">
          <strong>Cơ chế bảo mật: cần đủ hai quyền</strong>
          <ol className="access-security-checks">
            <li>
              <span className="access-security-check__number">01</span>
              <span><b>Quyền trong Veridra</b><small>Vai trò cho phép hành động · ví dụ <code>gmail:send</code></small></span>
            </li>
            <li>
              <span className="access-security-check__number">02</span>
              <span><b>Quyền Google</b><small>Tài khoản đã cấp OAuth scope · ví dụ <code>gmail.send</code></small></span>
            </li>
          </ol>
          <p className="access-security-outcome">Thiếu một trong hai → Agent dừng trước khi gọi công cụ.</p>
        </div>
      </div>

      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}

      {!loading && (
        <div className="access-table-wrapper">
          <div className="table-scroll">
            <Table aria-label="Bảng người dùng và ma trận phân quyền" className="access-table">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell style={{ minWidth: '220px' }}>Người dùng & Định danh</TableHeaderCell>
                  <TableHeaderCell style={{ minWidth: '150px' }}>Vai trò hệ thống</TableHeaderCell>
                  <TableHeaderCell style={{ minWidth: '320px' }}>Quyền ứng dụng (RBAC)</TableHeaderCell>
                  <TableHeaderCell style={{ minWidth: '320px' }}>Google OAuth Scopes đã cấp</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => {
                  const userPerms = roles[user.role] ?? []
                  const hasGmailSendPerm = userPerms.includes('gmail:send')
                  const hasGmailSendScope = user.scopes.some((s) => s.includes('gmail.send'))

                  return (
                    <TableRow key={user.id} className="access-table-row">
                      {/* User Info Cell */}
                      <TableCell>
                        <div className="access-user-cell">
                          <div className="user-avatar-badge">
                            <Person20Regular />
                          </div>
                          <div>
                            <strong className="user-name">{user.display_name || 'Người dùng'}</strong>
                            <span className="user-email">{user.email}</span>
                            <small className="user-id-code">ID: {user.id.slice(0, 8)}</small>
                          </div>
                        </div>
                      </TableCell>

                      {/* Role Cell */}
                      <TableCell>
                        {user.id === currentUser.id ? (
                          <div className="current-user-role-pill">
                            <Badge appearance="filled" color="brand">
                              {roleLabels[user.role]}
                            </Badge>
                            <span className="role-self-hint">Tài khoản của bạn</span>
                          </div>
                        ) : (
                          <Dropdown
                            aria-label={`Đổi vai trò của ${user.display_name}`}
                            value={roleLabels[user.role]}
                            selectedOptions={[user.role]}
                            onOptionSelect={(_, data) => updateRole(user, data.optionValue as Role)}
                          >
                            {Object.entries(roleLabels).map(([value, label]) => (
                              <Option key={value} value={value} text={label}>
                                {label}
                              </Option>
                            ))}
                          </Dropdown>
                        )}
                      </TableCell>

                      {/* Permissions List Cell */}
                      <TableCell>
                        <div className="permission-chips-grid">
                          {userPerms.map((permission) => {
                            const isMutating = permission.includes('write') || permission.includes('send') || permission.includes('manage')
                            return (
                              <span
                                key={permission}
                                className={`perm-chip ${isMutating ? 'perm-chip--mutating' : 'perm-chip--read'}`}
                              >
                                {permission}
                              </span>
                            )
                          })}
                        </div>
                      </TableCell>

                      {/* OAuth Scopes Cell */}
                      <TableCell>
                        <div className="scopes-chips-grid">
                          {user.scopes.map((scope) => {
                            const cleanScope = scope.replace('https://www.googleapis.com/auth/', '')
                            const isSensitive = cleanScope.includes('send') || cleanScope.includes('file')
                            return (
                              <span
                                key={scope}
                                className={`scope-chip ${isSensitive ? 'scope-chip--sensitive' : 'scope-chip--normal'}`}
                              >
                                <CheckmarkCircle20Regular className="scope-check-icon" />
                                {cleanScope}
                              </span>
                            )
                          })}
                          {/* If RBAC has gmail:send but scope is truly missing */}
                          {hasGmailSendPerm && !hasGmailSendScope && (
                            <span
                              className="scope-chip scope-chip--warning"
                              title="RBAC cấp quyền gửi thư nhưng Google OAuth phiên này chưa nhận scope gmail.send"
                            >
                              <Warning20Regular className="scope-warn-icon" />
                              gmail.send (chờ cấp)
                            </span>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </section>
  )
}
