const MATH_COMMANDS = [
  [/\\times\b/g, '×'],
  [/\\cdot\b/g, '·'],
  [/\\div\b/g, '÷'],
  [/\\pm\b/g, '±'],
  [/\\leq?\b/g, '≤'],
  [/\\geq?\b/g, '≥'],
  [/\\neq\b/g, '≠'],
  [/\\to\b/g, '→'],
  [/\\rightarrow\b/g, '→'],
  [/\\left\b|\\right\b/g, ''],
]

function replaceFraction(_match, numerator, denominator) {
  const group = value => /[+*/^−-]|\\(?:times|cdot|div)\b/.test(value) ? `(${value})` : value
  return `${group(numerator)}/${group(denominator)}`
}

/**
 * Keep model-authored math readable when no TeX renderer is enabled.
 * This is deliberately a conservative presentation fallback: it changes only
 * common inline delimiters and symbols, never executes or interprets TeX.
 */
export function normalizeMathNotation(content) {
  if (!content) return ''
  let normalized = content
    .replace(/\\\(([^\n]*?)\\\)/g, '$1')
    .replace(/\\\[([^\n]*?)\\\]/g, '$1')
    .replace(/\$\$([^\n]*?)\$\$/g, '$1')
    .replace(/\$(?=[^$\n]*(?:\\[A-Za-z]+|[=+*/^×÷±≤≥]))([^$\n]+)\$/g, '$1')
    .replace(/\[[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\]/gi, '[nguồn]')
    .replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, replaceFraction)
    .replace(/\\text\{([^{}]*)\}/g, '$1')
  for (const [pattern, replacement] of MATH_COMMANDS) {
    normalized = normalized.replace(pattern, replacement)
  }
  return normalized
}
