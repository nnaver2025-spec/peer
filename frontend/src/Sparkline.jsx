// 시계열 최근 추이. width/height는 고정 viewBox로 두어 카드 레이아웃이 흔들리지 않게 한다.
export default function Sparkline({
  points,
  stroke,
  className = 'h-12 w-full',
  valueKey = 'spread',
  label = '스프레드 최근 추이',
}) {
  if (!points || points.length < 2) return null

  const values = points.map((p) => p[valueKey])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const w = 240
  const h = 48

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
      className={className}
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
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
          className="text-line"
        />
      )}
      <path
        d={path}
        fill="none"
        // 토큰 이름을 넘기면 테마를 따라가고, hex를 넘기면 그 값을 쓴다.
        stroke={stroke?.startsWith('--') ? `var(${stroke})` : stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
