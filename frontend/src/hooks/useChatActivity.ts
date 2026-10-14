import { useCallback, useEffect, useRef, useState } from 'react'
import { readChatActivity, reduceChatActivity, saveChatActivity, type ChatActivity, type ChatActivityEvent } from '../chatActivity.mjs'

export function useChatActivity(ownerId: string | undefined, page: string) {
  const [stored, setStored] = useState<ChatActivity | null>(null)
  const pageRef = useRef(page)
  useEffect(() => { pageRef.current = page }, [page])
  useEffect(() => { setStored(readChatActivity(sessionStorage, ownerId)) }, [ownerId])
  const activity = stored?.ownerId === ownerId ? stored : null
  useEffect(() => { saveChatActivity(sessionStorage, activity) }, [activity])
  const update = useCallback((event: ChatActivityEvent) => {
    if (!ownerId) return
    let selected: string | null = null
    try { selected = sessionStorage.getItem('drive_agent_session_id') } catch { /* Optional. */ }
    const viewing = pageRef.current === 'chat' && document.visibilityState === 'visible'
      && (event.sessionId === null || selected === event.sessionId)
    setStored(current => reduceChatActivity(current?.ownerId === ownerId ? current : null, event, ownerId, viewing))
  }, [ownerId])
  const acknowledge = useCallback(() => setStored(current =>
    current && current.ownerId === ownerId && current.unread ? {...current, unread: false} : current), [ownerId])
  useEffect(() => {
    const acknowledgeVisible = () => {
      if (page !== 'chat' || document.visibilityState !== 'visible') return
      let selected: string | null = null
      try { selected = sessionStorage.getItem('drive_agent_session_id') } catch { return }
      setStored(current => current && current.ownerId === ownerId && current.unread
        && current.sessionId === selected ? {...current, unread: false} : current)
    }
    acknowledgeVisible()
    document.addEventListener('visibilitychange', acknowledgeVisible)
    return () => document.removeEventListener('visibilitychange', acknowledgeVisible)
  }, [page, ownerId])
  return {activity, update, acknowledge}
}
