import { useCallback, useEffect, useRef, useState } from 'react'
import EvidenceList from './EvidenceList.jsx'

const CLOSE_DELAY_MS = 120   // 트리거와 패널 사이를 지나갈 여유
const PANEL_WIDTH = 420
const MARGIN = 12

// 호버로 원글을 보여주는 팝오버.
//
// 접기 방식은 목록이 열릴 때 아래 내용이 밀려 내려가 다른 카드를 비교하기 어려웠다.
// 팝오버는 레이아웃을 건드리지 않는다. 대신 화면 밖으로 나가지 않게 위치를 재고,
// 마우스가 트리거에서 패널로 옮겨가는 동안 닫히지 않도록 지연을 둔다.
export default function EvidencePopover({ evidence, label, children }) {
  const [open, setOpen] = useState(false)
  const [style, setStyle] = useState(null)
  const triggerRef = useRef(null)
  const timer = useRef(null)

  const place = useCallback(() => {
    const node = triggerRef.current
    if (!node) return
    const rect = node.getBoundingClientRect()
    const width = Math.min(PANEL_WIDTH, window.innerWidth - MARGIN * 2)

    // 오른쪽으로 넘치면 왼쪽 정렬로 뒤집는다.
    let left = rect.left
    if (left + width > window.innerWidth - MARGIN) {
      left = Math.max(MARGIN, window.innerWidth - width - MARGIN)
    }

    // 아래 공간이 부족하면 위로 띄운다.
    const below = window.innerHeight - rect.bottom
    const maxHeight = Math.max(below, rect.top) - MARGIN * 2
    const openUp = below < 260 && rect.top > below

    setStyle({
      left,
      width,
      maxHeight: Math.max(180, Math.min(460, maxHeight)),
      ...(openUp
        ? { bottom: window.innerHeight - rect.top + 6 }
        : { top: rect.bottom + 6 }),
    })
  }, [])

  const show = () => {
    clearTimeout(timer.current)
    place()
    setOpen(true)
  }

  const hide = () => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS)
  }

  useEffect(() => () => clearTimeout(timer.current), [])

  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    // 스크롤하면 트리거가 움직이므로 위치를 다시 잡는다.
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, place])

  if (!evidence?.length) return null

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={() => (open ? setOpen(false) : show())}
        aria-expanded={open}
        className={`rounded text-[12px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          open ? 'text-ink' : 'text-muted hover:text-ink'
        }`}
      >
        {children ?? `원글 ${evidence.length}개`}
      </button>

      {open && style && (
        <div
          onMouseEnter={show}
          onMouseLeave={hide}
          style={style}
          className="fixed z-30 overflow-y-auto rounded-md border border-line-strong bg-surface px-3 py-2 shadow-lg"
        >
          {label && <p className="pb-1 text-[11px] text-faint">{label}</p>}
          <EvidenceList evidence={evidence} />
        </div>
      )}
    </>
  )
}
