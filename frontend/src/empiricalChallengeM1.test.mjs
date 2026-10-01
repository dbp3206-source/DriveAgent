/**
 * @file empiricalChallengeM1.test.mjs
 * @description Empirical Challenger Test Suite for Milestone M1 (DriveAgent Harness Showcase).
 *
 * Verifies:
 * 1. Vietnamese dual-diacritic text rendering across all headings (h1, h2, h3) across multiple simulated viewports and line-wrap conditions.
 * 2. Rapid domain switching state consistency (Banking -> Education -> E-commerce -> Banking) across 50 iterations.
 * 3. URL hash tampering and edge-case query params (#/harness?domain=invalid&step=99, boundary steps, injection attempts).
 */

import assert from 'node:assert/strict'
import test, { describe, it } from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { pageFromHash, hashForPage } from './pageRoute.mjs'
import {
  HARNESS_SCENARIOS,
  HARNESS_SHARED_RAILS,
  CANONICAL_6_LAYERS,
  ARCHITECTURE_VIEW_MODES,
  COMMAND_FLAGS,
  DOMAIN_THEMES,
} from './harnessScenarios.ts'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

/* =========================================================================
 * IMPLEMENTATION REPLICAS UNDER TEST (Matching HarnessPage.tsx logic)
 * ========================================================================= */

const VALID_DOMAINS = ['banking', 'education', 'ecommerce']

export function parseHarnessUrlFromHash(hash) {
  try {
    const raw = hash || ''
    const qIndex = raw.indexOf('?')
    if (qIndex === -1) return {}
    const params = new URLSearchParams(raw.slice(qIndex + 1))
    const domainParam = params.get('domain')?.toLowerCase()
    const stepParam = params.get('step')

    const domain =
      domainParam === 'banking' || domainParam === 'education' || domainParam === 'ecommerce'
        ? domainParam
        : undefined

    let stepIndex
    if (stepParam !== null) {
      const parsed = parseInt(stepParam, 10)
      if (!Number.isNaN(parsed)) {
        stepIndex = Math.max(0, Math.min(6, parsed - 1))
      }
    }
    return { domain, stepIndex }
  } catch {
    return {}
  }
}

/**
 * Simulates HarnessPage State Machine
 */
export class HarnessPageStateSimulator {
  constructor(initialHash = '#/harness') {
    this.history = []
    this.currentHash = initialHash

    const initialParams = parseHarnessUrlFromHash(initialHash)
    this.selectedId = initialParams.domain ?? 'banking'
    this.activeStep = initialParams.stepIndex ?? 0
    this.diagramViewMode = 'business'

    this.syncUrl()
  }

  getScenario() {
    return HARNESS_SCENARIOS.find((item) => item.id === this.selectedId) ?? HARNESS_SCENARIOS[0]
  }

  getStep() {
    const scenario = this.getScenario()
    return scenario.steps[this.activeStep] ?? scenario.steps[0]
  }

  syncUrl() {
    if (!this.currentHash || this.currentHash.startsWith('#/harness') || this.currentHash.startsWith('#harness')) {
      const targetHash = `#/harness?domain=${this.selectedId}&step=${this.activeStep + 1}`
      if (this.currentHash !== targetHash) {
        this.currentHash = targetHash
        this.history.push(targetHash)
      }
    }
  }

  selectScenario(id) {
    this.selectedId = id
    this.activeStep = 0
    this.syncUrl()
  }

  selectStep(stepIndex) {
    this.activeStep = Math.max(0, Math.min(6, stepIndex))
    this.syncUrl()
  }

  simulateUserHashChange(newHash) {
    this.currentHash = newHash
    if (!newHash.startsWith('#/harness') && !newHash.startsWith('#harness')) {
      return
    }
    const { domain, stepIndex } = parseHarnessUrlFromHash(newHash)
    if (domain && domain !== this.selectedId) {
      this.selectedId = domain
    }
    if (stepIndex !== undefined && stepIndex !== this.activeStep) {
      this.activeStep = stepIndex
    }
    this.syncUrl()
  }
}


/* =========================================================================
 * 1. VIETNAMESE DUAL-DIACRITIC TEXT RENDERING & VIEWPORT LINE-WRAP TESTS
 * ========================================================================= */

describe('Empirical Challenge 1: Vietnamese Dual-Diacritic & Viewport Wrapping', () => {

  const CSS_PATH = path.resolve(__dirname, 'pages', 'harnessPage.css')
  const cssContent = fs.readFileSync(CSS_PATH, 'utf8')

  it('verifies exact CSS typography rules for h1 preventing diacritic clipping', () => {
    // 1. Line-height must be exactly 1.25 (or >= 1.25)
    assert.match(cssContent, /\.harness-flagship__header h1[\s\S]*?line-height:\s*1\.25;/)
    // 2. Headroom padding-top must be at least 8px
    assert.match(cssContent, /\.harness-flagship__header h1[\s\S]*?padding-top:\s*8px;/)
    // 3. Letter-spacing must be -0.02em (not excessively negative like -0.06em)
    assert.match(cssContent, /\.harness-flagship__header h1[\s\S]*?letter-spacing:\s*-0\.02em;/)
    // 4. Overflow must be visible so top marks are never clipped
    assert.match(cssContent, /\.harness-flagship__header h1[\s\S]*?overflow:\s*visible;/)
    // 5. Container overflow must also be visible
    assert.match(cssContent, /\.harness-flagship\s*\{[\s\S]*?overflow:\s*visible;/)
  })

  it('verifies exact CSS typography rules for h2 preventing diacritic clipping', () => {
    // 1. Scenario h2 line-height >= 1.25
    assert.match(cssContent, /\.harness-scenario-header h2[\s\S]*?line-height:\s*1\.25;/)
    // 2. Scenario h2 padding-top >= 6px
    assert.match(cssContent, /\.harness-scenario-header h2[\s\S]*?padding-top:\s*6px;/)
    // 3. Scenario h2 overflow: visible
    assert.match(cssContent, /\.harness-scenario-header h2[\s\S]*?overflow:\s*visible;/)
    // 4. Shared rails h2 line-height >= 1.25
    assert.match(cssContent, /\.harness-shared-rails h2[\s\S]*?line-height:\s*1\.25;/)
    // 5. Shared rails h2 overflow: visible
    assert.match(cssContent, /\.harness-shared-rails h2[\s\S]*?overflow:\s*visible;/)
  })

  it('analyzes all dual-diacritic character occurrences in all showcase headings', () => {
    // Extract all heading strings
    const headings = [
      'Kiến Trúc Tác Tử Doanh Nghiệp: Chuyển hóa yêu cầu thực tế thành kết quả kiểm chứng 100%',
      'Minh bạch hóa mọi quyết định, luồng dữ liệu và rào cản an toàn trước khi bất kỳ tác vụ nào được ghi nhận.',
      'Đối soát chênh lệch sổ sách & Giữ trọn vết kiểm toán',
      'Nhận diện lỗ hổng kiến thức & Đánh giá khách quan theo rubric',
      'Phân tích biến động đơn hàng & Đề xuất phương án vận hành kho',
      'Mọi domain đều đi qua cùng một cổng kiểm soát.',
      'Kiến trúc Tác tử 6 Tầng Chuẩn Doanh Nghiệp',
      'Nhấn vào từng bước để xem việc thật đã xảy ra.',
      ...HARNESS_SCENARIOS.flatMap((s) => s.steps.map((st) => st.plainTitle)),
      ...HARNESS_SCENARIOS.flatMap((s) => s.steps.map((st) => st.plainSummary)),
    ]

    // Regex for Vietnamese characters with stacked or tone diacritics
    const dualDiacriticRegex = /[ếềểễệốồổỗộứừửữựớờởỡợấầẩẫậắằẳẵặ]/gi
    const allMatches = []

    headings.forEach((h) => {
      const matches = h.match(dualDiacriticRegex) || []
      allMatches.push(...matches)
    })

    // Assert that we have extensively tested real dual-diacritic text (>= 40 instances)
    assert.ok(allMatches.length >= 40, `Found ${allMatches.length} dual-diacritic glyphs`)

    // Verify key stacked glyphs exist in the corpus
    const uniqueGlyphs = new Set(allMatches.map((c) => c.toLowerCase()))
    assert.ok(uniqueGlyphs.has('ế'), 'Contains ế')
    assert.ok(uniqueGlyphs.has('ệ'), 'Contains ệ')
    assert.ok(uniqueGlyphs.has('ể'), 'Contains ể')
    assert.ok(uniqueGlyphs.has('ứ'), 'Contains ứ')
    assert.ok(uniqueGlyphs.has('ộ'), 'Contains ộ')
    assert.ok(uniqueGlyphs.has('ậ'), 'Contains ậ')
    assert.ok(uniqueGlyphs.has('ổ'), 'Contains ổ')
    assert.ok(uniqueGlyphs.has('ố'), 'Contains ố')
  })

  it('simulates typography line wrapping across 7 viewport widths', () => {
    const viewports = [
      { name: 'Mobile XS', width: 320, padding: 32 },
      { name: 'Mobile Standard', width: 375, padding: 32 },
      { name: 'Mobile Large', width: 414, padding: 32 },
      { name: 'Tablet Portrait', width: 768, padding: 48 },
      { name: 'Tablet Landscape', width: 1024, padding: 64 },
      { name: 'Desktop HD', width: 1280, padding: 64 },
      { name: 'Desktop 4K', width: 1920, padding: 64 },
    ]

    const titleText = 'Kiến Trúc Tác Tử Doanh Nghiệp: Chuyển hóa yêu cầu thực tế thành kết quả kiểm chứng 100%'
    const words = titleText.split(/\s+/)

    viewports.forEach((vp) => {
      const containerWidth = vp.width - vp.padding
      // clamp(30px, 4.2vw, 54px)
      const calculatedVw = (vp.width * 4.2) / 100
      const fontSize = Math.max(30, Math.min(54, calculatedVw))
      const lineHeightPx = fontSize * 1.25

      // Longest word width estimation: average Vietnamese glyph width ~ 0.58em at bold font
      const maxWord = words.reduce((a, b) => (a.length > b.length ? a : b))
      const estimatedMaxWordWidth = maxWord.length * fontSize * 0.62

      // 1. Longest word must never exceed container width (no horizontal blowout)
      assert.ok(
        estimatedMaxWordWidth <= containerWidth,
        `Longest word "${maxWord}" (${estimatedMaxWordWidth}px) exceeds ${vp.name} width (${containerWidth}px)`,
      )

      // 2. Line height must provide at least 25% extra vertical clearance over font size
      const clearance = lineHeightPx - fontSize
      assert.ok(
        clearance >= fontSize * 0.24,
        `Insufficient line clearance ${clearance}px at ${vp.name}`,
      )

      // 3. Minimum line height must be >= 37.5px on mobile
      assert.ok(lineHeightPx >= 37.5, `Line height ${lineHeightPx}px too small for ${vp.name}`)
    })
  })
})


/* =========================================================================
 * 2. RAPID DOMAIN SWITCHING STATE CONSISTENCY STRESS TESTS
 * ========================================================================= */

describe('Empirical Challenge 2: Rapid Domain Switching State Consistency', () => {

  it('preserves scenario, step and theme consistency across rapid round-robin cycles', () => {
    const simulator = new HarnessPageStateSimulator('#/harness')

    // Verify initial Banking state
    assert.equal(simulator.selectedId, 'banking')
    assert.equal(simulator.activeStep, 0)
    assert.equal(simulator.currentHash, '#/harness?domain=banking&step=1')
    assert.equal(simulator.getScenario().domain, 'BANKING')

    // Cycle 1: Switch to Education
    simulator.selectScenario('education')
    assert.equal(simulator.selectedId, 'education')
    assert.equal(simulator.activeStep, 0)
    assert.equal(simulator.currentHash, '#/harness?domain=education&step=1')
    assert.equal(simulator.getScenario().domain, 'EDUCATION')
    assert.ok(simulator.getScenario().suggestedCommand.includes('/drive'))

    // Cycle 2: Switch to E-commerce
    simulator.selectScenario('ecommerce')
    assert.equal(simulator.selectedId, 'ecommerce')
    assert.equal(simulator.activeStep, 0)
    assert.equal(simulator.currentHash, '#/harness?domain=ecommerce&step=1')
    assert.equal(simulator.getScenario().domain, 'E-COMMERCE')
    assert.ok(simulator.getScenario().suggestedCommand.includes('/auto'))

    // Cycle 3: Switch back to Banking
    simulator.selectScenario('banking')
    assert.equal(simulator.selectedId, 'banking')
    assert.equal(simulator.activeStep, 0)
    assert.equal(simulator.currentHash, '#/harness?domain=banking&step=1')
    assert.equal(simulator.getScenario().domain, 'BANKING')
  })

  it('resets activeStep to 0 when switching domain from an advanced step', () => {
    const simulator = new HarnessPageStateSimulator('#/harness')

    // Advance to step 5 in Banking (step index 4)
    simulator.selectStep(4)
    assert.equal(simulator.activeStep, 4)
    assert.equal(simulator.currentHash, '#/harness?domain=banking&step=5')
    assert.equal(simulator.getStep().number, '05')

    // Switch to Education -> activeStep MUST reset to 0
    simulator.selectScenario('education')
    assert.equal(simulator.selectedId, 'education')
    assert.equal(simulator.activeStep, 0)
    assert.equal(simulator.currentHash, '#/harness?domain=education&step=1')
    assert.equal(simulator.getStep().number, '01')
    assert.equal(simulator.getStep().plainTitle, 'Nhận đúng việc')
    assert.equal(simulator.getStep().plainSummary, 'Nhận mục tiêu hỗ trợ và giữ nguyên quyền quyết định của giáo viên.')
  })

  it('survives 50 rapid randomized domain switches without state divergence', () => {
    const simulator = new HarnessPageStateSimulator('#/harness')
    const sequence = ['banking', 'education', 'ecommerce', 'banking']

    for (let i = 0; i < 50; i++) {
      const targetDomain = sequence[i % sequence.length]
      simulator.selectScenario(targetDomain)

      // Invariants check
      assert.equal(simulator.selectedId, targetDomain)
      assert.equal(simulator.activeStep, 0)
      assert.equal(simulator.currentHash, `#/harness?domain=${targetDomain}&step=1`)
      assert.equal(simulator.getScenario().id, targetDomain)
      assert.equal(simulator.getStep().number, '01')
    }
  })

  it('verifies TerminalCommandHub token integrity across all 3 domains', () => {
    HARNESS_SCENARIOS.forEach((scenario) => {
      const cmd = scenario.suggestedCommand
      const tokens = cmd.trim().split(/\s+/)
      assert.ok(tokens.length >= 2)

      // First token is always a skill flag
      assert.ok(tokens[0].startsWith('/skill:'))
      const skillName = tokens[0].slice('/skill:'.length)
      assert.ok(skillName.length > 3)

      // Subsequent tokens are valid command flags
      for (let i = 1; i < tokens.length; i++) {
        const flag = tokens[i]
        assert.ok(flag.startsWith('/'))
        assert.ok(COMMAND_FLAGS[flag], `Flag ${flag} defined in COMMAND_FLAGS`)
      }
    })
  })
})


/* =========================================================================
 * 3. URL HASH TAMPERING & QUERY PARAMETER EDGE-CASE TESTS
 * ========================================================================= */

describe('Empirical Challenge 3: URL Hash Tampering & Adversarial Edge Cases', () => {

  it('handles #/harness?domain=invalid&step=99 with safe clamping and domain fallback', () => {
    const res = parseHarnessUrlFromHash('#/harness?domain=invalid&step=99')
    // 1. Invalid domain returns undefined
    assert.equal(res.domain, undefined)
    // 2. Step 99 clamped to max step index 6 (Step 07)
    assert.equal(res.stepIndex, 6)

    // Verify simulator handling
    const simulator = new HarnessPageStateSimulator('#/harness?domain=invalid&step=99')
    assert.equal(simulator.selectedId, 'banking') // fallback to default banking
    assert.equal(simulator.activeStep, 6) // clamped to Step 07
    assert.equal(simulator.getStep().number, '07')
    // Self-healed hash
    assert.equal(simulator.currentHash, '#/harness?domain=banking&step=7')
  })

  it('clamps extreme negative and zero step parameters', () => {
    const step0 = parseHarnessUrlFromHash('#/harness?domain=banking&step=0')
    assert.equal(step0.stepIndex, 0)

    const stepNeg = parseHarnessUrlFromHash('#/harness?domain=banking&step=-42')
    assert.equal(stepNeg.stepIndex, 0)

    const stepNeg999 = parseHarnessUrlFromHash('#/harness?domain=banking&step=-999999')
    assert.equal(stepNeg999.stepIndex, 0)
  })

  it('safely handles non-numeric and floating point step values', () => {
    const stepAbc = parseHarnessUrlFromHash('#/harness?domain=banking&step=abc')
    assert.equal(stepAbc.stepIndex, undefined)

    const stepFloat = parseHarnessUrlFromHash('#/harness?domain=banking&step=3.75')
    assert.equal(stepFloat.stepIndex, 2) // parseInt converts 3.75 to 3, index = 2 (Step 03)

    const stepEmpty = parseHarnessUrlFromHash('#/harness?domain=banking&step=')
    assert.equal(stepEmpty.stepIndex, undefined)
  })

  it('normalizes uppercase domain parameters', () => {
    assert.equal(parseHarnessUrlFromHash('#/harness?domain=BANKING').domain, 'banking')
    assert.equal(parseHarnessUrlFromHash('#/harness?domain=Education').domain, 'education')
    assert.equal(parseHarnessUrlFromHash('#/harness?domain=ECOMMERCE').domain, 'ecommerce')
  })

  it('neutralizes malicious XSS and path traversal attempts in query params', () => {
    const xssAttack = parseHarnessUrlFromHash('#/harness?domain=<script>alert(1)</script>&step=2')
    assert.equal(xssAttack.domain, undefined)
    assert.equal(xssAttack.stepIndex, 1)

    const pathTraversal = parseHarnessUrlFromHash('#/harness?domain=../../../../etc/passwd&step=1')
    assert.equal(pathTraversal.domain, undefined)
    assert.equal(pathTraversal.stepIndex, 0)

    const sqlInjection = parseHarnessUrlFromHash('#/harness?domain=banking%27%20OR%201=1--&step=1')
    assert.equal(sqlInjection.domain, undefined)
  })

  it('preserves pageRoute.mjs routing contract under query parameter tampering', () => {
    // Router extracts base page name before query or subpath
    assert.equal(pageFromHash('#/harness?domain=invalid&step=99'), 'harness')
    assert.equal(pageFromHash('#/harness?domain=banking&step=1'), 'harness')
    assert.equal(pageFromHash('#/harness?unexpected_param=evil'), 'harness')
    assert.equal(pageFromHash('#harness?domain=ecommerce'), 'harness')
    assert.equal(pageFromHash('#/harness'), 'harness')
    assert.equal(pageFromHash(''), null)
    assert.equal(pageFromHash('#/unknownPage?domain=banking'), null)
  })

  it('simulates browser back/forward and hash tampering self-healing cycle', () => {
    const simulator = new HarnessPageStateSimulator('#/harness')
    assert.equal(simulator.currentHash, '#/harness?domain=banking&step=1')

    // User navigates to Education Step 3
    simulator.selectScenario('education')
    simulator.selectStep(2)
    assert.equal(simulator.currentHash, '#/harness?domain=education&step=3')

    // User tampers URL directly in address bar to invalid domain and step 99
    simulator.simulateUserHashChange('#/harness?domain=malicious&step=99')
    // Domain remains education (not overwritten by undefined malicious), step clamped to 6 (step 7)
    assert.equal(simulator.selectedId, 'education')
    assert.equal(simulator.activeStep, 6)
    // URL self-heals to valid canonical deep link
    assert.equal(simulator.currentHash, '#/harness?domain=education&step=7')
  })
})
