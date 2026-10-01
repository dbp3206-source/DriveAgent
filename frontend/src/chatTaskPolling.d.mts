export function waitForChatTask<T>(
  read: () => Promise<{status: string; result: T | null; error?: string | null}>,
  signal?: AbortSignal,
  onState?: (state: {status: string; result: T | null; error?: string | null}) => void,
  options?: {timeoutMs?: number; intervalMs?: number; sleep?: (ms: number) => Promise<void>},
): Promise<T>
