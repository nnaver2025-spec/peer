// 커플링 등급별 표시 규칙. Z-Score 신호를 어디까지 믿을지 결정한다.
// 등급 차이는 점(dot) 밝기로만 구분하고 방향성 강조색은 쓰지 않는다.
//
// 라벨에 '커플링'을 붙이지 않는다. 열 제목이 이미 커플링인데 '커플링 중'으로
// 적으니 등급의 '중'이 '~하는 중'으로 읽혔다.
//
// 표에서는 등급 대신 실제 강도를 보여준다(GroupTable.jsx). 등급 폭이 경계
// 차이보다 커서 3단계로 뭉치면 값이 왜곡됐다. 색만 등급을 따른다.
export const COUPLING_META = {
  strong: {
    label: '강함',
    chip: 'text-ink',
    dot: 'bg-good',
    bar: 'bg-good',
    note: '해외 흐름이 국내에 유의하게 전달됨',
  },
  moderate: {
    label: '보통',
    chip: 'text-muted',
    dot: 'bg-muted',
    bar: 'bg-muted',
    note: '부분적 전달, 신호 확인 후 사용',
  },
  weak: {
    label: '약함',
    chip: 'text-faint',
    dot: 'bg-line-strong',
    bar: 'bg-line-strong',
    note: '동행 근거 부족, 괴리 수렴 기대 어려움',
  },
  unknown: {
    label: '표본 부족',
    chip: 'text-faint',
    dot: 'bg-line',
    bar: 'bg-line',
    note: '커플링 측정 표본이 부족함',
  },
}

export function metaOf(coupling) {
  return COUPLING_META[coupling?.tier ?? 'unknown']
}

// 상관 0.5를 게이지 만점으로 본다. 일간 수익률 상관에서 0.5는 이미 매우 높다.
export function corrPercent(corr) {
  return Math.min(100, Math.max(0, ((corr ?? 0) / 0.5) * 100))
}
