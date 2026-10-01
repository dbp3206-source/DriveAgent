export type ChatControls = {
  source: 'auto' | 'drive' | 'rag' | 'gmail' | 'local' | 'memory' | 'general'
  agent: 'auto' | 'research' | 'communication' | 'study' | 'workspace'
  output: 'chat' | 'document' | 'spreadsheet'
  workflow: 'auto' | 'source_summary' | 'email_digest' | 'meeting_notes' | 'study_plan' | 'budget_tracker' | 'compare_sources'
  skill_name?: string
}

export const DEFAULT_CHAT_CONTROLS: ChatControls = {
  source: 'auto',
  agent: 'auto',
  output: 'chat',
  workflow: 'auto',
}

export type SlashOption = {
  id: string
  command: string
  group: 'Nguồn' | 'Agent' | 'Quy trình' | 'Đầu ra' | 'Skill của bạn'
  label: string
  description: string
  patch: Partial<ChatControls>
}

const builtInOptions: SlashOption[] = [
  {id: 'source-auto', command: '/auto', group: 'Nguồn', label: 'Tự chọn nguồn', description: 'Agent tự quyết định tool cần dùng.', patch: {source: 'auto'}},
  {id: 'source-drive', command: '/drive', group: 'Nguồn', label: 'Google Drive', description: 'Chỉ tìm và đọc tệp trực tiếp trong Drive.', patch: {source: 'drive', agent: 'research'}},
  {id: 'source-rag', command: '/rag', group: 'Nguồn', label: 'Kho tri thức RAG', description: 'Chỉ dùng các tài liệu đã lập chỉ mục.', patch: {source: 'rag', agent: 'research'}},
  {id: 'source-gmail', command: '/gmail', group: 'Nguồn', label: 'Gmail', description: 'Chỉ dùng email của tài khoản đang kết nối.', patch: {source: 'gmail', agent: 'communication'}},
  {id: 'source-local', command: '/local', group: 'Nguồn', label: 'Tài liệu trên máy', description: 'Chỉ dùng nguồn đã import từ máy này.', patch: {source: 'local', agent: 'research'}},
  {id: 'source-memory', command: '/memory', group: 'Nguồn', label: 'Bộ nhớ cá nhân', description: 'Chỉ tra thông tin bạn đã cho phép lưu.', patch: {source: 'memory', agent: 'study'}},
  {id: 'source-general', command: '/general', group: 'Nguồn', label: 'Không dùng dữ liệu riêng', description: 'Trả lời mà không mở Drive, Gmail, RAG hay Memory.', patch: {source: 'general'}},
  {id: 'agent-research', command: '/research', group: 'Agent', label: 'Research Agent', description: 'Tìm, đọc, đối chiếu và dẫn nguồn.', patch: {agent: 'research', output: 'chat'}},
  {id: 'agent-communication', command: '/communication', group: 'Agent', label: 'Communication Agent', description: 'Tóm tắt và chuẩn bị giao tiếp qua Gmail.', patch: {agent: 'communication', source: 'gmail', output: 'chat'}},
  {id: 'agent-study', command: '/study', group: 'Agent', label: 'Study Agent', description: 'Giải thích, tính toán và hỗ trợ học tập.', patch: {agent: 'study', output: 'chat'}},
  {id: 'agent-workspace', command: '/workspace', group: 'Agent', label: 'Workspace Agent', description: 'Chuẩn bị Docs hoặc Sheets có bước duyệt.', patch: {agent: 'workspace'}},
  {id: 'flow-summary', command: '/summary', group: 'Quy trình', label: 'Tóm tắt có nguồn', description: 'Tách kết luận, bằng chứng và bước tiếp theo.', patch: {workflow: 'source_summary'}},
  {id: 'flow-inbox', command: '/inbox', group: 'Quy trình', label: 'Tổng hợp hộp thư', description: 'Ưu tiên email và nêu hành động cần làm.', patch: {workflow: 'email_digest', source: 'gmail', agent: 'communication'}},
  {id: 'flow-meeting', command: '/meeting', group: 'Quy trình', label: 'Biên bản cuộc họp', description: 'Quyết định, đầu việc, người phụ trách và hạn.', patch: {workflow: 'meeting_notes'}},
  {id: 'flow-study', command: '/study-plan', group: 'Quy trình', label: 'Lộ trình học', description: 'Mục tiêu, thực hành và cách tự kiểm tra.', patch: {workflow: 'study_plan', agent: 'study', source: 'auto'}},
  // The reviewed budget flow is intentionally local/deterministic.  Selecting
  // it must not fall through to a model-authored workbook where formulas can
  // drift (for example, a SUM range that omits the last row).
  {id: 'flow-budget', command: '/budget', group: 'Quy trình', label: 'Theo dõi ngân sách', description: 'Dữ liệu có công thức và kiểm tra tổng.', patch: {workflow: 'budget_tracker', output: 'spreadsheet', agent: 'workspace', source: 'general'}},
  {id: 'flow-compare', command: '/compare', group: 'Quy trình', label: 'So sánh nguồn', description: 'Đối chiếu theo tiêu chí nhất quán.', patch: {workflow: 'compare_sources', agent: 'research'}},
  {id: 'output-chat', command: '/chat', group: 'Đầu ra', label: 'Trả lời trong chat', description: 'Trình bày đầy đủ ngay trong cuộc trò chuyện.', patch: {output: 'chat'}},
  {id: 'output-document', command: '/doc', group: 'Đầu ra', label: 'Google Docs', description: 'Chuẩn bị bản Docs và chờ bạn duyệt; giữ nguồn bạn đã chọn.', patch: {output: 'document', agent: 'workspace'}},
  {id: 'output-spreadsheet', command: '/sheet', group: 'Đầu ra', label: 'Google Sheets', description: 'Chuẩn bị bảng tính và chờ bạn duyệt; giữ nguồn bạn đã chọn.', patch: {output: 'spreadsheet', agent: 'workspace'}},
]

export function slashOptions(skills: Array<{name: string; title: string}>): SlashOption[] {
  return [
    ...builtInOptions,
    ...skills.map(skill => ({
      id: `skill-${skill.name}`,
      command: `/skill:${skill.name}`,
      group: 'Skill của bạn' as const,
      label: skill.title,
      description: `Dùng quy trình đã lưu: ${skill.name}`,
      patch: {skill_name: skill.name},
    })),
  ]
}

export function filterSlashOptions(options: SlashOption[], query: string): SlashOption[] {
  const needle = query.trim().toLocaleLowerCase('vi')
  if (!needle) return options
  return options.filter(option =>
    `${option.command} ${option.label} ${option.description}`.toLocaleLowerCase('vi').includes(needle)
  )
}

const legacyLeadingCommand = /^\/(?:auto|drive|rag|gmail|local|memory|general|research|communication|study|workspace|summary|inbox|meeting|study-plan|budget|compare|chat|doc|sheet|skill:[^\s]+)(?=\s|$)\s*/i

/** Hide recognized legacy slash prefixes without changing stored conversation data. */
export function displaySessionTitle(title: string): string {
  let visible = title.trim()
  while (legacyLeadingCommand.test(visible)) {
    visible = visible.replace(legacyLeadingCommand, '').trimStart()
  }
  return visible || title.trim()
}

const sourceAgent: Partial<Record<ChatControls['source'], ChatControls['agent']>> = {
  drive: 'research',
  rag: 'research',
  local: 'research',
  gmail: 'communication',
  memory: 'study',
}

/** Merge a command as a compatible intent patch, not an independent field spread. */
export function mergeChatControls(current: ChatControls, patch: Partial<ChatControls>): ChatControls {
  const nextPatch = {...patch}
  if (patch.skill_name) {
    const names = [...new Set([...(current.skill_name?.split('+') ?? []), patch.skill_name])].slice(0, 4)
    nextPatch.skill_name = names.join('+')
  }
  const next: ChatControls = {...current, ...nextPatch}
  const requestedAgent = patch.agent
  const requestedSource = patch.source

  if (requestedSource && requestedSource !== 'auto') {
    const compatible = sourceAgent[requestedSource]
    if (compatible && next.agent !== 'workspace' && next.agent !== 'auto' && next.agent !== compatible) {
      next.agent = compatible
    } else if (compatible && next.agent === 'auto') {
      next.agent = compatible
    }
  }

  if (requestedAgent && requestedAgent !== 'auto' && requestedAgent !== 'workspace') {
    const compatible = sourceAgent[next.source]
    if (compatible && compatible !== requestedAgent) next.source = 'auto'
  }

  // A writer output is compatible with a selected read source. Never silently
  // erase the user's scope just because they chose Docs or Sheets.
  if ((next.output === 'document' || next.output === 'spreadsheet') && next.agent === 'auto') {
    next.agent = 'workspace'
  }
  return next
}
