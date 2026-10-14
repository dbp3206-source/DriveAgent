export class ChatTaskError extends Error { phase: 'failed' | 'cancelled' | 'waiting'; constructor(message: string, phase: 'failed' | 'cancelled' | 'waiting') }
export function waitForChatTask<T>(
  read: () => Promise<{status: string; result: T | null; error?: string | null}>,
  signal?: AbortSignal,
  onState?: (state: {status: string; result: T | null; error?: string | null}) => void,
  options?: {timeoutMs?: number; intervalMs?: number; sleep?: (ms: number) => Promise<void>},
): Promise<T>
