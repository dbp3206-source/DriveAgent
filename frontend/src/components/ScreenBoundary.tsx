import { Component, type ReactNode } from 'react'
import { Button } from '@fluentui/react-components'

/** Một tab cũ có thể tham chiếu bundle đã thay đổi sau lần build mới. */
export class ScreenBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  render() {
    if (!this.state.failed) return this.props.children
    return <section className="center-state" role="alert">
      <h2>Chưa mở được màn hình</h2>
      <p>Ứng dụng có thể vừa được cập nhật hoặc mất kết nối. Tải lại để dùng phiên bản mới; bản nháp trong ô chat vẫn được giữ trên trình duyệt này.</p>
      <Button appearance="primary" onClick={() => window.location.reload()}>Tải lại ứng dụng</Button>
    </section>
  }
}
