export type ChatPhase = 'running' | 'completed' | 'incomplete' | 'failed' | 'cancelled' | 'waiting'
export interface ChatActivityEvent { ownerId: string; taskId: string; sessionId: string | null; phase: ChatPhase }
export interface ChatActivity extends ChatActivityEvent { unread: boolean }
export const CHAT_OPEN_EVENT: string
export const CHAT_OPEN_KEY: string
export function validChatActivity(value: unknown, ownerId: string): boolean
export function reduceChatActivity(current: ChatActivity | null, event: ChatActivityEvent, ownerId: string, viewingConversation: boolean): ChatActivity | null
export function readChatActivity(storage: Pick<Storage, 'getItem'>, ownerId?: string): ChatActivity | null
export function saveChatActivity(storage: Pick<Storage, 'setItem'>, value: ChatActivity | null): void
export function chatActivityCopy(phase?: ChatPhase): {title: string; text: string; action: string}
