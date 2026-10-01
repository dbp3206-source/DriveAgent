import assert from 'node:assert/strict'
import test from 'node:test'
import { markdownToDocumentBlocks } from './documentMarkdown.js'

test('retains markdown headings, paragraphs and lists as typed blocks', () => {
  assert.deepEqual(markdownToDocumentBlocks(
    '# Kế hoạch\n\nBắt đầu từ nguồn [hướng dẫn](https://example.test).\n\n- Đọc tài liệu\n1. Kiểm tra số liệu',
  ), [
    {kind: 'paragraph', text: 'Kế hoạch', style: 'HEADING_1', list_style: 'none'},
    {kind: 'paragraph', text: 'Bắt đầu từ nguồn hướng dẫn.', style: 'NORMAL_TEXT', list_style: 'none'},
    {kind: 'paragraph', text: 'Đọc tài liệu', style: 'NORMAL_TEXT', list_style: 'bullet'},
    {kind: 'paragraph', text: 'Kiểm tra số liệu', style: 'NORMAL_TEXT', list_style: 'numbered'},
  ])
})

test('turns GFM tables into rectangular native-table proposals', () => {
  assert.deepEqual(markdownToDocumentBlocks(
    '## So sánh\n\n| Tiêu chí | Phương án A | Phương án B |\n|:---|:---:|---:|\n| Chi phí | **Thấp** | Cao |\n| Link | [Nguồn 1](https://example.test) | Nguồn 2 |\n\nKết luận.',
  ), [
    {kind: 'paragraph', text: 'So sánh', style: 'HEADING_2', list_style: 'none'},
    {kind: 'table', rows: [
      ['Tiêu chí', 'Phương án A', 'Phương án B'],
      ['Chi phí', 'Thấp', 'Cao'],
      ['Link', 'Nguồn 1', 'Nguồn 2'],
    ]},
    {kind: 'paragraph', text: 'Kết luận.', style: 'NORMAL_TEXT', list_style: 'none'},
  ])
})

test('preserves escaped and inline-code pipes without changing table shape', () => {
  const blocks = markdownToDocumentBlocks(
    '| Ký hiệu | Mã |\n| --- | --- |\n| A \\| B | `left|right` |',
  )
  assert.deepEqual(blocks, [
    {kind: 'table', rows: [['Ký hiệu', 'Mã'], ['A | B', 'left|right']]},
  ])
})

test('keeps a ragged row as readable text rather than silently dropping cells', () => {
  const blocks = markdownToDocumentBlocks(
    '| A | B |\n| --- | --- |\n| one | two |\n| extra | cells | here |',
  )
  assert.deepEqual(blocks, [
    {kind: 'table', rows: [['A', 'B'], ['one', 'two']]},
    {kind: 'paragraph', text: 'extra | cells | here', style: 'NORMAL_TEXT', list_style: 'none'},
  ])
})
