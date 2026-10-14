import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Mascot } from 'page-mascot'
import {
  ArrowSwap16Regular,
  ChevronDown16Regular,
  Dismiss16Regular,
  Sparkle16Regular,
  Chat16Regular,
} from '@fluentui/react-icons'
import { api } from '../api'
import type { ProviderCapacity } from '../types'
import { chatActivityCopy, type ChatActivity } from '../chatActivity.mjs'
import type { PageKey } from './AppShell'

interface MascotAssistantProps {
  activity?: ChatActivity | null
  currentPage?: string
  onNavigateToChat?: () => void
  onNavigateToPage?: (page: PageKey) => void
}

type MascotChoice = {
  id: string
  label: string
  description: string
  directions: string
  reactions: string
}

const MASCOT_CHOICES: MascotChoice[] = [
  { id: 'fox', label: 'Cáo', description: 'Nhanh nhẹn, thân thiện', directions: '/mascots/page-mascot/fox-directions.png', reactions: '/mascots/page-mascot/fox-reactions.png' },
  { id: 'otter', label: 'Rái cá', description: 'Điềm tĩnh, tò mò', directions: '/mascots/page-mascot/otter-directions.png', reactions: '/mascots/page-mascot/otter-reactions.png' },
  { id: 'owl', label: 'Cú', description: 'Tập trung, quan sát kỹ', directions: '/mascots/page-mascot/owl-directions.png', reactions: '/mascots/page-mascot/owl-reactions.png' },
  { id: 'robot', label: 'Rô-bốt', description: 'Gọn gàng, chính xác', directions: '/mascots/page-mascot/robot-directions.png', reactions: '/mascots/page-mascot/robot-reactions.png' },
  { id: 'panda', label: 'Gấu trúc', description: 'Nhẹ nhàng, bền bỉ', directions: '/mascots/page-mascot/panda-directions.png', reactions: '/mascots/page-mascot/panda-reactions.png' },
  { id: 'cat', label: 'Mèo', description: 'Linh hoạt, nhanh nhạy', directions: '/mascots/page-mascot/cat-directions.png', reactions: '/mascots/page-mascot/cat-reactions.png' },
]

const PAGE_TIPS: Record<string, string> = {
  home: 'Nêu việc cần làm hoặc chọn một gợi ý. Bạn xem lại câu hỏi trước khi gửi.',
  chat: 'Chọn nguồn cần dùng, rồi nêu việc bạn muốn hoàn thành. Tạo tài liệu bên ngoài cần bạn duyệt.',
  gmail: 'Chọn thư cần xem. Nếu cần phản hồi, có thể chuẩn bị bản nháp trước; không tự gửi thư.',
  drive: 'Dùng Gần đây, Đã gắn sao và loại tệp để tìm nhanh; không cần nhớ tên tài liệu.',
  local: 'Nhập tài liệu rồi chọn Chat với tệp này. Khi hỏi, đoạn liên quan được gửi tới Gemini.',
  skills: 'Lưu cách làm thành mẫu, rồi thay dữ kiện khi dùng lại cho công việc mới.',
  artifacts: 'Sửa nội dung, kiểm bản đọc rồi lưu. Có thể xuất bản đã lưu sang tệp.',
  memory: 'Bạn có thể xem, sửa hoặc cất điều đã lưu. Cất ghi chú không phải xóa vĩnh viễn.',
  harness: 'Xem quy trình và vai trò của từng trợ lý. Chỉ coi kết quả đã kiểm là bằng chứng.',
  settings: 'Xem kết nối và hạn mức ứng dụng. Số lượt tại đây không phải số dư Google.',
  audit: 'Xem công cụ đã chạy và trạng thái thực tế của từng yêu cầu.',
  access: 'Chỉ cấp những quyền cần cho công việc. Linh vật không tự thay quyền.',
}

export function MascotAssistant({
  activity = null,
  currentPage = 'chat',
  onNavigateToChat,
  onNavigateToPage,
}: MascotAssistantProps) {
  const [enabled, setEnabled] = useState(() => {
    const saved = localStorage.getItem('driveagent_mascot_enabled')
    return saved !== null ? saved === 'true' : true
  })
  const [minimized, setMinimized] = useState(() => {
    return localStorage.getItem('driveagent_mascot_minimized') === 'true'
      || window.matchMedia('(max-width: 700px)').matches
  })
  const [speech, setSpeech] = useState<string | null>(null)
  const [selectedMascotId, setSelectedMascotId] = useState(() => localStorage.getItem('driveagent_mascot_id') || 'fox')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [hiddenNotice, setHiddenNotice] = useState('')
  const [capacity, setCapacity] = useState<ProviderCapacity | null>(null)
  const speechTimer = useRef<number | null>(null)
  const mascot = MASCOT_CHOICES.find((choice) => choice.id === selectedMascotId) ?? MASCOT_CHOICES[0]!
  const status = activity?.phase ?? 'idle'
  const noticeKey = activity ? `${activity.taskId}:${activity.phase}` : ''
  const showNotice = Boolean(activity?.unread && hiddenNotice !== noticeKey)
  const copy = chatActivityCopy(activity?.phase)
  const showSpeech = useCallback((text: string, duration = 6000) => {
    if (speechTimer.current) window.clearTimeout(speechTimer.current)
    setSpeech(text)
    speechTimer.current = window.setTimeout(() => setSpeech(null), duration)
  }, [])

  useEffect(() => {
    let active = true
    let requestVersion = 0
    const refresh = () => {
      const version = ++requestVersion
      void api<ProviderCapacity>('/api/settings/providers/gemini/status')
        .then((value) => { if (active && version === requestVersion) setCapacity(value) })
        .catch(() => { if (active && version === requestVersion) setCapacity(null) })
    }
    const changing = () => { requestVersion++; setCapacity(null) }
    refresh()
    const timer = window.setInterval(refresh, 60_000)
    window.addEventListener('veridra-credential-changing', changing)
    window.addEventListener('veridra-credential-changed', refresh)
    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener('veridra-credential-changing', changing)
      window.removeEventListener('veridra-credential-changed', refresh)
    }
  }, [status])

  // Listen for storage events (e.g. toggled from Settings page)
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === 'driveagent_mascot_enabled') {
        setEnabled(e.newValue !== 'false')
      }
      if (e.key === 'driveagent_mascot_id' && e.newValue) {
        setSelectedMascotId(e.newValue)
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // Listen for global mascot-notify events from any component
  useEffect(() => {
    function handleNotify(e: Event) {
      const custom = e as CustomEvent<{ text: string }>
      if (custom.detail?.text) {
        showSpeech(custom.detail.text, 5000)
      }
    }
    window.addEventListener('mascot-notify', handleNotify)
    return () => window.removeEventListener('mascot-notify', handleNotify)
  }, [showSpeech])

  useEffect(() => () => {
    if (speechTimer.current) window.clearTimeout(speechTimer.current)
  }, [])

  // Keep analytical pages readable: the expanded companion is useful in chat,
  // but it can cover charts and execution traces on narrower screens. Users
  // can still restore it from the small fox button whenever they need it.
  useEffect(() => {
    if (currentPage === 'chat') return
    setMinimized((prev) => {
      if (prev) return prev
      localStorage.setItem('driveagent_mascot_minimized', 'true')
      return true
    })
  }, [currentPage])

  function handlePoke() {
    if (activity?.unread) { setHiddenNotice(''); return }
    showSpeech(status === 'running' ? copy.text : PAGE_TIPS[currentPage] || 'Mình có thể giúp chọn nguồn và mở công việc cần làm.')
  }

  function selectMascot(id: string) {
    setSelectedMascotId(id)
    localStorage.setItem('driveagent_mascot_id', id)
    setPickerOpen(false)
    const next = MASCOT_CHOICES.find((choice) => choice.id === id)
    if (next) showSpeech(`Đã đổi sang trợ lý ${next.label}.`, 3000)
  }

  function goToChat(e?: React.MouseEvent) {
    if (e) e.stopPropagation()
    setSpeech(null)
    if (onNavigateToChat) {
      onNavigateToChat()
    } else {
      window.location.hash = '#/chat'
    }
  }

  function toggleMinimize() {
    setMinimized((prev) => {
      const next = !prev
      localStorage.setItem('driveagent_mascot_minimized', String(next))
      return next
    })
  }

  if (!enabled) return null

  return (
    <aside
      className={`mascot-companion ${minimized ? 'mascot-companion--minimized' : ''}`}
      aria-label="Trợ lý linh vật Veridra"
      data-task-phase={status}
    >
      {showNotice ? (
        <section className={`mascot-notice mascot-notice--${status}`} role="status" aria-live="polite" aria-atomic="true" aria-label="Thông báo từ trợ lý">
          <div className="mascot-speech__header">
            <span className="mascot-speech__author">Trợ lý {mascot.label}</span>
            <button type="button" className="mascot-speech__close" aria-label="Để thông báo lại sau" onClick={() => setHiddenNotice(noticeKey)}><Dismiss16Regular /></button>
          </div>
          <strong>{copy.title}</strong>
          <p>{copy.text}</p>
          <button type="button" className="mascot-speech__action" onClick={goToChat}><Chat16Regular />{copy.action}</button>
        </section>
      ) : speech && !minimized ? (
        <div className="mascot-speech" role="status" aria-live="polite">
          <div className="mascot-speech__header">
            <span className="mascot-speech__author">Trợ lý {mascot.label}</span>
            <button
              type="button"
              className="mascot-speech__close"
              onClick={() => setSpeech(null)}
              aria-label="Đóng lời thoại"
            >
              <Dismiss16Regular />
            </button>
          </div>
          <p className="mascot-speech__text">{speech}</p>
          <div className="mascot-shortcuts">
            <button type="button" className="mascot-speech__action" onClick={goToChat}><Chat16Regular />Trò chuyện</button>
            {onNavigateToPage ? <button type="button" className="mascot-speech__action" onClick={() => {setSpeech(null); onNavigateToPage(currentPage === 'drive' || currentPage === 'local' ? 'skills' : 'drive')}}>{currentPage === 'drive' || currentPage === 'local' ? 'Mẫu công việc' : 'Chọn tài liệu'}</button> : null}
          </div>
        </div>
      ) : null}

      <div className="mascot-frame" onClick={handlePoke}>
        {minimized ? (
          <button
            type="button"
            className="mascot-restore-btn"
            onClick={(e) => {
              e.stopPropagation()
              if (activity?.unread) setHiddenNotice(hiddenNotice === noticeKey ? '' : noticeKey)
              else toggleMinimize()
            }}
            title={activity?.unread ? 'Xem thông báo chưa đọc' : status === 'running' ? 'Trợ lý đang xử lý câu hỏi' : 'Mở lại trợ lý linh vật'}
            aria-label={activity?.unread ? 'Xem thông báo chưa đọc' : 'Mở lại trợ lý linh vật'}
          >
            <span className="mascot-restore-icon" aria-hidden="true" style={{ backgroundImage: `url(${mascot.directions})` }} />
            <span className="mascot-status-pulse" aria-hidden="true" />
            {activity?.unread ? <span className="mascot-unread-badge" aria-hidden="true">{status === 'completed' ? '1' : '!'}</span> : null}
          </button>
        ) : (
          <>
            <div className="mascot-controls">
              <button
                type="button"
                className="mascot-control-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  toggleMinimize()
                }}
                title="Thu nhỏ trợ lý"
                aria-label="Thu nhỏ trợ lý"
              >
                <Dismiss16Regular />
              </button>
            </div>

            <div className="mascot-sprite-wrapper" title={`Nhấn để trò chuyện cùng trợ lý ${mascot.label}`}>
              <Mascot
                directions={mascot.directions}
                reactions={mascot.reactions}
                size={84}
                label={`Veridra ${mascot.label}`}
                className="mascot-interactive-canvas"
              />
            </div>

            <button type="button" className="mascot-task-status" onClick={(event) => {
              event.stopPropagation()
              if (activity?.unread || status === 'running') goToChat()
              else handlePoke()
            }}>
              <span className="mascot-task-dot" aria-hidden="true" />
              {activity?.unread ? copy.title : status === 'running' ? 'Đang xử lý · bạn cứ làm việc khác' : 'Cần mình hỗ trợ?'}
            </button>

            <div className="mascot-badge-row">
              <div className="mascot-badge">
                <Sparkle16Regular className="mascot-badge__icon" />
                <span>Trợ lý {mascot.label}</span>
              </div>
              <button
                type="button"
                className="mascot-switch-btn"
                onClick={(e) => { e.stopPropagation(); setPickerOpen((open) => !open) }}
                aria-expanded={pickerOpen}
                aria-controls="mascot-picker"
                title="Đổi linh vật trợ lý"
              >
                <ArrowSwap16Regular />
                <span>Đổi</span>
                <ChevronDown16Regular />
              </button>
              {pickerOpen && (
                <div id="mascot-picker" className="mascot-picker" role="listbox" aria-label="Chọn linh vật trợ lý">
                  <div className="mascot-picker__heading"><strong>Chọn trợ lý</strong><small>Thay đổi chỉ áp dụng trên thiết bị này.</small></div>
                  <div className="mascot-picker__grid">
                    {MASCOT_CHOICES.map((choice) => (
                      <button
                        key={choice.id}
                        type="button"
                        role="option"
                        aria-selected={mascot.id === choice.id}
                        className={`mascot-picker__option ${mascot.id === choice.id ? 'is-selected' : ''}`}
                        onClick={(e) => { e.stopPropagation(); selectMascot(choice.id) }}
                      >
                        <span className="mascot-picker__avatar" aria-hidden="true" style={{ backgroundImage: `url(${choice.directions})` }} />
                        <span><strong>{choice.label}</strong><small>{choice.description}</small></span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <button
                type="button"
                className="mascot-chat-pill"
                onClick={goToChat}
                title="Mở màn hình Trò chuyện với Agent"
              >
                <Chat16Regular />
                <span>Trò chuyện</span>
              </button>
            </div>
            <button
              type="button"
              className="mascot-capacity"
              onClick={(event) => { event.stopPropagation(); window.location.hash = '#/settings' }}
              title={`Mở chi tiết năng lực AI của key hiệu lực ${capacity?.display_name || capacity?.credential_source || 'chưa cấu hình'}${capacity?.failover_active ? ' (dự phòng)' : ''}`}
            >
              <span>Năng lực AI</span>
              <strong>
                {capacity?.local_budget
                  ? `${capacity.local_budget.daily_remaining}/${capacity.local_budget.daily_limit} lượt ứng dụng`
                  : capacity?.configured ? 'Đang cập nhật' : 'Chưa có khóa'}
              </strong>
              {capacity?.local_budget ? (
                <span className="mascot-capacity__track" aria-hidden="true">
                  <span style={{ width: `${Math.max(0, Math.min(100, capacity.local_budget.daily_remaining / capacity.local_budget.daily_limit * 100))}%` }} />
                </span>
              ) : null}
            </button>
          </>
        )}
      </div>
    </aside>
  )
}
