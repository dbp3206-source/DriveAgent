const PARAGRAPH_STYLE = 'NORMAL_TEXT'

function cleanInlineMarkdown(value) {
  return value
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, (_, alt) => (alt ? `[Hình: ${alt}]` : '[Hình]'))
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/~~(.*?)~~/g, '$1')
    .replace(/[*_`]/g, '')
    .trim()
}

function splitTableRow(line) {
  let source = line.trim()
  if (source.startsWith('|')) source = source.slice(1)
  if (source.endsWith('|')) source = source.slice(0, -1)

  const cells = []
  let cell = ''
  let inCode = false
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index]
    if (char === '\\' && source[index + 1] === '|') {
      cell += '|'
      index += 1
    } else if (char === '`') {
      inCode = !inCode
      cell += char
    } else if (char === '|' && !inCode) {
      cells.push(cleanInlineMarkdown(cell))
      cell = ''
    } else {
      cell += char
    }
  }
  cells.push(cleanInlineMarkdown(cell))
  return cells
}

function parseTable(lines, start) {
  if (start + 1 >= lines.length || !lines[start].includes('|')) return null
  const headers = splitTableRow(lines[start])
  const separators = splitTableRow(lines[start + 1])
  const isSeparator = separators.length === headers.length
    && separators.every((cell) => /^:?-{3,}:?$/.test(cell))
  if (!headers.length || !isSeparator) return null

  const rows = [headers]
  let next = start + 2
  while (next < lines.length && lines[next].trim() && lines[next].includes('|')) {
    const row = splitTableRow(lines[next])
    if (row.length !== headers.length) {
      return {block: {kind: 'table', rows}, next: next + 1, looseText: row.join(' | ')}
    }
    rows.push(row)
    next += 1
  }
  return {block: {kind: 'table', rows}, next, looseText: null}
}

function paragraph(text, style = PARAGRAPH_STYLE, listStyle = 'none') {
  return {kind: 'paragraph', text: cleanInlineMarkdown(text), style, list_style: listStyle}
}

export function markdownToDocumentBlocks(markdown) {
  const lines = markdown.split(/\r?\n/)
  const blocks = []
  let pendingParagraph = []
  const flush = () => {
    const text = pendingParagraph.join(' ').replace(/\s+/g, ' ').trim()
    if (text) blocks.push(paragraph(text))
    pendingParagraph = []
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim()
    if (!line) {
      flush()
      continue
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      flush()
      blocks.push(paragraph(heading[2], `HEADING_${heading[1].length}`))
      continue
    }
    const table = parseTable(lines, index)
    if (table) {
      flush()
      blocks.push(table.block)
      if (table.looseText) blocks.push(paragraph(table.looseText))
      index = table.next - 1
      continue
    }
    const bullet = line.match(/^[-*+•]\s+(.+)$/)
    if (bullet) {
      flush()
      blocks.push(paragraph(bullet[1], PARAGRAPH_STYLE, 'bullet'))
      continue
    }
    const numbered = line.match(/^\d+[.)]\s+(.+)$/)
    if (numbered) {
      flush()
      blocks.push(paragraph(numbered[1], PARAGRAPH_STYLE, 'numbered'))
      continue
    }
    pendingParagraph.push(line)
  }
  flush()
  return blocks.length ? blocks : [paragraph('Chưa có nội dung để xuất.')]
}
