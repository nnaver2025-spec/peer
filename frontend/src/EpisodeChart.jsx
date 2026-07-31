import { useState } from 'react'

// 표 폭을 꽉 채우도록 가로로 긴 viewBox를 쓴다. 640x200으로 두면 높이에 맞춰
// 축소돼 좌우에 빈 공간이 남았다. 폭에 맞춰 늘어나므로 높이는 h-auto로 따라간다.
const W = 1200
const H = 250
const PAD = { top: 16, right: 16, bottom: 26, left: 46 }
const FONT = 11

// 신호 시점을 100으로 다시 잡는다. 그래야 "그 시점 이후 누가 얼마나 갔는지"가
// 두 선의 벌어짐으로 바로 읽힌다. 절대 지수 레벨은 여기서 볼 값이 아니다.
function rebase(values, at) {
  const base = values[at]
  return values.map((v) => (v / base) * 100)
}

// 표의 `국내-해외`(excess)와 같은 정의로 괴리를 잰다.
// 백테스트는 로그 상대지수로 계산하므로, 정규화 지수를 그냥 빼면 같은 시점에
// 두 숫자가 어긋난다(60일 기준 -7.4%p vs -5.5%p).
function logGap(lead, lag, at, i) {
  return (Math.log(lag[i] / lag[at]) - Math.log(lead[i] / lead[at])) * 100
}

/**
 * 에피소드 한 건의 해외/국내 경로.
 *
 * group.series에 그룹 전체 시계열이 한 벌 들어있고, episode.pos가 신호 위치다.
 * 여기서 앞 before일 / 뒤 after일만 잘라 쓴다.
 */
export default function EpisodeChart({ group, episode, before = 60, after = 60 }) {
  const [hover, setHover] = useState(null)
  const { dates, lead, lag } = group.series

  const from = Math.max(0, episode.pos - before)
  const to = Math.min(dates.length - 1, episode.pos + after)
  // 과거 사례는 신호일을 100으로 잡아 '그 이후'를 본다. 현재 건은 신호 이후가
  // 없어 마지막 날에 두 선이 붙어버리므로, 구간 시작을 기준으로 잡아
  // 지금까지 벌어진 폭이 오른쪽 끝에 드러나게 한다.
  const live = episode.pos >= dates.length - 1
  const at = live ? 0 : episode.pos - from

  const d = dates.slice(from, to + 1)
  const leadRaw = lead.slice(from, to + 1)
  const lagRaw = lag.slice(from, to + 1)
  const leadPath = rebase(leadRaw, at)
  const lagPath = rebase(lagRaw, at)

  const all = [...leadPath, ...lagPath]
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1

  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i) => PAD.left + (i / Math.max(d.length - 1, 1)) * innerW
  const y = (v) => PAD.top + (1 - (v - min) / span) * innerH

  const line = (values) =>
    values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')

  const active = hover ?? d.length - 1
  const gapNow = logGap(leadRaw, lagRaw, at, active)
  const signalX = x(at)

  // 눈금은 시작/신호/끝 세 개만. 60개를 다 찍으면 라벨이 겹쳐 읽히지 않는다.
  const ticks = [
    { i: 0, label: d[0]?.slice(2) },
    { i: at, label: d[at]?.slice(2) },
    { i: d.length - 1, label: d[d.length - 1]?.slice(2) },
  ].filter((t, idx, arr) => arr.findIndex((o) => o.i === t.i) === idx)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12px]">
        <span className="flex items-center gap-1.5 text-muted">
          <span className="inline-block h-[2px] w-3 bg-faint" aria-hidden="true" />
          해외 {group.lead_labels.slice(0, 3).join(', ')}
          {group.lead_labels.length > 3 && ` +${group.lead_labels.length - 3}`}
        </span>
        <span className="flex items-center gap-1.5 text-ink">
          <span className="inline-block h-[2px] w-3 bg-accent" aria-hidden="true" />
          국내 {group.lag_labels.slice(0, 3).join(', ')}
          {group.lag_labels.length > 3 && ` +${group.lag_labels.length - 3}`}
        </span>
        <span className="tnum ml-auto text-faint">
          {d[active]} · 국내-해외 {gapNow > 0 ? '+' : ''}
          {gapNow.toFixed(1)}%p
          <span className="ml-1 text-[11px]">
            ({live ? '구간 시작 기준' : '신호 시점 기준'})
          </span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`${group.desc} ${episode.date} 괴리 전후 해외/국내 지수 경로`}
      >
        {/* 신호 시점 = 100 기준선. 여기서 두 선이 만난다. */}
        <line
          x1={PAD.left}
          y1={y(100)}
          x2={W - PAD.right}
          y2={y(100)}
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="3 3"
          className="text-line"
        />
        {/* 신호 시점 수직선. 현재 건은 구간 시작이 기준이라 표시하지 않는다. */}
        {!live && (
          <>
            <line
              x1={signalX}
              y1={PAD.top}
              x2={signalX}
              y2={H - PAD.bottom}
              stroke="currentColor"
              strokeWidth="1"
              className="text-line-strong"
            />
            <text
              x={signalX + 4}
              y={PAD.top + FONT}
              className="fill-faint"
              style={{ fontSize: FONT }}
            >
              신호
            </text>
          </>
        )}

        <path d={line(leadPath)} fill="none" stroke="var(--color-faint)" strokeWidth="1.5" />
        <path d={line(lagPath)} fill="none" stroke="var(--color-accent)" strokeWidth="1.5" />

        <circle cx={x(active)} cy={y(leadPath[active])} r="3" fill="var(--color-faint)" />
        <circle cx={x(active)} cy={y(lagPath[active])} r="3" fill="var(--color-accent)" />

        {/* y축 라벨: 위/아래 끝값만 */}
        {[max, min].map((v) => (
          <text
            key={v}
            x={PAD.left - 6}
            y={y(v) + 3}
            textAnchor="end"
            className="fill-faint"
            style={{ fontSize: FONT }}
          >
            {v.toFixed(0)}
          </text>
        ))}

        {ticks.map((t) => (
          <text
            key={t.i}
            x={x(t.i)}
            y={H - 6}
            textAnchor={t.i === 0 ? 'start' : t.i === d.length - 1 ? 'end' : 'middle'}
            className="fill-faint"
            style={{ fontSize: FONT }}
          >
            {t.label}
          </text>
        ))}

        {/* 히트 영역. 선이 얇아 정확히 짚기 어렵다. */}
        <rect
          x={PAD.left}
          y={PAD.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          onMouseMove={(e) => {
            const box = e.currentTarget.getBoundingClientRect()
            const ratio = (e.clientX - box.left) / box.width
            setHover(Math.round(Math.min(1, Math.max(0, ratio)) * (d.length - 1)))
          }}
          onMouseLeave={() => setHover(null)}
        />
      </svg>
    </div>
  )
}
