// 커플링 등급별 표시 규칙. Z-Score 신호를 어디까지 믿을지 결정한다.
// 등급 차이는 점(dot) 밝기로만 구분하고 방향성 강조색은 쓰지 않는다.
//
// 라벨에 '커플링'을 붙이지 않는다. 열 제목이 이미 커플링인데 '커플링 중'으로
// 적으니 등급의 '중'이 '~하는 중'으로 읽혔다. rank는 세 칸 막대의 채움 수다.
export const COUPLING_META = {
  strong: {
    label: '강함',
    rank: 3,
    chip: 'text-ink',
    dot: 'bg-good',
    bar: 'bg-good',
    note: '해외 흐름이 국내에 유의하게 전달됨',
  },
  moderate: {
    label: '보통',
    rank: 2,
    chip: 'text-muted',
    dot: 'bg-muted',
    bar: 'bg-muted',
    note: '부분적 전달, 신호 확인 후 사용',
  },
  weak: {
    label: '약함',
    rank: 1,
    chip: 'text-faint',
    dot: 'bg-line-strong',
    bar: 'bg-line-strong',
    note: '동행 근거 부족, 괴리 수렴 기대 어려움',
  },
  unknown: {
    label: '표본 부족',
    rank: 0,
    chip: 'text-faint',
    dot: 'bg-line',
    bar: 'bg-line',
    note: '커플링 측정 표본이 부족함',
  },
}

export function metaOf(coupling) {
  return COUPLING_META[coupling?.tier ?? 'unknown']
}

export const TIER_STEPS = 3

// 상관 0.5를 게이지 만점으로 본다. 일간 수익률 상관에서 0.5는 이미 매우 높다.
export function corrPercent(corr) {
  return Math.min(100, Math.max(0, ((corr ?? 0) / 0.5) * 100))
}
