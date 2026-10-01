export function VeridraMark({ className = '' }: { className?: string }) {
  return (
    <img
      className={`veridra-mark ${className}`.trim()}
      src="/veridra-mark-transparent.png"
      alt=""
      aria-hidden="true"
      decoding="async"
      draggable={false}
    />
  )
}

export function VeridraLogo({ className = '' }: { className?: string }) {
  return (
    <img
      className={`veridra-logo ${className}`.trim()}
      src="/veridra-logo-transparent.png"
      aria-label="Veridra"
      alt="Veridra"
      decoding="async"
      draggable={false}
    />
  )
}
