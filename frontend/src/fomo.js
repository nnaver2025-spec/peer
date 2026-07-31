// FOMO 구간별 강조. zone.js와 같은 역할이고 팔레트도 공유한다.
//
// 색 의미를 스프레드 탭과 맞춘다. 파랑(accent)은 "역발상 매수 여지", 빨강(warn)은
// "과열, 되돌림 위험"이다. 같은 화면에서 파랑이 두 가지를 뜻하면 읽는 사람이 헷갈린다.
const ZONES = {
  extreme_fear: {
    label: '극단적 공포',
    text: 'text-accent',
    bar: 'bg-accent',
    stroke: '--color-accent',
    note: '역발상 매수 타이밍',
  },
  fear: {
    label: '공포',
    text: 'text-accent',
    bar: 'bg-accent/70',
    stroke: '--color-accent',
    note: '공포 우세',
  },
  neutral: {
    label: '중립',
    text: 'text-ink',
    bar: 'bg-line-strong',
    stroke: '--color-faint',
    note: '탐욕과 공포가 균형',
  },
  greed: {
    label: '탐욕',
    text: 'text-warn',
    bar: 'bg-warn/70',
    stroke: '--color-warn',
    note: '탐욕 우세',
  },
  extreme_greed: {
    label: '극단적 탐욕',
    text: 'text-warn',
    bar: 'bg-warn',
    stroke: '--color-warn',
    note: '역발상 매도 타이밍',
  },
}

// 점수 -> 구간 키. 파이썬 fomo_core.ZONES와 같은 경계를 쓴다(CNN Fear & Greed 기준).
// 서버가 zone을 주지 않는 값(시장 지표 구성요소)을 화면에서 분류할 때 쓴다.
export function bandOf(score) {
  if (score == null) return null
  if (score >= 75) return 'extreme_greed'
  if (score >= 55) return 'greed'
  if (score >= 45) return 'neutral'
  if (score >= 25) return 'fear'
  return 'extreme_fear'
}

export function zoneOf(stock) {
  // 표본이 얇아 점수를 못 낸 상태(zone: null)는 중립과 다르다. 회색으로 낮춰
  // "판단 보류"임을 색으로 알린다.
  if (stock.zone == null) {
    return { label: '표본 부족', text: 'text-faint', bar: 'bg-line', stroke: '--color-faint', note: '키워드 표본이 적어 판단 보류' }
  }
  return ZONES[stock.zone] ?? ZONES.neutral
}

// 키워드 카운트를 "가즈아(8) 진입(5)" 형태로 줄인다. 0개면 빈 문자열.
export function topKeywords(counts, limit = 3) {
  return Object.entries(counts ?? {})
    .slice(0, limit)
    .map(([word, n]) => `${word}(${n})`)
    .join(' ')
}

// 실패한 소스 수. 수집 신뢰도를 판단하는 데 쓴다.
//
// 구조상 못 쓰는 소스는 세지 않는다. 지수는 6자리 티커가 없어 네이버 종목토론실을
// 쓸 수 없는데, 이걸 실패로 세면 매 회차 고장난 것처럼 보인다.
export function failedSources(stock) {
  return (stock.per_source ?? []).filter((s) => s.error && !s.unsupported).length
}
