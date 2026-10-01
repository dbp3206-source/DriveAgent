import React, { useEffect, useRef, useState, useId } from 'react'
import { Copy16Regular, Checkmark16Regular, ZoomIn16Regular } from '@fluentui/react-icons'

// Mermaid (and ELK) is a large optional dependency. Keep it out of the normal
// chat bundle: a diagram is rendered only after a response actually contains
// Mermaid syntax. This keeps the common text/RAG path fast on local machines.
let mermaidPromise: Promise<typeof import('mermaid')> | null = null

function loadMermaid() {
  mermaidPromise ??= import('mermaid').then((module) => {
    const mermaid = module.default
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        primaryColor: '#1a73e8',
        primaryTextColor: '#ffffff',
        primaryBorderColor: '#4285f4',
        lineColor: '#8ab4f8',
        secondaryColor: '#1e293b',
        tertiaryColor: '#0f172a',
      },
      securityLevel: 'loose',
    })
    return module
  })
  return mermaidPromise
}

interface MermaidDiagramProps {
  chart: string
  onZoom?: (svgHtml: string) => void
}

export function MermaidDiagram({ chart, onZoom }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svgHtml, setSvgHtml] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const uniqueId = useId().replace(/[^a-zA-Z0-9_-]/g, '_')

  useEffect(() => {
    let active = true
    const renderChart = async () => {
      try {
        setError(null)
        const cleanChart = chart.trim()
        const { default: mermaid } = await loadMermaid()
        const { svg } = await mermaid.render(`mermaid_${uniqueId}`, cleanChart)
        if (active) {
          setSvgHtml(svg)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Lỗi hiển thị sơ đồ')
        }
      }
    }
    renderChart()
    return () => {
      active = false
    }
  }, [chart, uniqueId])

  function handleCopy() {
    navigator.clipboard.writeText(chart)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (error) {
    return (
      <div className="mermaid-fallback">
        <div className="mermaid-fallback__header">
          <span>Sơ đồ (Mã nguồn)</span>
          <button type="button" onClick={handleCopy} className="mermaid-action-btn">
            {copied ? <Checkmark16Regular /> : <Copy16Regular />}
            <span>{copied ? 'Đã chép' : 'Chép mã'}</span>
          </button>
        </div>
        <pre><code>{chart}</code></pre>
      </div>
    )
  }

  return (
    <div className="mermaid-container" ref={containerRef}>
      <div className="mermaid-toolbar">
        <span className="mermaid-tag">Sơ đồ tương tác</span>
        <div className="mermaid-actions">
          {onZoom && svgHtml ? (
            <button
              type="button"
              className="mermaid-action-btn"
              onClick={() => onZoom(svgHtml)}
              title="Phóng to sơ đồ"
              aria-label="Phóng to sơ đồ"
            >
              <ZoomIn16Regular />
              <span>Phóng to</span>
            </button>
          ) : null}
          <button
            type="button"
            className="mermaid-action-btn"
            onClick={handleCopy}
            title="Sao chép cú pháp Mermaid"
            aria-label="Sao chép cú pháp Mermaid"
          >
            {copied ? <Checkmark16Regular /> : <Copy16Regular />}
            <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
          </button>
        </div>
      </div>
      <div
        className="mermaid-render-area"
        dangerouslySetInnerHTML={{ __html: svgHtml }}
      />
    </div>
  )
}
