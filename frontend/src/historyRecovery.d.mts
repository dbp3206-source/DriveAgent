export function readHistoryWithRecovery<T>(read: () => Promise<T>, signal: AbortSignal, sleep?: (ms: number) => Promise<void>): Promise<T>
