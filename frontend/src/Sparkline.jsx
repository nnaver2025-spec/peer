// 스프레드 최근 추이. width/height는 고정 viewBox로 두어 카드 레이아웃이 흔들리지 않게 한다.
export default function Sparkline({ points, stroke }) {
  if (!points || points.length < 2) return null

  const values = points.map((p) => p.spread)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const w = 240
  const h = 44

  const path = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w
      const y = h - ((v - min) / span) * h
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const zeroY = min <= 0 && max >= 0 ? h - ((0 - min) / span) * h : null

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-11 w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="스프레드 최근 추이"
    >
      {zeroY !== null && (
        <line
          x1="0"
          y1={zeroY}
          x2={w}
          y2={zeroY}
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="3 3"
          className="text-neutral-700"
        />
      )}
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.75" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
