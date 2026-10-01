import { useState, useCallback, useEffect, useRef } from 'react'

interface UseResizableOptions {
  initialSize: number
  minSize?: number
  maxSize?: number
  direction?: 'horizontal' | 'vertical'
  storageKey?: string
}

export function useResizable({
  initialSize,
  minSize = 180,
  maxSize = 600,
  direction = 'horizontal',
  storageKey,
}: UseResizableOptions) {
  const [size, setSize] = useState(() => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const num = parseFloat(saved)
        if (!isNaN(num) && num >= minSize && num <= maxSize) {
          return num
        }
      }
    }
    return initialSize
  })

  const [isDragging, setIsDragging] = useState(false)
  const dragStartPos = useRef<number>(0)
  const dragStartSize = useRef<number>(size)

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    setIsDragging(true)
    dragStartPos.current = direction === 'horizontal' ? e.clientX : e.clientY
    dragStartSize.current = size
  }, [direction, size])

  const handleDoubleClick = useCallback(() => {
    setSize(initialSize)
    if (storageKey) {
      localStorage.setItem(storageKey, String(initialSize))
    }
  }, [initialSize, storageKey])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const step = 16
    if (direction === 'horizontal') {
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        setSize(curr => {
          const next = Math.max(minSize, curr - step)
          if (storageKey) localStorage.setItem(storageKey, String(next))
          return next
        })
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        setSize(curr => {
          const next = Math.min(maxSize, curr + step)
          if (storageKey) localStorage.setItem(storageKey, String(next))
          return next
        })
      }
    } else {
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSize(curr => {
          const next = Math.max(minSize, curr - step)
          if (storageKey) localStorage.setItem(storageKey, String(next))
          return next
        })
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSize(curr => {
          const next = Math.min(maxSize, curr + step)
          if (storageKey) localStorage.setItem(storageKey, String(next))
          return next
        })
      }
    }
  }, [direction, minSize, maxSize, storageKey])

  useEffect(() => {
    if (!isDragging) return

    function onPointerMove(e: PointerEvent) {
      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY
      const delta = currentPos - dragStartPos.current
      const newSize = Math.max(minSize, Math.min(maxSize, dragStartSize.current + delta))
      setSize(newSize)
    }

    function onPointerUp() {
      setIsDragging(false)
      if (storageKey) {
        localStorage.setItem(storageKey, String(size))
      }
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'

    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [isDragging, direction, minSize, maxSize, size, storageKey])

  return {
    size,
    isDragging,
    resizerProps: {
      onPointerDown: handlePointerDown,
      onDoubleClick: handleDoubleClick,
      onKeyDown: handleKeyDown,
      role: 'separator',
      'aria-valuenow': Math.round(size),
      'aria-valuemin': minSize,
      'aria-valuemax': maxSize,
      tabIndex: 0,
    },
  }
}
