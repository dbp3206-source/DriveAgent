import {
  ArrowRight20Regular,
  Bot20Regular,
  Brain20Regular,
  CheckmarkCircle20Regular,
  Database20Regular,
  Dismiss20Regular,
  DocumentCheckmark20Regular,
  Flowchart20Regular,
  LockClosed20Regular,
  Play20Regular,
  ShieldCheckmark20Regular,
  Sparkle20Regular,
  Wrench20Regular,
} from '@fluentui/react-icons'
import { useEffect, useMemo, useState } from 'react'
import {
  HARNESS_TECH_GROUPS,
  TECH_STACK_ITEMS,
  type HarnessGroupKey,
  type TechItem,
  type TechStackGroup,
} from '../../harnessScenarios'

export interface TechInspectorDrawerProps {
  isOpen: boolean
  selectedTechId: string | null
  onClose: () => void
  onSelectTech?: (techId: string) => void
}

function getGroupIcon(groupId: HarnessGroupKey) {
  switch (groupId) {
    case 'adk':
      return <Bot20Regular aria-hidden="true" />
    case 'context':
      return <Brain20Regular aria-hidden="true" />
    case 'storage':
      return <Database20Regular aria-hidden="true" />
    case 'tools':
      return <Wrench20Regular aria-hidden="true" />
    case 'orchestration':
      return <Flowchart20Regular aria-hidden="true" />
    case 'eval':
      return <ShieldCheckmark20Regular aria-hidden="true" />
    default:
      return <Sparkle20Regular aria-hidden="true" />
  }
}

function findTechItem(idOrName: string | null): TechItem | undefined {
  if (!idOrName) return undefined
  if (TECH_STACK_ITEMS[idOrName]) return TECH_STACK_ITEMS[idOrName]
  const normalized = idOrName.toLowerCase().trim()
  return Object.values(TECH_STACK_ITEMS).find(
    (item) =>
      item.id.toLowerCase() === normalized ||
      item.name.toLowerCase() === normalized ||
      item.id.replace(/-/g, '_') === normalized.replace(/-/g, '_') ||
      normalized.includes(item.id) ||
      item.name.toLowerCase().includes(normalized),
  )
}

const DEFAULT_TECH: TechItem = Object.values(TECH_STACK_ITEMS)[0] ?? {
  id: 'google-adk',
  name: 'Google ADK',
  harnessGroup: 'adk',
  plainEnglish: 'Bộ não điều phối tổng quát, đóng vai trò như trưởng nhóm tiếp nhận công việc và phân công cho đúng chuyên viên.',
  driveAgentRole: 'Đóng gói vòng đời tác tử (agent lifecycle), duy trì phiên làm việc stateful và phân giải câu lệnh slash.',
  anatomy: [
    'Kích hoạt: Tiếp nhận câu lệnh tự nhiên hoặc lệnh slash từ giao diện người dùng.',
    'Kiểm soát: Giới hạn token budget, ép buộc timeout và kiểm tra quyền hạn mức phiên.',
    'Xuất kết quả: Kế hoạch thực thi chuẩn hóa và chỉ định agent chuyên trách xử lý.',
  ],
}

const DEFAULT_GROUP: TechStackGroup = HARNESS_TECH_GROUPS[0] ?? {
  id: 'adk',
  title: '1. ADK Agent Framework',
  subtitle: 'Nền tảng tác tử, quản lý phiên và phân rã mục tiêu',
  badge: 'Framework',
  color: '#3b82f6',
}

export function TechInspectorDrawer({
  isOpen,
  selectedTechId,
  onClose,
  onSelectTech,
}: TechInspectorDrawerProps) {
  // Resolve current active tech item
  const initialItem: TechItem = useMemo(() => {
    return findTechItem(selectedTechId) ?? DEFAULT_TECH
  }, [selectedTechId])

  const [activeTechId, setActiveTechId] = useState<string>(initialItem.id)
  const [activeGroupId, setActiveGroupId] = useState<HarnessGroupKey>(initialItem.harnessGroup)

  // Sync state when drawer opens or selectedTechId changes
  useEffect(() => {
    if (isOpen) {
      if (selectedTechId) {
        const found = findTechItem(selectedTechId)
        if (found) {
          setActiveTechId(found.id)
          setActiveGroupId(found.harnessGroup)
        }
      } else {
        setActiveTechId(DEFAULT_TECH.id)
        setActiveGroupId(DEFAULT_TECH.harnessGroup)
      }
    }
  }, [isOpen, selectedTechId])

  // ESC key handler and body scroll lock for accessibility
  useEffect(() => {
    if (!isOpen) return

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, onClose])

  const currentTech: TechItem = useMemo(() => {
    return findTechItem(activeTechId) ?? DEFAULT_TECH
  }, [activeTechId])

  const currentGroup: TechStackGroup = useMemo(() => {
    return HARNESS_TECH_GROUPS.find((g) => g.id === activeGroupId) ?? DEFAULT_GROUP
  }, [activeGroupId])

  // Technologies partitioned by group
  const groupTechnologies = useMemo(() => {
    return Object.values(TECH_STACK_ITEMS).filter((t) => t.harnessGroup === activeGroupId)
  }, [activeGroupId])

  function handleSelect(tech: TechItem) {
    setActiveTechId(tech.id)
    setActiveGroupId(tech.harnessGroup)
    onSelectTech?.(tech.id)
  }

  function handleGroupTab(group: TechStackGroup) {
    setActiveGroupId(group.id)
    const firstInGroup = Object.values(TECH_STACK_ITEMS).find((t) => t.harnessGroup === group.id)
    if (firstInGroup) {
      setActiveTechId(firstInGroup.id)
      onSelectTech?.(firstInGroup.id)
    }
  }

  if (!isOpen) return null

  return (
    <>
      <div
        className="tech-inspector-backdrop"
        onClick={onClose}
        aria-hidden="true"
        data-testid="tech-inspector-backdrop"
      />
      <aside
        className="tech-inspector-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tech-inspector-title"
        aria-describedby="tech-inspector-subtitle"
      >
        {/* Drawer Header */}
        <header className="tech-inspector-header">
          <div className="tech-inspector-header__main">
            <span className="tech-inspector-header__eyebrow">
              <Sparkle20Regular aria-hidden="true" />
              INTERACTIVE TECH INSPECTOR · HARNESS SHOWCASE
            </span>
            <h2 id="tech-inspector-title" className="tech-inspector-header__title">
              Giải Phẫu Kiến Trúc & Công Nghệ Harness
            </h2>
            <p id="tech-inspector-subtitle" className="tech-inspector-header__subtitle">
              Phân loại theo 5/6 nhóm chuẩn mực. Khám phá bản chất đời thường, vai trò trong hệ thống và sơ đồ giải phẫu 3 bước.
            </p>
          </div>
          <button
            type="button"
            className="tech-inspector-close-btn"
            onClick={onClose}
            aria-label="Đóng Tech Inspector"
            title="Đóng (Esc)"
          >
            <Dismiss20Regular aria-hidden="true" />
          </button>
        </header>

        {/* 5/6 Harness Groups Navigation */}
        <nav className="tech-inspector-groups" aria-label="Nhóm công nghệ Harness">
          {HARNESS_TECH_GROUPS.map((group) => {
            const isGroupActive = group.id === activeGroupId
            const count = Object.values(TECH_STACK_ITEMS).filter((t) => t.harnessGroup === group.id).length
            return (
              <button
                key={group.id}
                type="button"
                className={`tech-group-tab ${isGroupActive ? 'is-active' : ''}`}
                style={{ ['--group-color' as string]: group.color }}
                onClick={() => handleGroupTab(group)}
              >
                <span className="tech-group-tab__icon">{getGroupIcon(group.id)}</span>
                <span className="tech-group-tab__info">
                  <strong>{group.title}</strong>
                  <small>{group.badge} · {count} module</small>
                </span>
              </button>
            )
          })}
        </nav>

        {/* Sub-navigation: Technology chips within active group */}
        <div className="tech-inspector-chips" role="tablist" aria-label="Danh sách module trong nhóm">
          {groupTechnologies.map((tech) => {
            const isTechActive = tech.id === currentTech.id
            return (
              <button
                key={tech.id}
                type="button"
                role="tab"
                aria-selected={isTechActive}
                className={`tech-chip ${isTechActive ? 'is-active' : ''}`}
                onClick={() => handleSelect(tech)}
              >
                <span className="tech-chip__dot" aria-hidden="true" />
                <span className="tech-chip__label">{tech.name}</span>
              </button>
            )
          })}
        </div>

        {/* 3-Tier Anatomy Display */}
        <section className="tech-anatomy-container">
          {/* Active Technology Banner */}
          <div className="tech-anatomy-banner" style={{ ['--group-color' as string]: currentGroup.color }}>
            <div className="tech-anatomy-banner__header">
              <span className="tech-anatomy-banner__badge">
                {getGroupIcon(currentGroup.id)} {currentGroup.title}
              </span>
              <span className="tech-anatomy-banner__id">{currentTech.id}</span>
            </div>
            <h3 className="tech-anatomy-banner__title">{currentTech.name}</h3>
            <p className="tech-anatomy-banner__subtitle">{currentGroup.subtitle}</p>
          </div>

          <div className="tech-anatomy-tiers">
            {/* TIER 1: Plain English */}
            <article className="tech-tier-card tech-tier-card--plain">
              <div className="tech-tier-card__header">
                <span className="tech-tier-badge">TẦNG 1 · BẢN CHẤT ĐỜI THƯỜNG</span>
                <h4>Góc nhìn thực tế (Plain English)</h4>
              </div>
              <p className="tech-tier-card__body">{currentTech.plainEnglish}</p>
              <div className="tech-tier-card__footer">
                <CheckmarkCircle20Regular className="tech-tier-card__footer-icon" aria-hidden="true" />
                <span>Diễn giải dễ hiểu, không đánh đố thuật ngữ học thuật</span>
              </div>
            </article>

            {/* TIER 2: DriveAgent Role */}
            <article className="tech-tier-card tech-tier-card--role">
              <div className="tech-tier-card__header">
                <span className="tech-tier-badge tech-tier-badge--role">TẦNG 2 · VAI TRÒ KIẾN TRÚC</span>
                <h4>Sứ mệnh trong Veridra</h4>
              </div>
              <p className="tech-tier-card__body">{currentTech.driveAgentRole}</p>
              <div className="tech-tier-card__footer">
                <ShieldCheckmark20Regular className="tech-tier-card__footer-icon" aria-hidden="true" />
                <span>Bảo chứng độ an toàn, tuân thủ kiểm toán và phân tách quyền hạn</span>
              </div>
            </article>

            {/* TIER 3: 3-Step Anatomy Diagram */}
            <article className="tech-tier-card tech-tier-card--anatomy">
              <div className="tech-tier-card__header">
                <span className="tech-tier-badge tech-tier-badge--anatomy">TẦNG 3 · GIẢI PHẪU QUY TRÌNH 3 BƯỚC</span>
                <h4>Luồng thực thi nội bộ (Execution Anatomy)</h4>
              </div>

              <div className="tech-anatomy-steps">
                {/* Step 1: Trigger */}
                <div className="tech-anatomy-step tech-anatomy-step--trigger">
                  <div className="tech-anatomy-step__indicator">
                    <span className="tech-anatomy-step__num">01</span>
                    <Play20Regular className="tech-anatomy-step__icon" aria-hidden="true" />
                  </div>
                  <div className="tech-anatomy-step__content">
                    <strong className="tech-anatomy-step__label">KÍCH HOẠT (Trigger)</strong>
                    <p>{(currentTech.anatomy?.[0] ?? '').replace(/^Kích hoạt:\s*/i, '')}</p>
                  </div>
                </div>

                <div className="tech-anatomy-connector" aria-hidden="true">
                  <ArrowRight20Regular />
                </div>

                {/* Step 2: Control */}
                <div className="tech-anatomy-step tech-anatomy-step--control">
                  <div className="tech-anatomy-step__indicator">
                    <span className="tech-anatomy-step__num">02</span>
                    <LockClosed20Regular className="tech-anatomy-step__icon" aria-hidden="true" />
                  </div>
                  <div className="tech-anatomy-step__content">
                    <strong className="tech-anatomy-step__label">KIỂM SOÁT (Control & Gate)</strong>
                    <p>{(currentTech.anatomy?.[1] ?? '').replace(/^Kiểm soát:\s*/i, '')}</p>
                  </div>
                </div>

                <div className="tech-anatomy-connector" aria-hidden="true">
                  <ArrowRight20Regular />
                </div>

                {/* Step 3: Output */}
                <div className="tech-anatomy-step tech-anatomy-step--output">
                  <div className="tech-anatomy-step__indicator">
                    <span className="tech-anatomy-step__num">03</span>
                    <DocumentCheckmark20Regular className="tech-anatomy-step__icon" aria-hidden="true" />
                  </div>
                  <div className="tech-anatomy-step__content">
                    <strong className="tech-anatomy-step__label">XUẤT KẾT QUẢ (Output & Audit)</strong>
                    <p>{(currentTech.anatomy?.[2] ?? '').replace(/^Xuất kết quả:\s*/i, '')}</p>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        {/* Drawer Footer Actions */}
        <footer className="tech-inspector-footer">
          <div className="tech-inspector-footer__note">
            <span>Module này tuân thủ các kiểm soát Zero Trust được triển khai trong Google ADK và Veridra.</span>
          </div>
          <button type="button" className="tech-inspector-btn tech-inspector-btn--close" onClick={onClose}>
            Đóng cửa sổ
          </button>
        </footer>
      </aside>
    </>
  )
}
