import { Button, Input, Spinner, Textarea } from '@fluentui/react-components'
import {
  Add20Regular,
  Archive20Regular,
  BrainCircuit20Regular,
  Checkmark16Regular,
  Checkmark20Regular,
  ChevronDown20Regular,
  ChevronUp20Regular,
  Copy20Regular,
  Cube20Regular,
  Dismiss16Regular,
  DocumentText20Regular,
  Folder20Regular,
  Mail20Regular,
  Play20Regular,
  ReOrderDotsVertical20Regular,
  Save20Regular,
  Search20Regular,
  Sparkle20Regular,
  Table20Regular,
  Tag20Regular,
} from '@fluentui/react-icons'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState, LoadingState } from '../components/AsyncState'

export type Skill = {
  id: string
  name: string
  title: string
  description: string
  goal: string
  procedure: string[]
  constraints: string[]
  preferred_capabilities: string[]
  output_format: string
  revision: number
  active: boolean
}

export type SkillRunResult = {
  goal: string
  procedure: string[]
  constraints: string[]
  output_format: string
  preferred_capabilities: string[]
}

export interface SkillColorTheme {
  accent: string
  bg: string
  border: string
  gradient: string
  glow: string
}

const SKILL_PALETTES: SkillColorTheme[] = [
  {
    accent: '#6366f1',
    bg: 'rgba(99, 102, 241, 0.08)',
    border: 'rgba(99, 102, 241, 0.3)',
    gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
    glow: 'rgba(99, 102, 241, 0.25)',
  },
  {
    accent: '#0ea5e9',
    bg: 'rgba(14, 165, 233, 0.08)',
    border: 'rgba(14, 165, 233, 0.3)',
    gradient: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
    glow: 'rgba(14, 165, 233, 0.25)',
  },
  {
    accent: '#10b981',
    bg: 'rgba(16, 185, 129, 0.08)',
    border: 'rgba(16, 185, 129, 0.3)',
    gradient: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    glow: 'rgba(16, 185, 129, 0.25)',
  },
  {
    accent: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.08)',
    border: 'rgba(245, 158, 11, 0.3)',
    gradient: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
    glow: 'rgba(245, 158, 11, 0.25)',
  },
  {
    accent: '#ec4899',
    bg: 'rgba(236, 72, 153, 0.08)',
    border: 'rgba(236, 72, 153, 0.3)',
    gradient: 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)',
    glow: 'rgba(236, 72, 153, 0.25)',
  },
  {
    accent: '#8b5cf6',
    bg: 'rgba(139, 92, 246, 0.08)',
    border: 'rgba(139, 92, 246, 0.3)',
    gradient: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
    glow: 'rgba(139, 92, 246, 0.25)',
  },
  {
    accent: '#14b8a6',
    bg: 'rgba(20, 184, 166, 0.08)',
    border: 'rgba(20, 184, 166, 0.3)',
    gradient: 'linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)',
    glow: 'rgba(20, 184, 166, 0.25)',
  },
]

function getSkillColorTheme(name: string): SkillColorTheme {
  const defaultTheme: SkillColorTheme = {
    accent: '#6366f1',
    bg: 'rgba(99, 102, 241, 0.08)',
    border: 'rgba(99, 102, 241, 0.3)',
    gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
    glow: 'rgba(99, 102, 241, 0.25)',
  }
  if (!name) return SKILL_PALETTES[0] ?? defaultTheme
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i)
    hash |= 0
  }
  const index = Math.abs(hash) % SKILL_PALETTES.length
  return SKILL_PALETTES[index] ?? defaultTheme
}

interface CapabilityConfig {
  key: string
  label: string
  icon: typeof Folder20Regular
  badgeColor: string
  desc: string
}

const CAPABILITY_CONFIGS: CapabilityConfig[] = [
  {
    key: 'drive',
    label: 'Google Drive',
    icon: Folder20Regular,
    badgeColor: '#0ea5e9',
    desc: 'Tìm kiếm và trích xuất nội dung file Drive',
  },
  {
    key: 'gmail',
    label: 'Gmail Inbox',
    icon: Mail20Regular,
    badgeColor: '#ef4444',
    desc: 'Tìm kiếm thư và đọc luồng email',
  },
  {
    key: 'rag',
    label: 'Kho Tri Thức RAG',
    icon: Search20Regular,
    badgeColor: '#8b5cf6',
    desc: 'Tra cứu thông tin theo ngữ nghĩa tài liệu',
  },
  {
    key: 'memory',
    label: 'Bộ Nhớ Memory',
    icon: BrainCircuit20Regular,
    badgeColor: '#10b981',
    desc: 'Gợi lại sở thích & ngữ cảnh cá nhân',
  },
  {
    key: 'docs',
    label: 'Google Docs',
    icon: DocumentText20Regular,
    badgeColor: '#3b82f6',
    desc: 'Tạo tài liệu và bản nháp nội dung',
  },
  {
    key: 'sheets',
    label: 'Google Sheets',
    icon: Table20Regular,
    badgeColor: '#059669',
    desc: 'Tạo và quản lý dữ liệu bảng tính',
  },
  {
    key: 'artifacts',
    label: 'Artifacts',
    icon: Cube20Regular,
    badgeColor: '#f59e0b',
    desc: 'Lưu trữ và tái sử dụng mã nguồn/tài liệu',
  },
]

const OUTPUT_FORMAT_OPTIONS = [
  { key: 'markdown', label: 'Markdown', desc: 'Văn bản định dạng Rich text' },
  { key: 'table', label: 'Bảng dữ liệu', desc: 'Dữ liệu dạng bảng lưới cột' },
  { key: 'json', label: 'JSON cấu trúc', desc: 'Dữ liệu JSON có schema chuẩn' },
  { key: 'checklist', label: 'Checklist', desc: 'Danh sách việc cần làm' },
]

const PRESET_TEMPLATES: Array<Omit<Skill, 'id' | 'revision' | 'active'>> = [
  {
    name: 'weekly_study_plan',
    title: 'Kế hoạch học tập tuần',
    description: 'Lên lịch học, bài tập và ôn tập theo từng môn cho cả tuần',
    goal: 'Tạo thời khóa biểu học tập chi tiết 7 ngày cho môn {subject}, tối ưu thời gian ôn thi',
    procedure: [
      'Thu thập danh sách môn học và đề cương từ Drive',
      'Phân bổ thời gian học mỗi ngày từ 2 đến 3 tiếng',
      'Đánh dấu các mốc nộp bài tập và deadline quan trọng',
      'Lập bảng theo dõi tiến độ từng môn học',
    ],
    constraints: ['Không xếp lịch học quá 4 tiếng/ngày', 'Dành sáng Chủ nhật để nghỉ ngơi'],
    preferred_capabilities: ['drive', 'docs'],
    output_format: 'markdown',
  },
  {
    name: 'daily_email_triage',
    title: 'Phân loại Email công việc',
    description: 'Đọc và lọc email quan trọng trong ngày, tạo việc cần làm',
    goal: 'Tóm tắt các email từ đối tác và đồng nghiệp cần phản hồi trong ngày hôm nay',
    procedure: [
      'Tìm kiếm thư chưa đọc có gắn cờ quan trọng trong hộp thư',
      'Trích xuất yêu cầu công việc và deadline từ nội dung email',
      'Tạo danh sách các hành động cần thực hiện',
    ],
    constraints: ['Bỏ qua thư quảng cáo và bản tin tự động', 'Ưu tiên email từ quản lý'],
    preferred_capabilities: ['gmail', 'memory'],
    output_format: 'checklist',
  },
  {
    name: 'research_knowledge_brief',
    title: 'Tổng hợp tri thức nghiên cứu',
    description: 'Tra cứu Semantic RAG từ tài liệu nội bộ và đúc kết báo cáo',
    goal: 'Tổng hợp các phát hiện chính về chủ đề {topic} từ kho tài liệu',
    procedure: [
      'Tìm kiếm tài liệu liên quan trong kho tri thức RAG',
      'Trích xuất bằng chứng xác thực và số liệu then chốt',
      'So sánh các quan điểm khác nhau và đúc kết luận điểm',
      'Đóng gói thành bản tóm tắt điều hành',
    ],
    constraints: ['Chỉ sử dụng tài liệu đã được xác thực', 'Trích dẫn nguồn cụ thể'],
    preferred_capabilities: ['rag', 'docs', 'artifacts'],
    output_format: 'markdown',
  },
  {
    name: 'daily_news_brief',
    title: 'Bản tin chi tiết trong ngày',
    description: 'Đọc và tổng hợp các email “Bản chi tiết” từ Bảo Phúc Đinh trong ngày hiện tại, đến đúng thời điểm chạy.',
    goal: 'Tạo báo cáo có chiều sâu, hợp nhất toàn bộ nội dung các email “Bản chi tiết” nhận từ Bảo Phúc Đinh trong ngày hiện tại (Asia/Bangkok) đến thời điểm chạy; không chỉ cắt phần đầu thư.',
    procedure: [
      'Gọi gmail_read_matching_messages với from:"Bảo Phúc Đinh" subject:"Bản chi tiết", day_scope="today", timezone="Asia/Bangkok" và sender_name="Bảo Phúc Đinh"; để công cụ tự xác định ngày hiện tại, không tự tính local_date. Kiểm next_page_token cho đến khi hết. Nếu truy vấn người gửi không thấy thư, tìm theo subject nhưng vẫn lọc sender_name từ header; công cụ chấp nhận thứ tự tên Đinh Bảo Phúc tương đương.',
      'Dùng body đầy đủ đã đọc của từng thư phù hợp; chỉ giữ thư có người gửi xác minh được là Bảo Phúc Đinh, ngày nhận là hôm nay theo Asia/Bangkok và thời gian không vượt quá thời điểm chạy. Chỉ mở thread riêng nếu body thiếu; không dùng snippet làm nội dung tóm tắt.',
      'Đếm tất cả thư phù hợp có received_at_local trong ngày đang xét và không muộn hơn as_of_local. Báo số thư thực tế cùng thời điểm nhận, bất kể tiêu đề có nhãn 8h, 12h hay nhãn khác; không ép đủ bốn mốc, không suy đoán thư sẽ đến sau. Không coi thư không truy cập được là thư không tồn tại.',
      'Tổng hợp toàn bộ chủ đề, luận điểm, dữ kiện và diễn biến giữa các thư; gộp ý trùng, chỉ ra cập nhật/mâu thuẫn, phân biệt thông tin được email nêu với nhận định của AI; không thêm sự kiện ngoài nguồn.',
      'Viết báo cáo Markdown có phạm vi và số thư đã đọc, tóm lược điều hành, từng chủ đề với bằng chứng/diễn biến/ý nghĩa, điểm mới hoặc bất đồng giữa các mốc, việc cần theo dõi (tách riêng hành động được nêu rõ và gợi ý của AI), cùng giới hạn dữ liệu.',
      'Gắn citation Gmail ngay cạnh từng nhận định trọng yếu, bao quát mọi thư được tổng hợp. Nếu body, ảnh, tệp đính kèm hoặc trang nguồn không đọc được, ghi rõ phần thiếu và không suy diễn nội dung đó.',
    ],
    constraints: [
      'Chỉ đọc Gmail; không sửa nhãn, đánh dấu đã đọc, tạo nháp hay gửi thư.',
      'Chỉ đưa thư của đúng người gửi và đúng ngày địa phương hiện tại; loại thư hôm qua dù nằm trong cửa sổ tìm 48 giờ.',
      'Số thư trong báo cáo là số tìm thấy và đọc được lúc chạy; không giả định mỗi ngày phải đủ bốn thư hay đúng giờ ghi trên tiêu đề.',
      'Không tóm tắt từ snippet hoặc vài câu đầu; đọc toàn văn từng thư trước khi hợp nhất.',
      'Không bịa mốc gửi, số liệu, kết luận hoặc hành động; báo cáo rõ khi thiếu thư, thiếu quyền hoặc thiếu nội dung đọc được.',
      'Nếu có nhiều thư lặp lại cùng tin, gộp nhưng vẫn dẫn các nguồn liên quan; giữ khác biệt quan trọng giữa các phiên bản.',
    ],
    preferred_capabilities: ['gmail'],
    output_format: 'markdown_report',
  },
]

const emptySkill = (): Skill => ({
  id: '',
  name: '',
  title: '',
  description: '',
  goal: '',
  procedure: [''],
  constraints: [],
  preferred_capabilities: [],
  output_format: 'markdown',
  revision: 0,
  active: true,
})

const SKILL_NAME_REGEX = /^[a-z][a-z0-9_]*$/

export function SkillsPage() {
  const [items, setItems] = useState<Skill[]>([])
  const [selected, setSelected] = useState<Skill>(emptySkill)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [runResult, setRunResult] = useState<SkillRunResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [running, setRunning] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [error, setError] = useState('')
  const [copiedSection, setCopiedSection] = useState<string | null>(null)
  const [newConstraintDraft, setNewConstraintDraft] = useState('')
  const [expandedAccordions, setExpandedAccordions] = useState<Record<string, boolean>>({
    goal: true,
    procedure: true,
    constraints: true,
    capabilities: true,
    output: true,
  })

  async function load() {
    try {
      const response = await api<{ data: { items: Skill[] } }>('/api/skills')
      setItems(response.data.items)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được Skills.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  function validateSkill(skill: Skill): string | null {
    if (!SKILL_NAME_REGEX.test(skill.name) || skill.name.length < 3 || skill.name.length > 60) {
      return 'Tên kỹ thuật phải bắt đầu bằng chữ cái thường, chỉ gồm chữ thường, số, dấu gạch dưới và dài từ 3 đến 60 ký tự.'
    }
    if (skill.title.trim().length < 3 || skill.title.length > 120) {
      return 'Tên hiển thị phải từ 3 đến 120 ký tự.'
    }
    if (skill.goal.trim().length < 3 || skill.goal.length > 500) {
      return 'Mục tiêu kết quả cần đạt phải từ 3 đến 500 ký tự.'
    }
    const cleanProcedure = skill.procedure.filter((step) => step.trim().length > 0)
    if (cleanProcedure.length < 1 || cleanProcedure.length > 20) {
      return 'Quy trình phải có từ 1 đến 20 bước hợp lệ.'
    }
    if (skill.constraints.length > 20) {
      return 'Số lượng nguyên tắc ràng buộc tối đa là 20.'
    }
    return null
  }

  async function save() {
    setError('')
    const validationError = validateSkill(selected)
    if (validationError) {
      setError(validationError)
      return
    }

    setBusy(true)
    try {
      const payload = {
        skill: {
          name: selected.name,
          title: selected.title,
          description: selected.description,
          goal: selected.goal,
          procedure: selected.procedure.filter(Boolean),
          constraints: selected.constraints.filter(Boolean),
          preferred_capabilities: selected.preferred_capabilities,
          output_format: selected.output_format || 'markdown',
        },
        expected_revision: selected.revision || null,
      }
      const result = await api<{ data: Skill }>('/api/skills', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setSelected(result.data)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2500)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không lưu được skill.')
    } finally {
      setBusy(false)
    }
  }

  async function run() {
    setBusy(true)
    setRunning(true)
    setError('')
    setRunResult(null)
    try {
      const result = await api<{ data: SkillRunResult }>('/api/skills/run', {
        method: 'POST',
        body: JSON.stringify({ name: selected.name, inputs }),
      })
      setRunResult(result.data)
      setExpandedAccordions({
        goal: true,
        procedure: true,
        constraints: true,
        capabilities: true,
        output: true,
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không chạy được skill.')
    } finally {
      setBusy(false)
      setRunning(false)
    }
  }

  async function archive() {
    setBusy(true)
    setError('')
    try {
      await api('/api/skills/archive', {
        method: 'POST',
        body: JSON.stringify({ skill_id: selected.id }),
      })
      setSelected(emptySkill())
      setRunResult(null)
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không cất được skill.')
    } finally {
      setBusy(false)
    }
  }

  function addProcedureStep() {
    if (selected.procedure.length >= 20) return
    setSelected({ ...selected, procedure: [...selected.procedure, ''] })
  }

  function updateProcedureStep(index: number, val: string) {
    const updated = selected.procedure.map((step, i) => (i === index ? val : step))
    setSelected({ ...selected, procedure: updated })
  }

  function removeProcedureStep(index: number) {
    if (selected.procedure.length <= 1) {
      setSelected({ ...selected, procedure: [''] })
      return
    }
    const updated = selected.procedure.filter((_, i) => i !== index)
    setSelected({ ...selected, procedure: updated })
  }

  function addConstraint() {
    const trimmed = newConstraintDraft.trim()
    if (!trimmed) return
    if (selected.constraints.length >= 20) return
    if (selected.constraints.includes(trimmed)) {
      setNewConstraintDraft('')
      return
    }
    setSelected({
      ...selected,
      constraints: selected.constraints.concat(trimmed),
    })
    setNewConstraintDraft('')
  }

  function removeConstraint(index: number) {
    setSelected({
      ...selected,
      constraints: selected.constraints.filter((_, i) => i !== index),
    })
  }

  function toggleCapability(key: string) {
    const current = selected.preferred_capabilities || []
    const updated = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key]
    setSelected({ ...selected, preferred_capabilities: updated })
  }

  function toggleAccordion(key: string) {
    setExpandedAccordions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }))
  }

  function copyText(text: string, sectionKey: string) {
    void navigator.clipboard.writeText(text)
    setCopiedSection(sectionKey)
    setTimeout(() => {
      setCopiedSection(null)
    }, 2000)
  }

  function applyPreset(preset: Omit<Skill, 'id' | 'revision' | 'active'>) {
    setSelected({
      ...emptySkill(),
      ...preset,
    })
    setRunResult(null)
  }

  const placeholders = [
    ...new Set(
      [selected.goal, ...selected.procedure, ...selected.constraints, selected.output_format].flatMap((value) =>
        [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map((match) => match[1]!),
      ),
    ),
  ]

  const currentTheme = getSkillColorTheme(selected.name || 'default')
  const currentFormat = selected.output_format || 'markdown'
  const currentFormatMeta =
    OUTPUT_FORMAT_OPTIONS.find((opt) => opt.key === currentFormat) ?? {
      key: currentFormat,
      label: currentFormat || 'Tự do',
      desc: 'Định dạng tùy chỉnh',
    }

  return (
    <section className="stack-page skills-page">
      <header className="page-heading skills-page-heading">
        <div className="skills-heading-lockup">
          <p className="home-kicker">Reusable Skills Workbench</p>
          <div className="skills-heading-title-row">
            <h2>Dạy Agent cách bạn muốn làm việc</h2>
            <span className="skills-total-badge" title="Tổng số skill hiện có">
              {items.length} skills
            </span>
          </div>
          <p className="skills-heading-lead">
            Lưu mục tiêu, trình tự và nguyên tắc — không ghi lại cứng một chuỗi tool. Mỗi lần chạy sẽ lấy dữ liệu mới.
          </p>
        </div>
      </header>

      {error && <ErrorState message={error} />}

      <div className="artifact-workbench skills-workbench skills-layout">
        {/* Left Column: Skills List */}
        <aside className="artifact-list skills-list-pane">
          <div className="skills-list-header">
            <div className="skills-list-header__title-group">
              <span className="skills-list-caption">Skill đang dùng</span>
              <span className="skills-count-badge skills-count">{items.length} skills</span>
            </div>
            <Button
              appearance="primary"
              icon={<Add20Regular />}
              className="skills-add-button"
              onClick={() => {
                setSelected(emptySkill())
                setRunResult(null)
                setError('')
              }}
            >
              + Thêm skill
            </Button>
          </div>

          {loading ? (
            <LoadingState label="Đang tải danh sách kỹ năng…" />
          ) : items.length === 0 ? (
            <div className="skills-empty-state">
              <Sparkle20Regular className="skills-empty-icon" />
              <h4>Chưa có skill nào</h4>
              <p>Hãy bắt đầu bằng cách nạp một mẫu có sẵn hoặc bấm <strong>+ Thêm skill</strong>.</p>
              <div className="skills-preset-quick-list">
                <span className="skills-preset-label">Mẫu gợi ý:</span>
                {PRESET_TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.name}
                    type="button"
                    className="skills-preset-btn"
                    onClick={() => applyPreset(tmpl)}
                  >
                    <Sparkle20Regular /> {tmpl.title}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="skill-cards-container">
              {items.map((item) => {
                const itemTheme = getSkillColorTheme(item.name)
                const isSelected = selected.id === item.id || (!selected.id && selected.name === item.name)

                return (
                  <button
                    type="button"
                    key={item.id || item.name}
                    className={`skill-card ${isSelected ? 'skill-card--selected skill-card--active' : ''}`}
                    style={
                      {
                        '--skill-accent': itemTheme.accent,
                        '--skill-border': itemTheme.border,
                        '--skill-bg': itemTheme.bg,
                        '--skill-glow': itemTheme.glow,
                      } as React.CSSProperties
                    }
                    onClick={() => {
                      setSelected(item)
                      setRunResult(null)
                      setError('')
                    }}
                  >
                    <div className="skill-card__accent-bar" style={{ background: itemTheme.gradient }} />
                    <div className="skill-card__body">
                      <div className="skill-card__top">
                        <strong className="skill-card__title">{item.title || item.name}</strong>
                        <span
                          className={`skill-card__status-badge ${
                            item.active ? 'skill-card__status-badge--active' : 'skill-card__status-badge--inactive'
                          }`}
                        >
                          {item.active ? 'Hoạt động' : 'Tạm dừng'}
                        </span>
                      </div>

                      {item.description && (
                        <p className="skill-card__description" title={item.description}>
                          {item.description}
                        </p>
                      )}

                      <div className="skill-card__footer">
                        <span className="skill-card__step-badge" title="Số bước trong quy trình">
                          {item.procedure.length} bước
                        </span>
                        <span className="skill-card__version">
                          {item.name} · v{item.revision}
                        </span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </aside>

        {/* Right Column: Workbench Editor & Runner */}
        <div className="skills-editor-column">
          <form
            className="artifact-editor skills-editor-form"
            onSubmit={(event) => {
              event.preventDefault()
              void save()
            }}
          >
            {/* Header info strip */}
            <div className="skills-editor-banner" style={{ borderColor: currentTheme.border }}>
              <div className="skills-editor-banner__title-group">
                <div
                  className="skills-editor-avatar"
                  style={{ background: currentTheme.gradient, boxShadow: `0 0 16px ${currentTheme.glow}` }}
                >
                  <Sparkle20Regular />
                </div>
                <div>
                  <h3 className="skills-editor-headline">
                    {selected.title ? selected.title : selected.name ? selected.name : 'Tạo Skill Mới'}
                  </h3>
                  <span className="skills-editor-subline">
                    {selected.id ? `ID: ${selected.id} · Phiên bản v${selected.revision}` : 'Đang soạn thảo bản ghi mới'}
                  </span>
                </div>
              </div>

              {!selected.id && (
                <div className="skills-preset-bar">
                  <span className="skills-preset-bar__caption">Nạp nhanh mẫu:</span>
                  {PRESET_TEMPLATES.map((tmpl) => (
                    <button
                      key={tmpl.name}
                      type="button"
                      className="skills-preset-pill"
                      onClick={() => applyPreset(tmpl)}
                    >
                      {tmpl.title}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Core Identification */}
            <div className="skill-field-row">
              <div className="skills-input-group">
                <label className="artifact-label" htmlFor="skill-name">
                  Tên kỹ thuật <span className="skills-required-star">*</span>
                </label>
                <Input
                  id="skill-name"
                  disabled={Boolean(selected.id)}
                  value={selected.name}
                  placeholder="ví dụ: weekly_study_plan"
                  onChange={(_, d) =>
                    setSelected({
                      ...selected,
                      name: d.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
                    })
                  }
                />
                <small className="skills-field-hint">Chữ thường, số và gạch dưới (3–60 ký tự)</small>
              </div>

              <div className="skills-input-group">
                <label className="artifact-label" htmlFor="skill-title">
                  Tên dễ nhớ <span className="skills-required-star">*</span>
                </label>
                <Input
                  id="skill-title"
                  value={selected.title}
                  placeholder="ví dụ: Kế hoạch học tập tuần"
                  onChange={(_, d) => setSelected({ ...selected, title: d.value })}
                />
                <small className="skills-field-hint">Tên hiển thị trực quan (3–120 ký tự)</small>
              </div>
            </div>

            {/* Description */}
            <div className="skills-input-group">
              <label className="artifact-label" htmlFor="skill-description">
                Mô tả ngắn gọn
              </label>
              <Input
                id="skill-description"
                value={selected.description}
                placeholder="Tóm tắt ngắn gọn vai trò của kỹ năng này..."
                onChange={(_, d) => setSelected({ ...selected, description: d.value })}
              />
            </div>

            {/* Goal */}
            <div className="skills-input-group">
              <label className="artifact-label" htmlFor="skill-goal">
                Kết quả cần đạt (Goal) <span className="skills-required-star">*</span>
              </label>
              <Textarea
                id="skill-goal"
                rows={2}
                value={selected.goal}
                placeholder="Ví dụ: Tạo bảng kế hoạch học tập 7 ngày cho môn {subject}..."
                onChange={(_, d) => setSelected({ ...selected, goal: d.value })}
              />
              <small className="skills-field-hint">Dùng cú pháp {'{tên_biến}'} để tạo tham số đầu vào động</small>
            </div>

            {/* Procedure: Interactive Numbered Steps */}
            <div className="skills-editor-section">
              <div className="skills-section-header">
                <div className="skills-section-header__title">
                  <span className="skills-section-index">1</span>
                  <strong>Quy trình thực hiện (Procedure)</strong>
                  <span className="skills-count-pill">{selected.procedure.length} / 20 bước</span>
                </div>
                <small className="skills-section-desc">
                  Thứ tự các bước Agent sẽ thực thi. Kéo thả hoặc sắp xếp trực quan.
                </small>
              </div>

              <div className="procedure-steps-container">
                {selected.procedure.map((step, idx) => (
                  <div key={idx} className="procedure-step">
                    <span className="procedure-step__drag-handle drag-handle" title="Tay cầm kéo thả">
                      <ReOrderDotsVertical20Regular />
                    </span>
                    <span className="procedure-step__number">{idx + 1}</span>
                    <Input
                      className="procedure-step__input"
                      value={step}
                      placeholder={`Nội dung bước ${idx + 1}...`}
                      onChange={(_, d) => updateProcedureStep(idx, d.value)}
                    />
                    <Button
                      type="button"
                      appearance="subtle"
                      icon={<Dismiss16Regular />}
                      className="procedure-step__remove-btn"
                      title="Xóa bước này"
                      disabled={selected.procedure.length <= 1}
                      onClick={() => removeProcedureStep(idx)}
                    />
                  </div>
                ))}

                {selected.procedure.length < 20 && (
                  <Button
                    type="button"
                    appearance="subtle"
                    icon={<Add20Regular />}
                    className="procedure-add-step-btn"
                    onClick={addProcedureStep}
                  >
                    + Thêm bước tiếp theo
                  </Button>
                )}
              </div>
            </div>

            {/* Constraints: Interactive Tag Chips */}
            <div className="skills-editor-section">
              <div className="skills-section-header">
                <div className="skills-section-header__title">
                  <Tag20Regular />
                  <strong>Nguyên tắc & Ràng buộc (Constraints)</strong>
                  <span className="skills-count-pill">{selected.constraints.length} nguyên tắc</span>
                </div>
                <small className="skills-section-desc">
                  Ranh giới hoạt động giúp Agent không làm sai yêu cầu hoặc vi phạm an toàn.
                </small>
              </div>

              <div className="constraints-container">
                <div className="constraint-chips-list">
                  {selected.constraints.map((constraint, idx) => (
                    <span key={idx} className="constraint-chip">
                      <span className="constraint-chip__text">{constraint}</span>
                      <button
                        type="button"
                        className="constraint-chip__remove-btn"
                        title="Xóa nguyên tắc"
                        onClick={() => removeConstraint(idx)}
                      >
                        <Dismiss16Regular />
                      </button>
                    </span>
                  ))}
                  {selected.constraints.length === 0 && (
                    <span className="skills-empty-chip-note">Chưa thiết lập nguyên tắc nào.</span>
                  )}
                </div>

                {selected.constraints.length < 20 && (
                  <div className="constraint-add-row">
                    <Input
                      className="constraint-add-input"
                      placeholder="Gõ nguyên tắc mới rồi nhấn Enter hoặc Thêm..."
                      value={newConstraintDraft}
                      onChange={(_, d) => setNewConstraintDraft(d.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          addConstraint()
                        }
                      }}
                    />
                    <Button
                      type="button"
                      appearance="secondary"
                      icon={<Add20Regular />}
                      onClick={addConstraint}
                      disabled={!newConstraintDraft.trim()}
                    >
                      Thêm chip
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {/* Preferred Capabilities */}
            <div className="skills-editor-section">
              <div className="skills-section-header">
                <div className="skills-section-header__title">
                  <Cube20Regular />
                  <strong>Công cụ ưu tiên (Preferred Capabilities)</strong>
                  <span className="skills-count-pill">
                    {selected.preferred_capabilities?.length || 0} đã chọn
                  </span>
                </div>
                <small className="skills-section-desc">
                  Gợi ý công cụ thích hợp khi Agent giải quyết kỹ năng này.
                </small>
              </div>

              <div className="capabilities-grid">
                {CAPABILITY_CONFIGS.map((cap) => {
                  const IconComponent = cap.icon
                  const isSelected = selected.preferred_capabilities?.includes(cap.key)

                  return (
                    <button
                      key={cap.key}
                      type="button"
                      className={`capability-card ${isSelected ? 'capability-card--active' : ''}`}
                      style={{ '--cap-color': cap.badgeColor } as React.CSSProperties}
                      onClick={() => toggleCapability(cap.key)}
                      title={cap.desc}
                    >
                      <div className="capability-card__icon-box">
                        <IconComponent />
                      </div>
                      <div className="capability-card__info">
                        <span className="capability-card__label">{cap.label}</span>
                        <small className="capability-card__desc">{cap.desc}</small>
                      </div>
                      <div className="capability-card__check">
                        {isSelected ? <Checkmark16Regular /> : <span className="capability-card__dot" />}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Output Format Preview */}
            <div className="skills-editor-section">
              <div className="skills-section-header">
                <div className="skills-section-header__title">
                  <DocumentText20Regular />
                  <strong>Định dạng kết quả đầu ra (Output Format)</strong>
                  <span className="skills-output-preview-chip" title="Xem trước định dạng">
                    Định dạng: {currentFormatMeta.label}
                  </span>
                </div>
                <small className="skills-section-desc">
                  Chọn mẫu định dạng tiêu chuẩn hoặc điền định dạng mong muốn.
                </small>
              </div>

              <div className="output-format-selector">
                <div className="output-format-pills">
                  {OUTPUT_FORMAT_OPTIONS.map((opt) => {
                    const isPicked = (selected.output_format || 'markdown') === opt.key
                    return (
                      <button
                        key={opt.key}
                        type="button"
                        className={`output-format-pill ${isPicked ? 'output-format-pill--active' : ''}`}
                        onClick={() => setSelected({ ...selected, output_format: opt.key })}
                      >
                        <span className="output-format-pill__name">{opt.label}</span>
                        <small className="output-format-pill__desc">{opt.desc}</small>
                      </button>
                    )
                  })}
                </div>

                <div className="output-format-custom-row">
                  <label htmlFor="skill-output-custom" className="artifact-label">
                    Tùy chỉnh định dạng:
                  </label>
                  <Input
                    id="skill-output-custom"
                    value={selected.output_format ?? 'markdown'}
                    placeholder="markdown, table, json, checklist..."
                    onChange={(_, d) => setSelected({ ...selected, output_format: d.value })}
                  />
                </div>
              </div>
            </div>

            {/* Primary Actions */}
            <div className="artifact-actions skills-actions-bar">
              <Button
                type="submit"
                appearance="primary"
                disabled={busy}
                icon={saveSuccess ? <Checkmark20Regular /> : <Save20Regular />}
                className={`skills-save-btn ${saveSuccess ? 'skills-save-btn--success' : ''}`}
              >
                {saveSuccess ? 'Đã lưu thành công!' : 'Lưu skill'}
              </Button>

              {selected.id && (
                <Button
                  type="button"
                  icon={<Archive20Regular />}
                  disabled={busy}
                  className="skills-archive-btn"
                  onClick={() => void archive()}
                >
                  Cất skill
                </Button>
              )}
            </div>
          </form>

          {/* Test Runner Workbench Section */}
          {selected.id && (
            <section className="skill-runner skills-runner-panel">
              <div className="skills-runner-header">
                <div>
                  <h3 className="skills-runner-title">Chạy thử procedure</h3>
                  <p className="skills-runner-lead">
                    Điền thông tin của lần làm việc này. Agent sẽ áp dụng biến vào quy trình mà không nạp lại dữ liệu cũ.
                  </p>
                </div>
              </div>

              {placeholders.length > 0 ? (
                <div className="skills-placeholders-grid">
                  {placeholders.map((name) => (
                    <div key={name} className="skills-placeholder-item">
                      <label className="artifact-label" htmlFor={`skill-input-${name}`}>
                        {'{' + name + '}'} <span className="skills-required-star">*</span>
                      </label>
                      <Input
                        id={`skill-input-${name}`}
                        value={inputs[name] ?? ''}
                        placeholder={`Nhập giá trị cho ${name}...`}
                        onChange={(_, d) => setInputs({ ...inputs, [name]: d.value })}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="skills-no-placeholders-text">
                  Kỹ năng này không chứa placeholder dạng {'{tên_biến}'}. Bạn có thể bấm Nạp procedure trực tiếp.
                </p>
              )}

              <div className="skills-runner-actions">
                <Button
                  appearance="primary"
                  icon={running ? <Spinner size="tiny" /> : <Play20Regular />}
                  disabled={busy || running || placeholders.some((name) => !inputs[name]?.trim())}
                  onClick={() => void run()}
                  className="skills-run-button"
                >
                  {running ? 'Đang nạp procedure…' : 'Nạp procedure'}
                </Button>
              </div>

              {/* Accordion Run Result Panel */}
              {runResult && (
                <div className="skill-run-result run-result-panel">
                  <div className="run-result-header">
                    <div className="run-result-header__title">
                      <Sparkle20Regular />
                      <strong>Kết quả nạp Procedure thành công</strong>
                    </div>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={copiedSection === 'all' ? <Checkmark16Regular /> : <Copy20Regular />}
                      onClick={() => {
                        const fullText = [
                          `Mục tiêu: ${runResult.goal}`,
                          `Quy trình:\n${runResult.procedure.map((s, i) => `${i + 1}. ${s}`).join('\n')}`,
                          `Nguyên tắc:\n${runResult.constraints.map((c) => `- ${c}`).join('\n')}`,
                          `Định dạng đầu ra: ${runResult.output_format}`,
                        ].join('\n\n')
                        copyText(fullText, 'all')
                      }}
                    >
                      {copiedSection === 'all' ? 'Đã sao chép' : 'Sao chép toàn bộ'}
                    </Button>
                  </div>

                  {/* Accordion: Goal */}
                  <div className="run-result-accordion">
                    <div
                      className="run-result-accordion__header"
                      onClick={() => toggleAccordion('goal')}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="run-result-accordion__title">Mục tiêu (Goal)</span>
                      <div className="run-result-accordion__tools" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="run-result-accordion__copy-btn"
                          title="Sao chép mục tiêu"
                          onClick={() => copyText(runResult.goal, 'goal')}
                        >
                          {copiedSection === 'goal' ? <Checkmark16Regular /> : <Copy20Regular />}
                        </button>
                        <span className="run-result-accordion__chevron">
                          {expandedAccordions.goal ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                        </span>
                      </div>
                    </div>
                    {expandedAccordions.goal && (
                      <div className="run-result-accordion__content">
                        <p>{runResult.goal}</p>
                      </div>
                    )}
                  </div>

                  {/* Accordion: Procedure */}
                  <div className="run-result-accordion">
                    <div
                      className="run-result-accordion__header"
                      onClick={() => toggleAccordion('procedure')}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="run-result-accordion__title">
                        Các bước sẽ thực thi ({runResult.procedure.length})
                      </span>
                      <div className="run-result-accordion__tools" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="run-result-accordion__copy-btn"
                          title="Sao chép danh sách bước"
                          onClick={() =>
                            copyText(
                              runResult.procedure.map((s, i) => `${i + 1}. ${s}`).join('\n'),
                              'procedure',
                            )
                          }
                        >
                          {copiedSection === 'procedure' ? <Checkmark16Regular /> : <Copy20Regular />}
                        </button>
                        <span className="run-result-accordion__chevron">
                          {expandedAccordions.procedure ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                        </span>
                      </div>
                    </div>
                    {expandedAccordions.procedure && (
                      <div className="run-result-accordion__content">
                        <ol className="run-result-steps-list">
                          {runResult.procedure.map((step, index) => (
                            <li key={index}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>

                  {/* Accordion: Constraints */}
                  {runResult.constraints.length > 0 && (
                    <div className="run-result-accordion">
                      <div
                        className="run-result-accordion__header"
                        onClick={() => toggleAccordion('constraints')}
                        role="button"
                        tabIndex={0}
                      >
                        <span className="run-result-accordion__title">
                          Nguyên tắc áp dụng ({runResult.constraints.length})
                        </span>
                        <div className="run-result-accordion__tools" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="run-result-accordion__copy-btn"
                            title="Sao chép nguyên tắc"
                            onClick={() => copyText(runResult.constraints.join('\n'), 'constraints')}
                          >
                            {copiedSection === 'constraints' ? <Checkmark16Regular /> : <Copy20Regular />}
                          </button>
                          <span className="run-result-accordion__chevron">
                            {expandedAccordions.constraints ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                          </span>
                        </div>
                      </div>
                      {expandedAccordions.constraints && (
                        <div className="run-result-accordion__content">
                          <ul className="run-result-constraints-list">
                            {runResult.constraints.map((c, i) => (
                              <li key={i}>{c}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Accordion: Output format */}
                  <div className="run-result-accordion">
                    <div
                      className="run-result-accordion__header"
                      onClick={() => toggleAccordion('output')}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="run-result-accordion__title">Định dạng đầu ra</span>
                      <div className="run-result-accordion__tools" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="run-result-accordion__copy-btn"
                          title="Sao chép định dạng"
                          onClick={() => copyText(runResult.output_format, 'output')}
                        >
                          {copiedSection === 'output' ? <Checkmark16Regular /> : <Copy20Regular />}
                        </button>
                        <span className="run-result-accordion__chevron">
                          {expandedAccordions.output ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                        </span>
                      </div>
                    </div>
                    {expandedAccordions.output && (
                      <div className="run-result-accordion__content">
                        <span className="run-result-format-badge">{runResult.output_format}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </section>
  )
}
