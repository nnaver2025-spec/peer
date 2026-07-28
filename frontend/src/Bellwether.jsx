// Bellwether(RS 1등)와 나머지 평균의 괴리(internal Z), 그리고 Top Pick(시총 1등).
// internal_spread = rest_index - bellwether_index 이므로 음수일수록 주도주만 앞서간 상태다.
// 색은 카드 상단 Z-Score와 같은 규칙(양수 빨강 / 음수 파랑)을 쓴다.
const TOOLTIP = '주도주보다 나머지 종목이 덜 오름 = 추격 매수 기회'
const THRESHOLD = 1.5

function toneOf(z) {
  if (z === null || z === undefined) return 'text-zinc-300'
  return z > 0 ? 'text-warn' : 'text-accent'
}

function stateOf(z) {
  if (z === null || z === undefined) return '내부 괴리 산출 불가'
  if (z <= -THRESHOLD) return '주도주만 앞서감, 나머지 따라잡기 여지'
  if (z >= THRESHOLD) return '나머지가 주도주보다 앞섬, 순환매 확산'
  return '내부 괴리 정상 범위'
}

export default function Bellwether({ group }) {
  const {
    bellwether_name: name,
    bellwether_rs: rs,
    bellwether_z_score: z,
    internal_spread: spread,
    top_pick_name: topPick,
  } = group
  if (!name) return null

  const hasZ = z !== null && z !== undefined
  const hasSpread = spread !== null && spread !== undefined
  const detail = hasSpread
    ? `${TOOLTIP} · internal spread ${spread > 0 ? '+' : ''}${spread.toFixed(2)} · ${stateOf(z)}`
    : TOOLTIP

  return (
    <div className="tnum flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs leading-5 text-zinc-400">
      <p title={detail}>
        Bellwether: <span className="text-zinc-600">{name}</span>{' '}
        <span className={toneOf(z)}>
          {hasZ ? `Z ${z > 0 ? '+' : ''}${z.toFixed(2)}` : 'Z n/a'}
        </span>
      </p>
      {topPick && (
        <p title="시가총액 1위 종목 · RS 1위(Bellwether) 기준과 별개">
          Top Pick: <span className="text-zinc-600">{topPick}</span>
        </p>
      )}
      {rs !== null && rs !== undefined && (
        <p className="text-zinc-300" title="Bellwether의 최근 6개월 상대강도 (기준일 100)">
          RS {rs.toFixed(1)}
        </p>
      )}
    </div>
  )
}
