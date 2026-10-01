import {
  Button,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components'
import { ArrowRight24Regular, CheckmarkCircle20Regular } from '@fluentui/react-icons'
import type { AuthStatus } from '../types'
import { VeridraMark } from './VeridraMark'

export function SetupGate({ status }: { status: AuthStatus }) {
  const oauthReady = status.oauth_configured
  const sharedGeminiReady = status.gemini_configured

  async function enterDemo() {
    await fetch('/api/auth/demo', { method: 'POST', credentials: 'include' })
    window.location.reload()
  }

  return (
    <main className="setup-page">
      <section className="setup-intro" aria-labelledby="setup-title">
        <div className="brand-lockup">
          <VeridraMark />
          <span>Veridra</span>
        </div>
        <p className="section-kicker">Thiết lập lần đầu</p>
        <h1 id="setup-title">Kết nối dữ liệu. Giữ quyền kiểm soát.</h1>
        <p className="setup-lede">
          Google cho phép đọc Drive và Gmail. Veridra kiểm tra quyền ở mỗi thao tác;
          tạo tệp hoặc nháp cần bước xem trước và xác nhận của bạn.
        </p>
      </section>

      <section className="setup-checklist" aria-label="Trạng thái thiết lập">
        <div className="setup-step">
          <span className="setup-step__number">1</span>
          <div>
            <h2>Gemini API key</h2>
            <p>Sau khi đăng nhập, thêm key riêng trong Cài đặt. Key được gửi tới backend một lần để kiểm tra và lưu mã hóa; bạn không cần sửa cấu hình máy chủ.</p>
          </div>
          <strong className={sharedGeminiReady ? 'status-ok' : 'status-warn'}>
            {sharedGeminiReady ? 'Máy chủ đã có key' : 'Có thể dùng key riêng'}
          </strong>
        </div>
        <div className="setup-step">
          <span className="setup-step__number">2</span>
          <div>
            <h2>Google OAuth client</h2>
            <p>Người vận hành cấu hình OAuth client trên máy chủ; người dùng chỉ cần đăng nhập bằng Google.</p>
          </div>
          <strong className={oauthReady ? 'status-ok' : 'status-warn'}>
            {oauthReady ? 'Đã sẵn sàng' : 'Chưa cấu hình'}
          </strong>
        </div>
        <div className="setup-step">
          <span className="setup-step__number">3</span>
          <div>
            <h2>Kết nối tài khoản</h2>
            <ul className="setup-step__scope-list">
              <li><strong>Được yêu cầu:</strong> đọc Drive/Gmail, tạo tệp và lưu nháp.</li>
              <li><strong>Không yêu cầu:</strong> quyền gửi email.</li>
            </ul>
          </div>
          {oauthReady ? (
            <Button
              as="a"
              href="/api/auth/google"
              appearance="primary"
              icon={<ArrowRight24Regular />}
              iconPosition="after"
            >
              Kết nối Google
            </Button>
          ) : (
            <Button disabled>Chờ OAuth client</Button>
          )}
        </div>
        {!oauthReady ? (
          <MessageBar intent="warning">
            <MessageBarBody>
              <MessageBarTitle>OAuth chưa được máy chủ cấu hình</MessageBarTitle>
              Người vận hành cần hoàn tất kết nối Google trước khi bạn có thể đăng nhập.
            </MessageBarBody>
          </MessageBar>
        ) : (
          <div className="setup-ready">
            <CheckmarkCircle20Regular /> Đăng nhập Google để bắt đầu; thêm Gemini key riêng trong Cài đặt nếu cần.
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
