export type DocumentParagraphBlock = {
  kind: 'paragraph'
  text: string
  style: 'NORMAL_TEXT' | 'HEADING_1' | 'HEADING_2' | 'HEADING_3'
  list_style: 'none' | 'bullet' | 'numbered'
}

export type DocumentTableBlock = {
  kind: 'table'
  rows: string[][]
}

export type DocumentBlock = DocumentParagraphBlock | DocumentTableBlock

export function markdownToDocumentBlocks(markdown: string): DocumentBlock[]
