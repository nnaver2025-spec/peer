import { useState } from 'react'

const W = 240
const H = 48
// 점 반지름(3)보다 넉넉히 둔다. 최저점이 하단에 놓일 때 원이 잘려 안 보였다.
const PAD = 6

// 여론 점수 추이. 선만 있으면 무슨 값인지 알 수 없어 회차 라벨과 호버 값을 붙였다.
//
// preserveAspectRatio="none"으로 늘리는 기존 Sparkline과 달리 좌표를 그대로 쓴다.
// 점을 찍어야 하는데 비율이 깨지면 점이 타원으로 눌린다.
export default function ScoreTrend({
  points,
  stroke,
  className = 'h-10 w-full',
  label = '여론 점수 추이',
  showCaption = true,
  // 일별 이력은 {date, score, n}, 회차 이력은 {ts, score}를 쓴다.
  unit = '회차',
}) {
  const [hover, setHover] = useState(null)
  if (!points?.length) return null

  const values = points.map((p) => p.score)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const color = stroke?.startsWith('--') ? `var(${stroke})` : stroke

  const xy = (i) => {
    const x = points.length === 1 ? W / 2 : PAD + (i / (points.length - 1)) * (W - PAD * 2)
    const y = H - PAD - ((values[i] - min) / span) * (H - PAD * 2)
    return [x, y]
  }

  const path = values
    .map((_, i) => {
      const [x, y] = xy(i)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const active = hover ?? points.length - 1
  const [ax, ay] = xy(active)
  const shown = points[active]

  return (
    <div className="flex flex-col gap-0.5">
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className={className}
          role="img"
          aria-label={`${label} · 최근 ${points.length}${unit} · 현재 ${values[values.length - 1]}`}
        >
          {/* 라벨을 숨긴 자리(표 안)에서도 값을 볼 수 있게 브라우저 툴팁을 남긴다. */}
          <title>
            {`${label} · 최근 ${points.length}${unit} · ${min} ~ ${max} · 현재 ${
              values[values.length - 1]
            }`}
          </title>

          {points.length > 1 && (
            <path
              d={path}
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
            />
          )}

          {/* 마지막 점은 항상 찍어 현재 위치를 알린다. */}
          {points.map((_, i) => {
            const [x, y] = xy(i)
            const isActive = i === active
            if (!isActive && i !== points.length - 1) return null
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                // viewBox가 240x48인데 실제 렌더 폭은 100px 안팎이라 좌표계가
                // 가로로 눌린다. 반지름을 키워야 화면에서 점으로 보인다.
                r={isActive ? 4 : 3}
                fill={color}
                stroke="var(--color-surface)"
                strokeWidth="1.5"
              />
            )
          })}

          {/* 보이지 않는 히트 영역. 점이 작아 선 위를 정확히 짚기 어렵다. */}
          {points.map((_, i) => {
            const step = (W - PAD * 2) / Math.max(points.length - 1, 1)
            return (
              <rect
                key={`hit-${i}`}
                x={xy(i)[0] - step / 2}
                y={0}
                width={step}
                height={H}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            )
          })}
        </svg>
      </div>

      {showCaption && (
        <p className="tnum truncate text-[11px] text-faint">
          {hover === null
            ? `최근 ${points.length}${unit}`
            : `${stampOf(shown)} ${shown.score}`}
        </p>
      )}
    </div>
  )
}

// 회차 이력은 시각까지, 일별 이력은 날짜만 보여준다.
function stampOf(point) {
  if (point.date) return point.date.slice(5)
  return point.ts?.slice(5) ?? ''
}
