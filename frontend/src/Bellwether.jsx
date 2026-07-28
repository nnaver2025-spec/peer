// 주도주(RS 1등)와 나머지 평균의 괴리(internal Z), 그리고 대장주(시총 1등).
// 화면 라벨은 한국어로 쓰고, JSON 필드명(bellwether_*, top_pick_*)은 그대로 둔다.
// internal_spread = rest_index - bellwether_index 이므로 음수일수록 주도주만 앞서간 상태다.
// 색은 카드 상단 Z-Score와 같은 규칙(양수 빨강 / 음수 파랑)을 쓴다.
import { ratingTone } from './zone.js'

const TOOLTIP = '주도주보다 나머지 종목이 덜 오름 = 추격 매수 기회'
const THRESHOLD = 1.5

function toneOf(z) {
  if (z === null || z === undefined) return 'text-faint'
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
    bellwether_rs_rating: rating,
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

  const hasRating = rating !== null && rating !== undefined
  const hasRs = rs !== null && rs !== undefined
  // 등급은 순위만 담으므로 실제 상승률을 툴팁에 함께 남긴다.
  const ratingDetail = [
    '국내 유니버스 백분위 · 100이 최상위',
    hasRs ? `6개월 ${rs >= 100 ? '+' : ''}${(rs - 100).toFixed(1)}%` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="tnum flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px] leading-6 text-faint">
      <p title={detail}>
        주도주: <span className="text-muted">{name}</span>{' '}
        <span className={toneOf(z)}>
          {hasZ ? `Z ${z > 0 ? '+' : ''}${z.toFixed(2)}` : 'Z n/a'}
        </span>
      </p>
      {topPick && (
        <p title="시가총액 1위 종목 · RS 1위(주도주) 기준과 별개">
          대장주: <span className="text-muted">{topPick}</span>
        </p>
      )}
      {hasRating && (
        <p title={ratingDetail}>
          RS <span className={ratingTone(rating)}>{rating}</span>
          <span className="text-faint/70">/100</span>
        </p>
      )}
    </div>
  )
}
