/** Retry only an idempotent history read, once, after a transient failure. */
export async function readHistoryWithRecovery(read, signal, sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (signal.aborted) throw new DOMException('Đã dừng tải lịch sử.', 'AbortError')
    try {
      return await read()
    } catch (error) {
      if (signal.aborted || error?.name === 'AbortError' || attempt === 1
          || (error?.status !== 0 && !(error?.status >= 500))) throw error
      await sleep(1000)
    }
  }
}
