import {
  Button,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components'
import { ArrowRight24Regular, CheckmarkCircle20Regular } from '@fluentui/react-icons'
import type { AuthStatus } from '../types'

export function SetupGate({ status }: { status: AuthStatus }) {
  const oauthReady = status.oauth_configured
  const geminiReady = status.gemini_configured

  async function enterDemo() {
    await fetch('/api/auth/demo', { method: 'POST', credentials: 'include' })
    window.location.reload()
  }

  return (
    <main className="setup-page">
      <section className="setup-intro" aria-labelledby="setup-title">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">D</div>
          <span>DriveAgent</span>
        </div>
        <p className="section-kicker">Thiết lập lần đầu</p>
        <h1 id="setup-title">Kết nối Drive. Giữ quyền kiểm soát.</h1>
        <p className="setup-lede">
          Agent chỉ đọc các tệp bạn đã cấp quyền. Mỗi tool call đều được kiểm tra và ghi nhật ký.
        </p>
      </section>

      <section className="setup-checklist" aria-label="Trạng thái thiết lập">
        <div className="setup-step">
          <span className="setup-step__number">1</span>
          <div>
            <h2>Gemini API key</h2>
            <p>Thêm key vào file <code>.env</code>. Key không xuất hiện trong trình duyệt hoặc audit.</p>
          </div>
          <strong className={geminiReady ? 'status-ok' : 'status-warn'}>
            {geminiReady ? 'Đã sẵn sàng' : 'Chưa cấu hình'}
          </strong>
        </div>
        <div className="setup-step">
          <span className="setup-step__number">2</span>
          <div>
            <h2>Google OAuth client</h2>
            <p>Tải OAuth JSON từ Google Cloud và lưu thành <code>client_secret.json</code>.</p>
          </div>
          <strong className={oauthReady ? 'status-ok' : 'status-warn'}>
            {oauthReady ? 'Đã sẵn sàng' : 'Chưa cấu hình'}
          </strong>
        </div>
        <div className="setup-step">
          <span className="setup-step__number">3</span>
          <div>
            <h2>Kết nối tài khoản</h2>
            <p>Google sẽ hiển thị chính xác quyền đọc mà DriveAgent yêu cầu.</p>
          </div>
          {oauthReady ? (
            <Button
              as="a"
              href="/api/auth/google"
              appearance="primary"
              icon={<ArrowRight24Regular />}
              iconPosition="after"
            >
              Kết nối Google Drive
            </Button>
          ) : (
            <Button disabled>Chờ OAuth client</Button>
          )}
        </div>
        {!oauthReady || !geminiReady ? (
          <MessageBar intent="warning">
            <MessageBarBody>
              <MessageBarTitle>Còn một bước trên máy của bạn</MessageBarTitle>
              Mở <code>docs/SETUP_GOOGLE.md</code> và làm theo hướng dẫn khoảng 5 phút.
            </MessageBarBody>
          </MessageBar>
        ) : (
          <div className="setup-ready">
            <CheckmarkCircle20Regular /> Cấu hình nền đã hoàn tất.
          </div>
        )}
        {status.demo_login_enabled ? (
          <Button appearance="secondary" onClick={enterDemo}>
            Mở dữ liệu demo cho QA
          </Button>
        ) : null}
      </section>
    </main>
  )
}
