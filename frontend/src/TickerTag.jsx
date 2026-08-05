import { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { formatPrice, quoteUrl, signed } from './zone.js'

// 국내 관행대로 상승 적색 / 하락 청색. Z-Score용 warn/accent와는 다른 톤을 써서
// 같은 색이 "신호 방향"과 "가격 등락"을 동시에 뜻하지 않게 한다.
function changeTone(value) {
  if (value === null || value === undefined) return 'text-muted'
  if (value > 0) return 'text-up'
  if (value < 0) return 'text-down'
  return 'text-muted'
}

// 호버 시 뜨는 시세 카드. 브라우저 기본 title은 지연이 길고 스타일을 맞출 수
// 없어 직접 띄운다. 키보드 포커스에서도 같이 열려 마우스 없이 확인 가능하다.
function QuoteCard({ ticker, quote, positionClass }) {
  return (
    <span
      role="tooltip"
      className={`pointer-events-none absolute bottom-full mb-1 z-30 w-max rounded-md border border-line-strong bg-raised px-2.5 py-2 shadow-lg ${positionClass}`}
    >
      <span className="tnum flex items-baseline gap-2">
        <span className="text-[15px] text-ink">{formatPrice(quote.close, ticker)}</span>
        {quote.change !== null && quote.change !== undefined && (
          <span className={`text-[13px] ${changeTone(quote.change)}`}>
            {signed(quote.change)}%
          </span>
        )}
      </span>
      <span className="tnum mt-0.5 flex items-baseline gap-2 text-[12px] text-faint">
        <span>{quote.date}</span>
        {quote.period !== null && quote.period !== undefined && (
          <span>
            구간 <span className={changeTone(quote.period)}>{signed(quote.period, 1)}%</span>
          </span>
        )}
      </span>
    </span>
  )
}

export default function TickerTag({ ticker }) {
  const [open, setOpen] = useState(false)
  const [positionClass, setPositionClass] = useState('left-0')
  const quote = ticker.quote
  const canShow = Boolean(quote) && !ticker.missing

  const handleOpen = (e) => {
    if (e?.currentTarget) {
      const parent = e.currentTarget.closest('section') || e.currentTarget.parentElement
      if (parent) {
        const parentRect = parent.getBoundingClientRect()
        const tagRect = e.currentTarget.getBoundingClientRect()
        const tagCenter = tagRect.left + tagRect.width / 2 - parentRect.left
        const parentWidth = parentRect.width

        if (tagCenter > parentWidth * 0.65) {
          setPositionClass('right-0')
        } else if (tagCenter < parentWidth * 0.35) {
          setPositionClass('left-0')
        } else {
          setPositionClass('left-1/2 -translate-x-1/2')
        }
      }
    }
    setOpen(true)
  }

  return (
    <span className="relative inline-block">
      <a
        href={quoteUrl(ticker.ticker)}
        target="_blank"
        rel="noopener noreferrer"
        title={
          ticker.missing
            ? `${ticker.ticker} · 가격 데이터 없음 (계산 제외)`
            : `${ticker.ticker} 시세 보기`
        }
        onMouseEnter={handleOpen}
        onMouseLeave={() => setOpen(false)}
        onFocus={handleOpen}
        onBlur={() => setOpen(false)}
        className={`group inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[13px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          ticker.missing
            ? 'text-faint/70 line-through hover:text-faint'
            : 'text-muted hover:bg-raised hover:text-ink'
        }`}
      >
        {ticker.label}
        <ExternalLink
          size={10}
          aria-hidden="true"
          className="shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
        />
      </a>
      {open && canShow && (
        <QuoteCard ticker={ticker.ticker} quote={quote} positionClass={positionClass} />
      )}
    </span>
  )
}
