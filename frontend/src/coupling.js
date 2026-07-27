// 커플링 등급별 표시 규칙. Z-Score 신호를 어디까지 믿을지 결정한다.
export const COUPLING_META = {
  strong: {
    label: '커플링 강',
    chip: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    bar: 'bg-emerald-400',
    note: '해외 흐름이 국내에 유의하게 전달됨',
  },
  moderate: {
    label: '커플링 중',
    chip: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    bar: 'bg-amber-400',
    note: '부분적 전달, 신호 확인 후 사용',
  },
  weak: {
    label: '커플링 약',
    chip: 'bg-neutral-800/60 text-neutral-500 border-neutral-700',
    bar: 'bg-neutral-600',
    note: '동행 근거 부족, 괴리 수렴 기대 어려움',
  },
  unknown: {
    label: '표본 부족',
    chip: 'bg-neutral-800/60 text-neutral-500 border-neutral-700',
    bar: 'bg-neutral-700',
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
