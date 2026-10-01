import {
  ArrowRight20Regular,
  Copy20Regular,
  Open20Regular,
  Sparkle20Regular,
} from '@fluentui/react-icons'
import { useState } from 'react'
import { type HarnessScenario } from '../../harnessScenarios'

export interface InteractiveTestDriveProps {
  scenario: HarnessScenario
}

export const CHAT_LAUNCH_CONFIG = Object.freeze({
  storageKey: 'drive_agent_chat_launch',
  eventName: 'driveagent:chat-launch',
  targetRoute: 'chat',
})

export function InteractiveTestDrive({ scenario }: InteractiveTestDriveProps) {
  const [copied, setCopied] = useState(false)

  // Extract skill identifier from suggestedCommand (e.g. /skill:daily_reconciliation -> daily_reconciliation)
  const skillToken = scenario.suggestedCommand
    .split(/\s+/)
    .find((t) => t.startsWith('/skill:'))
  const skillName = skillToken ? skillToken.replace('/skill:', '') : 'default_skill'

  function handleTestDriveLaunch() {
    const domainControls = {
      banking: { source: 'local', agent: 'research', output: 'spreadsheet', workflow: 'compare_sources' },
      education: { source: 'drive', agent: 'study', output: 'document', workflow: 'study_plan' },
      ecommerce: { source: 'auto', agent: 'workspace', output: 'spreadsheet', workflow: 'budget_tracker' },
    }[scenario.id] || { source: 'auto', agent: 'auto', output: 'chat', workflow: 'auto' }

    const payload = {
      prompt: scenario.request,
      controls: {
        ...domainControls,
        domain: scenario.id,
        skill: skillName,
        skill_name: skillName,
      },
    }

    try {
      sessionStorage.setItem(CHAT_LAUNCH_CONFIG.storageKey, JSON.stringify(payload))
    } catch {
      /* SessionStorage safe fallback */
    }

    try {
      localStorage.setItem(CHAT_LAUNCH_CONFIG.storageKey, JSON.stringify(payload))
    } catch {
      /* LocalStorage safe fallback */
    }

    try {
      window.dispatchEvent(
        new CustomEvent(CHAT_LAUNCH_CONFIG.eventName, {
          detail: payload,
        }),
      )
    } catch {
      /* Event dispatch fallback */
    }

    // Direct navigation to chat page
    window.location.hash = '#/chat'
  }

  function fallbackCopy() {
    try {
      const textarea = document.createElement('textarea')
      textarea.value = scenario.suggestedCommand
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      /* fallback */
    }
  }

  function handleCopyCommand() {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(scenario.suggestedCommand).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2500)
      }).catch(() => {
        fallbackCopy()
      })
    } else {
      fallbackCopy()
    }
  }

  // Parse flags for visual presentation
  const flags = scenario.suggestedCommand
    .split(/\s+/)
    .filter((t) => t.startsWith('/'))

  return (
    <section className="interactive-test-drive" aria-labelledby="test-drive-title">
      <div className="interactive-test-drive__card">
        {/* Glow ambient background element */}
        <div className="interactive-test-drive__glow" aria-hidden="true" />

        <div className="interactive-test-drive__content">
          <div className="interactive-test-drive__header">
            <span className="interactive-test-drive__eyebrow">
              <Sparkle20Regular aria-hidden="true" />
              1-CLICK INTERACTIVE TEST DRIVE
            </span>
            <h2 id="test-drive-title" className="interactive-test-drive__title">
              Trải Nghiệm Kịch Bản Này Trên Chat Ngay
            </h2>
            <p className="interactive-test-drive__desc">
              Chuyển toàn bộ bối cảnh nghiệp vụ, cờ kiểm soát slash và yêu cầu mẫu của kịch bản{' '}
              <strong>{scenario.title}</strong> vào giao diện Chat tác tử chỉ với một cú nhấp chuột.
            </p>
          </div>

          {/* Prompt Terminal Preview */}
          <div className="interactive-test-drive__preview-box">
            <div className="interactive-test-drive__preview-top">
              <span className="interactive-test-drive__preview-label">
                PROMPT & CỜ THIẾT LẬP TỰ ĐỘNG
              </span>
              <div className="interactive-test-drive__flags">
                {flags.map((flag) => (
                  <span key={flag} className="interactive-test-drive__flag-pill">
                    {flag}
                  </span>
                ))}
              </div>
            </div>

            <div className="interactive-test-drive__cmd-line">
              <span className="interactive-test-drive__prompt-symbol">&gt;</span>
              <code>{scenario.suggestedCommand}</code>
            </div>

            <div className="interactive-test-drive__prompt-text">
              <span className="interactive-test-drive__quote-symbol">“</span>
              <p>{scenario.request}</p>
            </div>
          </div>

          {/* Action Row */}
          <div className="interactive-test-drive__actions">
            <button
              type="button"
              className="interactive-test-drive__cta-btn"
              onClick={handleTestDriveLaunch}
            >
              <Sparkle20Regular aria-hidden="true" />
              <span>Trải nghiệm kịch bản này trên Chat ngay</span>
              <ArrowRight20Regular aria-hidden="true" />
            </button>

            <button
              type="button"
              className={`interactive-test-drive__secondary-btn ${copied ? 'is-copied' : ''}`}
              onClick={handleCopyCommand}
            >
              {copied ? (
                <>
                  <Open20Regular aria-hidden="true" />
                  <span>Đã chép lệnh!</span>
                </>
              ) : (
                <>
                  <Copy20Regular aria-hidden="true" />
                  <span>Sao chép lệnh slash</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
