import React, { useState, useEffect, useRef } from 'react'
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

interface MascotAssistantProps {
  status?: 'idle' | 'running' | 'completed' | 'failed'
  statusText?: string
  currentPage?: string
  onNavigateToChat?: () => void
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
  chat: 'Cần tra cứu Drive hay tóm tắt văn bản gì cứ nhắn mình nhé!',
  gmail: 'Muốn tóm tắt email quan trọng? Bấm "Chat" để hỏi ngay!',
  drive: 'Kho Google Drive đã đồng bộ. Bạn muốn tìm dữ liệu trong file nào? 📁',
  local: 'Tài liệu local đã index vào RAG. Bạn có thể hỏi nội dung ngay! 💻',
  skills: 'Dạy mình quy trình mới bằng các mẫu có sẵn phía trên nhé! ⚡',
  artifacts: 'Soạn thảo Markdown với Live Preview và lưu nhanh bằng Ctrl+S! 📝',
  memory: 'Đã có các gợi ý bộ nhớ 1-click, nạp ngay để cá nhân hóa nhé! 🧠',
  harness: 'Xem báo cáo kiểm thử và chất lượng câu trả lời tại đây 📊',
  settings: 'Quản trị hạn mức và cấu hình hệ thống an toàn tại đây ⚙️',
}

export function MascotAssistant({
  status = 'idle',
  statusText,
  currentPage = 'chat',
  onNavigateToChat,
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
  const [pokeCount, setPokeCount] = useState(0)
  const [capacity, setCapacity] = useState<ProviderCapacity | null>(null)
  const speechTimer = useRef<number | null>(null)
  const mascot = MASCOT_CHOICES.find((choice) => choice.id === selectedMascotId) ?? MASCOT_CHOICES[0]!

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
  }, [])

  function showSpeech(text: string, duration = 4000) {
    if (speechTimer.current) window.clearTimeout(speechTimer.current)
    setSpeech(text)
    speechTimer.current = window.setTimeout(() => setSpeech(null), duration)
  }

  // React to status changes
  useEffect(() => {
    if (status === 'running') {
      showSpeech(statusText || 'Đang tra cứu dữ liệu & xử lý câu hỏi…', 5000)
    } else if (status === 'completed') {
      showSpeech('Xong rồi nha! Bạn kiểm tra kết quả nhé ✨', 4500)
    } else if (status === 'failed') {
      showSpeech('Có chút trục trặc nhỏ, bạn xem lại chi tiết nhé!', 4000)
    }
  }, [status, statusText])

  // Contextual tip on page change
  useEffect(() => {
    if (minimized) return
    const tip = PAGE_TIPS[currentPage]
    if (tip) {
      const timer = window.setTimeout(() => {
        showSpeech(tip, 5000)
      }, 1500)
      return () => window.clearTimeout(timer)
    }
  }, [currentPage, minimized])

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
    setPokeCount((c) => c + 1)
    if (capacity?.local_budget) {
      showSpeech(
        `Key hiệu lực ${capacity.display_name || capacity.credential_source}${capacity.failover_active ? ' (dự phòng)' : ''}: còn ${capacity.local_budget.daily_remaining}/${capacity.local_budget.daily_limit} lượt trong ledger local hôm nay.`,
        5000,
      )
      return
    }
    const cheers = [
      `Chào bạn! Mình là trợ lý ${mascot.label} của Veridra.`,
      'Bấm vào nút "Chat" để hỏi mình bất kỳ lúc nào nhé!',
      'Hôm nay làm việc năng suất lắm nè ✨',
      'Đừng quên kiểm tra Bản tin sáng trên trang chủ nha!',
      'File local của bạn đã nạp vào RAG rồi đấy, tra cứu rất nhanh!',
      'Sẵn sàng rồi, cùng nhau làm việc nào!',
    ]
    showSpeech(cheers[pokeCount % cheers.length] ?? `Chào bạn! Mình là trợ lý ${mascot.label} của Veridra.`, 3500)
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
    showSpeech('Mở khung trò chuyện ngay nè! ✨', 2500)
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
    >
      {speech && !minimized ? (
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
          {currentPage !== 'chat' && (
            <button type="button" className="mascot-speech__action" onClick={goToChat}>
              <Chat16Regular /> Đi đến Trò chuyện
            </button>
          )}
        </div>
      ) : null}

      <div className="mascot-frame" onClick={handlePoke}>
        {minimized ? (
          <button
            type="button"
            className="mascot-restore-btn"
            onClick={(e) => {
              e.stopPropagation()
              toggleMinimize()
            }}
            title="Mở lại trợ lý linh vật"
            aria-label="Mở lại trợ lý linh vật"
          >
            <span className="mascot-restore-icon" aria-hidden="true" style={{ backgroundImage: `url(${mascot.directions})` }} />
            <span className="mascot-status-pulse" />
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
                <span>Chat</span>
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
                  ? `${capacity.local_budget.daily_remaining}/${capacity.local_budget.daily_limit} lượt local`
                  : capacity?.configured ? 'Đang đồng bộ' : 'Chưa có key'}
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
