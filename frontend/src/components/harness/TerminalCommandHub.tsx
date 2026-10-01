import {
  Button,
  Popover,
  PopoverSurface,
  PopoverTrigger,
} from '@fluentui/react-components'
import {
  ArrowRouting20Regular,
  Chat16Regular,
  Checkmark16Regular,
  Copy16Regular,
  Document16Regular,
  Folder16Regular,
  Info16Regular,
  ShieldCheckmark16Regular,
  Sparkle16Regular,
  Table16Regular,
} from '@fluentui/react-icons'
import { useMemo, useState } from 'react'
import type { ChatControls } from '../../chatControls'
import type { HarnessScenarioId } from '../../harnessScenarios'
import './harnessComponents.css'

export interface TerminalCommandHubProps {
  domainId: HarnessScenarioId
  suggestedCommand: string
  request: string
  title: string
  onOpenChat?: () => void
}

interface ParsedToken {
  raw: string
  isFlag: boolean
  flagBase: string
  param?: string
}

const FLAG_META: Record<string, {
  name: string
  harness: string
  description: string
  safety: string
  icon: React.ReactNode
}> = {
  '/skill': {
    name: 'Skill Injection Harness',
    harness: 'ADK & Agent Memory',
    description: 'Nạp bộ quy trình, rubric kiểm tra và mẫu hồ sơ chuẩn hóa vào bộ nhớ tác tử.',
    safety: 'Chỉ nạp skill đã được kiểm duyệt và lưu trong danh mục tin cậy của doanh nghiệp.',
    icon: <Sparkle16Regular />,
  },
  '/local': {
    name: 'Local Source Boundary Harness',
    harness: 'Context & Local Storage',
    description: 'Giới hạn dữ liệu đầu vào trên máy khách, kiểm tra mã băm SHA-256 chống sửa đổi.',
    safety: 'Tệp được chọn đọc từ máy trạm; khi hỏi AI, nội dung liên quan có thể được gửi tới nhà cung cấp mô hình theo cấu hình.',
    icon: <Folder16Regular />,
  },
  '/sheet': {
    name: 'Google Sheets Two-Phase Harness',
    harness: 'Tool Harness & Governance',
    description: 'Đọc dữ liệu bảng tính đối soát; ghi dữ liệu mới bắt buộc qua bản Proposal xem trước.',
    safety: 'Bảo vệ công thức tính toán và ngăn chặn ghi đè làm hỏng sổ sách.',
    icon: <Table16Regular />,
  },
  '/doc': {
    name: 'Google Docs Proposal Harness',
    harness: 'Tool Harness & Output Contract',
    description: 'Khởi tạo bản thảo Google Docs theo cấu trúc đã chọn; citation metadata cần được đối chiếu với nội dung nguồn.',
    safety: 'Chỉ xuất bản nháp (Draft); người dùng duyệt mới ghi chính thức vào Drive.',
    icon: <Document16Regular />,
  },
  '/drive': {
    name: 'Google Drive Semantic RAG Harness',
    harness: 'Context Harness & Hybrid RAG',
    description: 'Truy vấn ngữ nghĩa Drive qua Qdrant Embedded & RRF để tìm đúng trang căn cứ.',
    safety: 'Tuân thủ nghiêm ngặt OAuth scope quyền đọc đã được người dùng ủy quyền.',
    icon: <Folder16Regular />,
  },
  '/auto': {
    name: 'Autonomous Multi-Agent DAG Harness',
    harness: 'Orchestration Harness',
    description: 'Cho phép ADK tự phân rã DAG và điều phối tác vụ giữa các chuyên gia chuyên trách.',
    safety: 'Đặt dưới giới hạn số vòng lặp an toàn (Loop Guard) và dừng lại khi cần quyết định.',
    icon: <ArrowRouting20Regular />,
  },
}

export function TerminalCommandHub({
  domainId,
  suggestedCommand,
  request,
  title,
  onOpenChat,
}: TerminalCommandHubProps) {
  const [copied, setCopied] = useState(false)

  // Tokenize command string
  const tokens = useMemo<ParsedToken[]>(() => {
    const parts = suggestedCommand.trim().split(/\s+/)
    return parts.map((part) => {
      if (part.startsWith('/')) {
        const colonIdx = part.indexOf(':')
        const flagBase = colonIdx > -1 ? part.slice(0, colonIdx) : part
        const param = colonIdx > -1 ? part.slice(colonIdx + 1) : undefined
        return { raw: part, isFlag: true, flagBase, param }
      }
      return { raw: part, isFlag: false, flagBase: '' }
    })
  }, [suggestedCommand])

  // 1-Click copy with 2-second visual feedback
  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(suggestedCommand)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = suggestedCommand
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignore clipboard permission errors
    }
  }

  // Deep-link to Chat with session storage and custom event launch
  const handleOpenChat = () => {
    const controls: ChatControls = {
      source: domainId === 'banking' ? 'local' : (domainId === 'education' ? 'drive' : 'auto'),
      agent: domainId === 'education' ? 'study' : 'workspace',
      output: domainId === 'education' ? 'document' : 'spreadsheet',
      workflow: domainId === 'banking' ? 'budget_tracker' : (domainId === 'education' ? 'study_plan' : 'auto'),
      skill_name: domainId === 'banking' ? 'daily_reconciliation' : (domainId === 'education' ? 'rubric_support' : 'campaign_review'),
    }

    const detail = {
      prompt: `${suggestedCommand}\n\n${request}`,
      controls,
    }

    try {
      sessionStorage.setItem('drive_agent_chat_launch', JSON.stringify(detail))
    } catch {
      // storage is optional
    }

    window.dispatchEvent(new CustomEvent('driveagent:chat-launch', { detail }))
    window.location.hash = '#/chat'
    onOpenChat?.()
  }

  return (
    <div className={`terminal-hub terminal-hub--${domainId}`} aria-label="Terminal Command Hub">
      <div className="terminal-hub__topbar">
        <div className="terminal-hub__window-controls" aria-hidden="true">
          <span className="terminal-hub__dot terminal-hub__dot--close" />
          <span className="terminal-hub__dot terminal-hub__dot--minimize" />
          <span className="terminal-hub__dot terminal-hub__dot--maximize" />
          <span className="terminal-hub__label">TERMINAL COMMAND HUB · VERIDRA RUNTIME</span>
        </div>

        <div className="terminal-hub__actions">
          <Button
            appearance="subtle"
            size="small"
            icon={copied ? <Checkmark16Regular className="terminal-hub__copied-icon" /> : <Copy16Regular />}
            onClick={handleCopy}
            className={`terminal-hub__btn terminal-hub__btn--copy ${copied ? 'is-copied' : ''}`}
            aria-label="Sao chép câu lệnh"
          >
            {copied ? 'Đã chép!' : 'Sao chép lệnh'}
          </Button>

          <Button
            appearance="primary"
            size="small"
            icon={<Chat16Regular />}
            onClick={handleOpenChat}
            className="terminal-hub__btn terminal-hub__btn--chat"
          >
            Mở trên Chat
          </Button>
        </div>
      </div>

      <div className="terminal-hub__body">
        <div className="terminal-hub__line">
          <span className="terminal-hub__prompt">$</span>
          <span className="terminal-hub__cmd-base">drive-agent run</span>

          <div className="terminal-hub__tokens">
            {tokens.map((token, idx) => {
              if (!token.isFlag) {
                return (
                  <span key={idx} className="terminal-hub__arg">
                    {token.raw}
                  </span>
                )
              }

              const meta = FLAG_META[token.flagBase] ?? {
                name: token.flagBase,
                harness: 'Runtime Flag',
                description: 'Cờ điều khiển môi trường thực thi của tác tử.',
                safety: 'Chạy trong phạm vi chính sách an toàn đã thiết lập.',
                icon: <Info16Regular />,
              }

              return (
                <Popover key={idx} withArrow positioning="above">
                  <PopoverTrigger>
                    <button
                      type="button"
                      className="terminal-hub__flag-badge"
                      aria-label={`Chi tiết cờ ${token.raw}`}
                    >
                      {meta.icon}
                      <span className="terminal-hub__flag-name">{token.flagBase}</span>
                      {token.param ? <span className="terminal-hub__flag-param">:{token.param}</span> : null}
                    </button>
                  </PopoverTrigger>
                  <PopoverSurface className="terminal-popover">
                    <div className="terminal-popover__header">
                      <span className="terminal-popover__badge">{meta.harness}</span>
                      <strong>{meta.name}</strong>
                    </div>
                    <p className="terminal-popover__desc">{meta.description}</p>
                    <div className="terminal-popover__safety">
                      <ShieldCheckmark16Regular />
                      <span>{meta.safety}</span>
                    </div>
                  </PopoverSurface>
                </Popover>
              )
            })}
          </div>
        </div>

        <div className="terminal-hub__meta-row">
          <span className="terminal-hub__hint">
            💡 Bấm vào từng cờ lệnh để xem cơ chế nạp bối cảnh hoặc bấm <strong>"Mở trên Chat"</strong> để chạy ngay kịch bản.
          </span>
          <span className="terminal-hub__domain-tag">{title}</span>
        </div>
      </div>
    </div>
  )
}
