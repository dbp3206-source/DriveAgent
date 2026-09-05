import { Badge, Button, Dropdown, Option, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow } from '@fluentui/react-components'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import type { User, Role } from '../types'

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

  useEffect(() => { void load() }, [load])

  async function updateRole(user: User, role: Role) {
    await api(`/api/admin/users/${user.id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) })
    await load()
  }

  if (currentUser.role !== 'super_admin') {
    return <EmptyState title="Khu vực dành cho super admin" description={`Bạn đang có vai trò ${roleLabels[currentUser.role]}. Bạn vẫn quản lý được dữ liệu của chính mình.`} />
  }

  return (
    <section className="stack-page">
      <div className="page-heading"><div><h2>Vai trò ứng dụng</h2><p>RBAC của DriveAgent và OAuth scope của Google là hai lớp kiểm tra độc lập.</p></div><Button onClick={load}>Làm mới</Button></div>
      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <LoadingState /> : null}
      {!loading ? <div className="table-scroll"><Table aria-label="Người dùng và vai trò">
        <TableHeader><TableRow><TableHeaderCell>Người dùng</TableHeaderCell><TableHeaderCell>Vai trò</TableHeaderCell><TableHeaderCell>Quyền ứng dụng</TableHeaderCell><TableHeaderCell>OAuth scopes</TableHeaderCell></TableRow></TableHeader>
        <TableBody>{users.map((user) => <TableRow key={user.id}>
          <TableCell><strong>{user.display_name}</strong><div className="muted">{user.email}</div></TableCell>
          <TableCell>{user.id === currentUser.id ? <Badge appearance="tint">{roleLabels[user.role]}</Badge> : <Dropdown aria-label={`Đổi vai trò của ${user.display_name}`} value={roleLabels[user.role]} selectedOptions={[user.role]} onOptionSelect={(_, data) => updateRole(user, data.optionValue as Role)}>{Object.entries(roleLabels).map(([value, label]) => <Option key={value} value={value}>{label}</Option>)}</Dropdown>}</TableCell>
          <TableCell><div className="permission-list">{(roles[user.role] ?? []).map((permission) => <code key={permission}>{permission}</code>)}</div></TableCell>
          <TableCell>{user.scopes.length} scope</TableCell>
        </TableRow>)}</TableBody>
      </Table></div> : null}
    </section>
  )
}
