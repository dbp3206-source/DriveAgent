import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeMathNotation } from './markdownPresentation.mjs'

test('renders a standalone subtraction symbol without TeX delimiters', () => {
  assert.equal(normalizeMathNotation('150 giờ $-$ 37,5 giờ = 112,5 giờ.'), '150 giờ - 37,5 giờ = 112,5 giờ.')
  assert.equal(normalizeMathNotation('Ngân sách $50 và $20.'), 'Ngân sách $50 và $20.')
})

test('normalizes common inline math into readable text', () => {
  assert.equal(
    normalizeMathNotation('`3` $\\times$ `45` = `135` phút; $\\frac{1}{2}$; \\(x \\geq 2\\)'),
    '`3` × `45` = `135` phút; 1/2; x ≥ 2',
  )
})

test('does not alter ordinary currency or prose dollars', () => {
  assert.equal(normalizeMathNotation('Ngân sách là $50 và còn $20.'), 'Ngân sách là $50 và còn $20.')
})

test('preserves numerator and denominator precedence when flattening fractions', () => {
  assert.equal(normalizeMathNotation('\\frac{5.1 - 3.1}{3.1}'), '(5.1 - 3.1)/3.1')
  assert.equal(normalizeMathNotation('\\frac{1}{x + 2}'), '1/(x + 2)')
})

test('hides technical UUID citation markers from human-facing previews', () => {
  assert.equal(normalizeMathNotation('Đã kiểm tra [78d7283b-5fe9-408c-9abe-5ec950c4510f].'), 'Đã kiểm tra [nguồn].')
})
