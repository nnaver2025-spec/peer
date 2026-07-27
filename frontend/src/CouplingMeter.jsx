import { metaOf, corrPercent } from './coupling.js'

// 연도별 상관 안정성. 막대 하나가 한 해이고, 음수 해는 붉게 둔다.
function YearBars({ byYear }) {
  const years = Object.entries(byYear ?? {})
  if (years.length === 0) return null

  return (
    <div className="flex items-end gap-0.5" aria-hidden="true">
      {years.map(([year, v]) => (
        <span
          key={year}
          title={`${year}년 상관 ${v.toFixed(2)}`}
          className={`w-1.5 rounded-sm ${v < 0 ? 'bg-rose-500/60' : 'bg-neutral-500'}`}
          style={{ height: `${Math.max(2, Math.min(14, Math.abs(v) * 34))}px` }}
        />
      ))}
    </div>
  )
}

export default function CouplingMeter({ coupling }) {
  const meta = metaOf(coupling)

  if (!coupling) {
    return <p className="text-[11px] text-neutral-500">{meta.note}</p>
  }

  // 등급은 동행/시차1일 중 강한 쪽으로 정해지므로, 그 채널을 강조해 표시한다.
  const sameDay = coupling.lead_channel === 'same_day'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase text-neutral-500">
          {sameDay ? '동행 전달' : '익일 전달'}
        </span>
        <span className="font-mono text-[11px]">
          <span className={sameDay ? 'text-neutral-300' : 'text-neutral-600'}>
            {coupling.corr.toFixed(2)}
          </span>
          <span className="text-neutral-700"> / </span>
          <span className={sameDay ? 'text-neutral-600' : 'text-neutral-300'}>
            {coupling.corr_lag1.toFixed(2)}
          </span>
        </span>
      </div>

      <div
        className="h-1 w-full overflow-hidden rounded-full bg-neutral-800"
        role="meter"
        aria-valuenow={coupling.strength}
        aria-valuemin={0}
        aria-valuemax={0.5}
        aria-label={sameDay ? '해외-국내 동행 상관' : '해외 전일 대비 국내 익일 상관'}
      >
        <div className={`h-full ${meta.bar}`} style={{ width: `${corrPercent(coupling.strength)}%` }} />
      </div>

      <div className="flex items-end justify-between gap-2">
        <YearBars byYear={coupling.by_year} />
        <span className="font-mono text-[10px] text-neutral-600">
          {coupling.sample_from.slice(0, 4)}~ {coupling.sample_days}일
        </span>
      </div>
    </div>
  )
}
