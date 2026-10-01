/** Poll only persisted task state; disconnecting never cancels server work. */
export async function waitForChatTask(read, signal, onState = () => {}, options = {}) {
  const deadline = Date.now() + (options.timeoutMs ?? 480000)
  const interval = options.intervalMs ?? 1000
  const sleep = options.sleep ?? ((ms) => new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException('Stopped polling', 'AbortError')) }
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve() }, ms)
    signal?.addEventListener('abort', abort, {once: true})
    if (signal?.aborted) abort()
  }))
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException('Stopped polling', 'AbortError')
    let state
    try {
      state = await read()
    } catch (error) {
      if (signal?.aborted || error?.name === 'AbortError') throw error
      // A restart/network outage is not a failed persisted task. Retry only
      // transient transport/server errors; auth/permission failures stop polling.
      if (error?.status !== 0 && !(error?.status >= 500)) throw error
      await sleep(interval)
      continue
    }
    onState(state)
    if (state.status === 'completed') {
      if (!state.result) throw new Error('Yêu cầu hoàn tất nhưng chưa tải được kết quả.')
      return state.result
    }
    if (state.status === 'failed' || state.status === 'cancelled') {
      throw new Error(state.error || 'Yêu cầu đã dừng; nội dung vẫn được lưu trong lịch sử.')
    }
    await sleep(interval)
  }
  throw new Error('Chưa nhận được kết quả. Yêu cầu vẫn được lưu; mở lại cuộc trò chuyện để kiểm tra.')
}
