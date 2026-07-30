import { AlertTriangle } from 'lucide-react'

// 데이터가 얼마나 최신인지 알린다.
//
// 갱신 시각을 화면 맨 아래 작은 글씨로만 두면 크론이 죽어도 아무 신호가 없다.
// 여론은 시간에 민감해서 옛 데이터를 지금 것으로 읽으면 판단이 틀어진다.
// 두 회차(주기 x 2)를 놓치면 경고로 바꾼다.
const STALE_FACTOR = 2

export function ageOf(generatedAt) {
  if (!generatedAt) return null
  // `2026-07-30 21:28:09`는 ISO가 아니라 Safari에서 NaN이 된다. T를 넣어준다.
  const ts = new Date(generatedAt.replace(' ', 'T')).getTime()
  if (Number.isNaN(ts)) return null
  return Math.max(0, Date.now() - ts)
}

function label(ms) {
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return '방금 갱신'
  if (minutes < 60) return `${minutes}분 전 갱신`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}시간 전 갱신`
  return `${Math.floor(hours / 24)}일 전 갱신`
}

export default function Freshness({ generatedAt, intervalHours = 2 }) {
  const age = ageOf(generatedAt)
  if (age === null) return null

  const stale = age > intervalHours * STALE_FACTOR * 3_600_000

  return (
    <span
      className={`inline-flex items-center gap-1 text-[12px] ${
        stale ? 'text-warn' : 'text-faint'
      }`}
      title={
        stale
          ? `${generatedAt} 이후 갱신되지 않았습니다. ${intervalHours}시간 주기 기준으로 두 회차를 놓쳤습니다.`
          : generatedAt
      }
    >
      {stale && <AlertTriangle size={11} aria-hidden="true" />}
      {label(age)}
    </span>
  )
}
