import { Badge, Button, MessageBar, MessageBarBody } from '@fluentui/react-components'
import { ArrowExit24Regular, CheckmarkCircle24Regular, DismissCircle24Regular } from '@fluentui/react-icons'
import type { AuthStatus, Health } from '../types'

function StatusLine({ label, ready, detail }: { label: string; ready: boolean; detail: string }) {
  return <div className="status-line">
    <span className={ready ? 'status-icon status-icon--ok' : 'status-icon status-icon--error'}>{ready ? <CheckmarkCircle24Regular /> : <DismissCircle24Regular />}</span>
    <div><strong>{label}</strong><p>{detail}</p></div>
    <Badge appearance="tint" color={ready ? 'success' : 'danger'}>{ready ? 'Sẵn sàng' : 'Cần xử lý'}</Badge>
  </div>
}

export function SettingsPage({ status, health }: { status: AuthStatus; health: Health | null }) {
  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    window.location.reload()
  }

  return <section className="stack-page settings-page">
    <div className="page-heading"><div><h2>Trạng thái hệ thống</h2><p>Kiểm tra nhanh mọi dependency cần cho một phiên agent.</p></div></div>
    <div className="status-board">
      <StatusLine label="SQLite" ready={Boolean(health?.database)} detail="Lưu user, session, audit và bản sao RAG trên máy." />
      <StatusLine label="Vector store" ready={Boolean(health?.vector_store)} detail={health?.vector_store ?? 'Chưa khởi tạo'} />
      <StatusLine
        label="Gemini"
        ready={status.gemini_configured}
        detail={health
          ? `${health.gemini_chat_model} · dự phòng ${health.gemini_fallback_model} · ${health.gemini_embedding_model} (${health.embedding_dimensions}D)`
          : 'Đang đọc cấu hình model…'}
      />
      <StatusLine label="Google OAuth" ready={status.oauth_configured} detail="Quyền Drive read-only, tách riêng cho từng user." />
    </div>
    <MessageBar intent="info"><MessageBarBody>DriveAgent không lưu API key trên trình duyệt. OAuth token được mã hóa bằng APP_SECRET trước khi ghi SQLite.</MessageBarBody></MessageBar>
    <div className="danger-zone"><div><h3>Rời phiên hiện tại</h3><p>Đăng xuất chỉ xóa cookie trên trình duyệt, không xóa dữ liệu hoặc quyền Google.</p></div><Button icon={<ArrowExit24Regular />} onClick={logout}>Đăng xuất</Button></div>
  </section>
}
