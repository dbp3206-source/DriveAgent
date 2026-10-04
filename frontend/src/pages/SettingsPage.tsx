import { Badge, Button, Field, Input, MessageBar, MessageBarBody, Spinner, Switch } from '@fluentui/react-components'
import { ArrowExit24Regular, CheckmarkCircle24Regular, DismissCircle24Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { hasDriveReadScope, hasGmailReadScope } from '../integrationStatus.mjs'
import type { AuthStatus, Health, ProviderCapacity } from '../types'

function StatusLine({ label, ready, detail }: { label: string; ready: boolean; detail: string }) {
  return <div className="status-line">
    <span className={ready ? 'status-icon status-icon--ok' : 'status-icon status-icon--error'}>{ready ? <CheckmarkCircle24Regular /> : <DismissCircle24Regular />}</span>
    <div><strong>{label}</strong><p>{detail}</p></div>
    <Badge appearance="tint" color={ready ? 'success' : 'danger'}>{ready ? 'Đã cấu hình' : 'Cần xử lý'}</Badge>
  </div>
}

const operationLabels: Record<string, string> = {
  docs_create: 'Tạo Google Docs',
  docs_edit: 'Sửa Google Docs',
  sheets_create: 'Tạo Google Sheets',
  sheets_edit: 'Sửa Google Sheets',
  email_send: 'Gửi Gmail',
  gmail_draft_create: 'Tạo bản nháp Gmail',
  slides_create: 'Google Slides · công cụ cũ đã ngừng',
  slides_edit: 'Google Slides · công cụ cũ đã ngừng',
}

const operationErrorLabels: Record<string, string> = {
  google_execution_uncertain: 'Mất phản hồi sau khi gọi Google',
  verification_failed: 'Read-back chưa khớp kết quả mong đợi',
  google_permission_denied: 'Google từ chối quyền ở lần chạy đó',
}

const scopeLabels: Record<string, string> = {
  openid: 'Xác thực danh tính Google',
  email: 'Đọc địa chỉ email tài khoản',
  profile: 'Đọc tên và ảnh hồ sơ',
  'https://www.googleapis.com/auth/drive.readonly': 'Đọc và tìm tệp trong Google Drive',
  'https://www.googleapis.com/auth/drive.file': 'Tạo và sửa tệp do Veridra tạo hoặc được bạn chọn',
  'https://www.googleapis.com/auth/gmail.readonly': 'Đọc thư Gmail để tìm kiếm và tóm tắt',
  'https://www.googleapis.com/auth/gmail.compose': 'Chỉ tạo bản nháp Gmail; không tự gửi thư',
  'https://www.googleapis.com/auth/gmail.send': 'Gửi thư Gmail (quyền cũ; cần thu hồi tại Google Account)',
  'https://www.googleapis.com/auth/gmail.modify': 'Sửa trạng thái Gmail (quyền cũ; cần thu hồi tại Google Account)',
}

type GeminiCredential = {
  id: string
  display_name: string
  project_alias: string
  fingerprint: string
  status: string
  is_active: boolean
  failover_enabled: boolean
  last_validated_at: string | null
  last_error_class: string | null
  cooldown_until: string | null
  created_at: string
  daily_flash_used: number
  circuit_open: boolean
  retry_after_seconds: number
}

export function SettingsPage({ status, health }: { status: AuthStatus; health: Health | null }) {
  const scopes = status.user?.scopes
  const driveReadReady = hasDriveReadScope(scopes)
  const gmailReadReady = hasGmailReadScope(scopes)
  const workspaceReadReady = driveReadReady && gmailReadReady
  // Xin lại đúng các quyền tùy chọn đã dùng; một OAuth flow giữ cả Docs/Sheets
  // và Gmail compose khi tài khoản cần kết nối lại sau khi refresh token hết hạn.
  const hasWorkspaceWrite = (scopes ?? []).includes('https://www.googleapis.com/auth/drive.file')
  const hasGmailCompose = (scopes ?? []).includes('https://www.googleapis.com/auth/gmail.compose')
  const reconnectCapability = hasWorkspaceWrite && hasGmailCompose
    ? 'reconnect'
    : hasWorkspaceWrite ? 'workspace' : hasGmailCompose ? 'gmail' : null
  const reconnectHref = `/api/auth/google${reconnectCapability ? `?capability=${reconnectCapability}` : ''}`
  const legacyScopes = (scopes ?? []).filter((scope) =>
    scope === 'https://www.googleapis.com/auth/gmail.send'
    || scope === 'https://www.googleapis.com/auth/gmail.modify')
  const [operations, setOperations] = useState<{
    items: Array<{
      id: string
      capability: string
      state: string
      created: number
      resource_id: string | null
      error_code: string | null
      reconcilable: boolean
    }>
    summary: Record<string, number>
    attention_count: number
    pending_previews: number
  } | null>(null)
  const [operationError, setOperationError] = useState('')
  const [reconciling, setReconciling] = useState('')
  const [mascotEnabled, setMascotEnabled] = useState(() => {
    return localStorage.getItem('driveagent_mascot_enabled') !== 'false'
  })
  const [credentials, setCredentials] = useState<GeminiCredential[]>([])
  const [credentialLoading, setCredentialLoading] = useState(true)
  const [credentialBusy, setCredentialBusy] = useState('')
  const [credentialMessage, setCredentialMessage] = useState<{ intent: 'success' | 'error'; text: string } | null>(null)
  const [credentialName, setCredentialName] = useState('')
  const [credentialProject, setCredentialProject] = useState('')
  const [credentialSecret, setCredentialSecret] = useState('')
  const [capacity, setCapacity] = useState<ProviderCapacity | null>(null)
  const activeCredential = credentials.find((item) => item.id === capacity?.active_credential_id)

  function handleMascotToggle(checked: boolean) {
    setMascotEnabled(checked)
    localStorage.setItem('driveagent_mascot_enabled', String(checked))
    window.dispatchEvent(new StorageEvent('storage', { key: 'driveagent_mascot_enabled', newValue: String(checked) }))
  }

  async function loadOperations() {
    try {
      setOperations(await api('/api/operations/status'))
      setOperationError('')
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : 'Không đọc được trạng thái thao tác.')
    }
  }

  useEffect(() => { void loadOperations() }, [])

  async function loadCredentials() {
    setCredentialLoading(true)
    try {
      const [items, current] = await Promise.all([
        api<GeminiCredential[]>('/api/settings/providers/gemini/credentials'),
        api<ProviderCapacity>('/api/settings/providers/gemini/status'),
      ])
      setCredentials(items)
      setCapacity(current)
    } catch (error) {
      setCredentialMessage({ intent: 'error', text: error instanceof Error ? error.message : 'Không đọc được danh sách Gemini key.' })
    } finally {
      setCredentialLoading(false)
    }
  }

  async function updateFailover(item: GeminiCredential, enabled: boolean) {
    setCredentialBusy(`failover:${item.id}`)
    setCredentialMessage(null)
    try {
      await api(`/api/settings/providers/gemini/credentials/${item.id}/failover`, {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
      })
      setCredentialMessage({
        intent: 'success',
        text: enabled
          ? 'Key được phép tham gia dự phòng trước request khi key chính bị chặn local.'
          : 'Đã tắt dự phòng cho key này.',
      })
      await loadCredentials()
    } catch (error) {
      setCredentialMessage({ intent: 'error', text: error instanceof Error ? error.message : 'Không cập nhật được dự phòng.' })
    } finally {
      setCredentialBusy('')
    }
  }

  useEffect(() => { void loadCredentials() }, [])

  async function addCredential(event: React.FormEvent) {
    event.preventDefault()
    setCredentialBusy('create')
    setCredentialMessage(null)
    try {
      await api('/api/settings/providers/gemini/credentials', {
        method: 'POST',
        body: JSON.stringify({
          display_name: credentialName,
          project_alias: credentialProject,
          api_key: credentialSecret,
        }),
      })
      setCredentialName('')
      setCredentialProject('')
      setCredentialSecret('')
      setCredentialMessage({ intent: 'success', text: 'Key đã được kiểm tra và lưu mã hóa cho tài khoản của bạn.' })
      await loadCredentials()
    } catch (error) {
      setCredentialMessage({ intent: 'error', text: error instanceof Error ? error.message : 'Không lưu được key.' })
    } finally {
      setCredentialBusy('')
    }
  }

  async function credentialAction(id: string, action: 'validate' | 'activate' | 'delete') {
    setCredentialBusy(`${action}:${id}`)
    setCredentialMessage(null)
    if (action === 'activate') {
      setCapacity(null)
      window.dispatchEvent(new Event('veridra-credential-changing'))
    }
    try {
      await api(`/api/settings/providers/gemini/credentials/${id}${action === 'delete' ? '' : `/${action}`}`, {
        method: action === 'delete' ? 'DELETE' : 'POST',
      })
      setCredentialMessage({
        intent: 'success',
        text: action === 'activate' ? 'Đã chuyển key nóng; không cần khởi động lại.' : action === 'delete' ? 'Đã xóa key khỏi thiết bị.' : 'Key vẫn kết nối được với Gemini.',
      })
      await loadCredentials()
      if (action === 'activate') window.dispatchEvent(new Event('veridra-credential-changed'))
    } catch (error) {
      setCredentialMessage({ intent: 'error', text: error instanceof Error ? error.message : 'Thao tác key không thành công.' })
      if (action === 'activate') {
        await loadCredentials()
        window.dispatchEvent(new Event('veridra-credential-changed'))
      }
    } finally {
      setCredentialBusy('')
    }
  }

  async function reconcile(operationId: string) {
    setReconciling(operationId)
    setOperationError('')
    try {
      await api(`/api/operations/${operationId}/reconcile`, { method: 'POST' })
      await loadOperations()
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : 'Không đối soát được thao tác.')
    } finally {
      setReconciling('')
    }
  }

  async function acknowledge(operationId: string) {
    setReconciling(operationId)
    setOperationError('')
    try {
      await api(`/api/operations/${operationId}/acknowledge`, { method: 'POST' })
      await loadOperations()
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : 'Không đóng được cảnh báo.')
    } finally {
      setReconciling('')
    }
  }

  async function logout() {
    try {
      await api('/api/auth/logout', { method: 'POST' })
      window.location.reload()
    } catch (caught) {
      setOperationError(caught instanceof Error ? caught.message : 'Chưa đăng xuất được. Hãy thử lại.')
    }
  }

  function scrollToSetting(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return <section className="stack-page settings-page">
    <div className="page-heading"><div><h2>Cài đặt Veridra</h2><p>Quản lý theo từng nhóm: hệ thống, AI, kết nối Google, trải nghiệm và bảo mật.</p></div></div>
    <nav className="settings-index" aria-label="Nhóm cài đặt">
      <button type="button" onClick={() => scrollToSetting('settings-system')}>Hệ thống</button>
      <button type="button" onClick={() => scrollToSetting('settings-ai')}>AI & hạn mức</button>
      <button type="button" onClick={() => scrollToSetting('settings-google')}>Google Workspace</button>
      <button type="button" onClick={() => scrollToSetting('settings-experience')}>Trải nghiệm</button>
      <button type="button" onClick={() => scrollToSetting('settings-security')}>Bảo mật</button>
    </nav>

    <section id="settings-system" className="settings-group" aria-labelledby="settings-system-title">
      <header className="settings-group__heading">
        <div><span>Hệ thống</span><h3 id="settings-system-title">Trạng thái dịch vụ</h3></div>
        <p>Health kiểm tra database và trạng thái hệ thống. Google và Gemini được xác nhận sau thao tác thật.</p>
      </header>
      <div className="status-board">
        <StatusLine label={health?.vector_store === 'postgres-pgvector' ? 'PostgreSQL' : 'Database'} ready={Boolean(health?.database)} detail="Lưu tài khoản, phiên làm việc, audit và dữ liệu RAG trên hệ thống đang chạy." />
        <StatusLine label="Vector store" ready={Boolean(health?.vector_store)} detail={health?.vector_store ?? 'Chưa khởi tạo'} />
        <StatusLine
          label="Gemini"
          ready={status.gemini_configured}
          detail={health
            ? `${health.gemini_chat_model} · dự phòng ${health.gemini_fallback_model} · ${health.gemini_embedding_model} (${health.embedding_dimensions}D) · chưa probe kết nối từ health`
            : 'Đang đọc cấu hình model…'}
        />
        <StatusLine
          label="Google OAuth"
          ready={status.oauth_configured}
          detail={workspaceReadReady
            ? 'OAuth client đã cấu hình; user đã cấp phạm vi đọc Drive và Gmail.'
            : driveReadReady
              ? 'OAuth client đã cấu hình; user chưa cấp phạm vi đọc Gmail.'
              : 'OAuth client đã cấu hình; user chưa cấp đủ phạm vi đọc Drive.'}
        />
      </div>
    </section>

    <section className="operation-ledger settings-group" aria-labelledby="operation-ledger-title">
      <header>
        <div>
          <h3 id="operation-ledger-title">Thao tác Google cần theo dõi</h3>
          <p>Chỉ hiển thị trạng thái kỹ thuật của tài khoản hiện tại; nội dung tài liệu, email và giá trị bảng không xuất hiện ở đây.</p>
        </div>
        <Button appearance="subtle" onClick={() => void loadOperations()}>Làm mới</Button>
      </header>
      {operationError && <MessageBar intent="error"><MessageBarBody>{operationError}</MessageBarBody></MessageBar>}
      {!operations ? <p>Đang đọc sổ thao tác…</p> : <>
        <div className="operation-ledger__summary">
          <span><strong>{operations.attention_count}</strong> cần đối soát</span>
          <span><strong>{operations.pending_previews}</strong> bản xem trước chưa chạy</span>
          <span><strong>{operations.summary.succeeded ?? 0}</strong> đã xác nhận thành công</span>
        </div>
        {operations.attention_count === 0 ? <p className="operation-ledger__empty">Không có thao tác đang chạy hoặc chưa xác định kết quả.</p> :
          <div className="operation-ledger__items">{operations.items
            .filter((item) => item.state === 'running' || item.state === 'uncertain')
            .map((item) => <article key={item.id}>
              <div><strong>{operationLabels[item.capability] ?? item.capability.replaceAll('_', ' ')}</strong><small>Đang cần xử lý</small></div>
              <Badge appearance="tint" color="warning">{item.state === 'uncertain' ? 'Chưa xác định' : 'Đang chạy'}</Badge>
              <span className="operation-ledger__reason">{operationErrorLabels[item.error_code ?? ''] ?? 'Đang chờ kết quả cuối'}</span>
              <div className="operation-ledger__actions">
                {item.reconcilable ? (
                  <Button size="small" disabled={Boolean(reconciling)} onClick={() => void reconcile(item.id)}>
                    {reconciling === item.id
                      ? 'Đang đối soát…'
                      : item.capability.startsWith('docs')
                      ? 'Đối soát Docs'
                      : item.capability.startsWith('gmail')
                      ? 'Đối soát Gmail'
                      : 'Đối soát bằng read-back'}
                  </Button>
                ) : (
                  <small>Không tự gửi lại. Hãy kiểm tra file/email bên Google trước.</small>
                )}
                {item.state === 'uncertain' && <Button size="small" appearance="subtle" disabled={Boolean(reconciling)} onClick={() => void acknowledge(item.id)}>
                  Đã kiểm tra, đóng cảnh báo
                </Button>}
              </div>
            </article>)}</div>}
      </>}
    </section>

    <section id="settings-ai" className="settings-section settings-group gemini-credentials" aria-labelledby="gemini-credentials-title">
      <header className="gemini-credentials__header">
        <div>
          <h3 id="gemini-credentials-title">Gemini API & hạn mức</h3>
          <p>Lưu tối đa 5 key riêng cho tài khoản. Key được mã hóa trên backend và không bao giờ được trả lại trình duyệt sau khi lưu.</p>
        </div>
        <Badge appearance="tint" color="informative">Free-tier · BYOK cô lập theo người dùng</Badge>
      </header>
      {capacity?.local_budget ? (
        <div className="provider-capacity-summary" aria-label="Năng lực AI hiện tại">
          <div><span>Còn theo ngân sách local của key hiệu lực</span><strong>{capacity.local_budget.daily_remaining}/{capacity.local_budget.daily_limit} lượt</strong></div>
          <div><span>Trong 60 giây</span><strong>{capacity.local_budget.minute_used}/{capacity.local_budget.minute_limit} lượt</strong></div>
          <div><span>Model dự phòng</span><strong>{capacity.fallback_model}</strong></div>
          <div><span>Key bạn đã chọn</span><strong>{activeCredential?.display_name || (capacity.active_credential_id ? 'Đang đồng bộ' : capacity.credential_source)}</strong></div>
          <div><span>Project/key hiệu lực</span><strong>{capacity.display_name || capacity.credential_source}{capacity.failover_active ? ' · dự phòng' : ''}</strong></div>
        </div>
      ) : null}
      {credentialMessage && <MessageBar intent={credentialMessage.intent}><MessageBarBody>{credentialMessage.text}</MessageBarBody></MessageBar>}
      {credentialLoading ? <Spinner label="Đang đọc kho key mã hóa…" /> : credentials.length ? (
        <div className="gemini-credential-list">
          {credentials.map((item) => <article key={item.id} className={item.is_active ? 'gemini-credential-card is-active' : 'gemini-credential-card'}>
            <div>
              <div className="gemini-credential-card__title">
                <strong>{item.display_name}</strong>
                {item.is_active && <Badge appearance="filled" color="success">Đang dùng</Badge>}
              </div>
              <p>{item.project_alias || 'Chưa đặt tên project'} · fingerprint <code>{item.fingerprint}</code></p>
              <small>
                Trạng thái: {item.status === 'ready' ? 'Sẵn sàng' : item.status}
                {' · '}{item.daily_flash_used} lượt model hôm nay
                {item.circuit_open ? ` · tạm nghỉ ${item.retry_after_seconds}s` : ' · circuit sẵn sàng'}
              </small>
            </div>
            <div className="gemini-credential-card__actions">
              <Switch
                checked={item.failover_enabled}
                disabled={Boolean(credentialBusy)}
                onChange={(_, data) => void updateFailover(item, data.checked)}
                label="Dự phòng"
                aria-label={`Cho phép ${item.display_name} tham gia dự phòng`}
              />
              <Button size="small" appearance="subtle" disabled={Boolean(credentialBusy)} onClick={() => void credentialAction(item.id, 'validate')}>
                {credentialBusy === `validate:${item.id}` ? 'Đang kiểm tra…' : 'Kiểm tra'}
              </Button>
              {!item.is_active && <Button size="small" appearance="primary" disabled={Boolean(credentialBusy)} onClick={() => void credentialAction(item.id, 'activate')}>
                {credentialBusy === `activate:${item.id}` ? 'Đang chuyển…' : 'Đặt làm key hiện tại'}
              </Button>}
              {!item.is_active && <Button size="small" appearance="subtle" disabled={Boolean(credentialBusy)} onClick={() => void credentialAction(item.id, 'delete')}>Xóa</Button>}
            </div>
          </article>)}
        </div>
      ) : <p className="operation-ledger__empty">Chưa có key riêng trong kho mã hóa. Thêm Gemini API key của bạn để sử dụng AI.</p>}
      <form className="gemini-credential-form" onSubmit={addCredential} autoComplete="off">
        <Field label="Tên dễ nhớ" required><Input value={credentialName} maxLength={80} onChange={(_, data) => setCredentialName(data.value)} placeholder="Ví dụ: Gemini chính" /></Field>
        <Field label="Tên project"><Input value={credentialProject} maxLength={120} onChange={(_, data) => setCredentialProject(data.value)} placeholder="Chỉ là bí danh hiển thị" /></Field>
        <Field label="API key" required hint="Key được gửi tới backend của Veridra để kiểm tra và lưu mã hóa cho tài khoản của bạn.">
          <Input type="password" value={credentialSecret} maxLength={512} onChange={(_, data) => setCredentialSecret(data.value)} placeholder="Dán Gemini API key" />
        </Field>
        <Button type="submit" appearance="primary" disabled={credentialBusy === 'create' || !credentialName.trim() || credentialSecret.trim().length < 20}>
          {credentialBusy === 'create' ? 'Đang kiểm tra và lưu…' : 'Kiểm tra & lưu key'}
        </Button>
      </form>
      <MessageBar intent="info"><MessageBarBody>{capacity?.provider_balance_note || 'Đây là bộ đếm bảo vệ của Veridra, không phải hạn mức còn lại được Google xác nhận.'} Chỉ các khóa bạn bật “Dự phòng” mới được chọn khi khóa chính tạm bị chặn do lỗi hoặc đã hết ngân sách bảo vệ.</MessageBarBody></MessageBar>
    </section>

    <section id="settings-experience" className="settings-section settings-group" aria-labelledby="assistant-prefs-title">
      <h3 id="assistant-prefs-title">Trợ lý ảo Linh vật & Tương tác</h3>
      <p>Bật hoặc tắt chú cáo Veridra Fox hỗ trợ theo dõi chuột và tạo sự sinh động khi làm việc.</p>
      <div className="status-line">
        <span className="status-icon status-icon--ok">🦊</span>
        <div>
          <strong>Chú cáo Veridra Fox</strong>
          <p>Linh vật tương tác ở góc màn hình, dõi theo con trỏ chuột và phản hồi trạng thái Agent.</p>
        </div>
        <Switch
          checked={mascotEnabled}
          onChange={(_, data) => handleMascotToggle(data.checked)}
          label={mascotEnabled ? 'Đang bật' : 'Đã tắt'}
        />
      </div>
    </section>

    <div id="settings-google" className="google-auth-upgrade-card settings-group">
      <div>
        <h3>Cấp quyền Gmail & Google Drive</h3>
        <p>
          {workspaceReadReady
            ? 'Tài khoản đã cấp phạm vi đọc cần thiết cho Drive và Gmail. Từng lần gọi vẫn cần được Google xác nhận thành công.'
            : driveReadReady
              ? 'Tài khoản có phạm vi đọc Drive nhưng chưa có đủ quyền đọc hộp thư Gmail. Kết nối lại để cấp quyền cần thiết.'
              : 'Tài khoản chưa có đủ phạm vi đọc Drive. Kết nối lại Google để cấp quyền cần thiết.'}
        </p>
      </div>
      <Button
        as="a"
        href={reconnectHref}
        appearance={workspaceReadReady ? 'outline' : 'primary'}
      >
        {workspaceReadReady ? 'Xem lại quyền Google' : gmailReadReady ? 'Cấp quyền Drive' : 'Cấp quyền Gmail & Drive'}
      </Button>
    </div>

    <section className="oauth-scope-ledger settings-group" aria-labelledby="oauth-scope-title">
      <h3 id="oauth-scope-title">Quyền Google tài khoản đã cấp</h3>
      <p>Danh sách lấy từ phiên OAuth hiện tại. Veridra không suy diễn quyền từ trạng thái “đã kết nối”.</p>
      <ul>{(scopes ?? []).map((scope) => <li key={scope}>
        <strong>{scopeLabels[scope] ?? 'Quyền Google khác'}</strong>
        <code>{scope}</code>
      </li>)}</ul>
      {!scopes?.length && <p>Chưa có scope nào được lưu. Hãy kết nối lại Google.</p>}
      {legacyScopes.length > 0 && <MessageBar intent="warning"><MessageBarBody>
        <p><strong>Vì sao cần làm lại:</strong> Google giữ các quyền cũ khi ứng dụng xin thêm scope; “Xem lại quyền” không thu hẹp token.</p>
        <p><strong>Cách xử lý:</strong></p>
        <ol className="oauth-reset-steps">
          <li>Mở Google Account → Bảo mật → Kết nối với ứng dụng bên thứ ba.</li>
          <li>Xóa quyền của Veridra.</li>
          <li>Kết nối lại và chỉ cấp Drive đọc, Gmail đọc và Gmail compose.</li>
        </ol>
      </MessageBarBody></MessageBar>}
    </section>

    <section id="settings-security" className="settings-security settings-group" aria-labelledby="settings-security-title">
      <h3 id="settings-security-title">Bảo mật và phiên làm việc</h3>
      <MessageBar intent="info"><MessageBarBody>Veridra không lưu API key trên trình duyệt. OAuth token được mã hóa bằng APP_SECRET trước khi ghi database.</MessageBarBody></MessageBar>
      <div className="danger-zone"><div><h3>Rời phiên hiện tại</h3><p>Đăng xuất chỉ xóa cookie trên trình duyệt, không xóa dữ liệu hoặc quyền Google.</p></div><Button icon={<ArrowExit24Regular />} onClick={logout}>Đăng xuất</Button></div>
    </section>
  </section>
}
