import { metaOf, corrPercent } from './coupling.js'

// 연도별 상관 안정성. 막대 하나가 한 해이고, 음수 해만 강조색으로 둔다.
function YearBars({ byYear }) {
  const years = Object.entries(byYear ?? {})
  if (years.length === 0) return null

  return (
    <div className="flex h-4 items-end gap-1" aria-hidden="true">
      {years.map(([year, v]) => (
        <span
          key={year}
          title={`${year}년 상관 ${v.toFixed(2)}`}
          className={`w-1.5 rounded-sm ${v < 0 ? 'bg-warn/70' : 'bg-line-strong'}`}
          style={{ height: `${Math.max(2, Math.min(16, Math.abs(v) * 34))}px` }}
        />
      ))}
    </div>
  )
}

export default function CouplingMeter({ coupling }) {
  const meta = metaOf(coupling)

  if (!coupling) {
    return <p className="text-[13px] text-faint">{meta.note}</p>
  }

  // 등급은 동행/시차1일 중 강한 쪽으로 정해지므로, 그 채널을 강조해 표시한다.
  const sameDay = coupling.lead_channel === 'same_day'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-faint">{sameDay ? '동행 전달' : '익일 전달'}</span>
        <span className="tnum text-[13px]">
          <span className={sameDay ? 'text-ink' : 'text-faint'}>
            {coupling.corr.toFixed(2)}
          </span>
          <span className="text-line-strong"> / </span>
          <span className={sameDay ? 'text-faint' : 'text-ink'}>
            {coupling.corr_lag1.toFixed(2)}
          </span>
        </span>
      </div>

      <div
        className="h-[3px] w-full overflow-hidden rounded-full bg-raised"
        role="meter"
        aria-valuenow={coupling.strength}
        aria-valuemin={0}
        aria-valuemax={0.5}
        aria-label={sameDay ? '해외-국내 동행 상관' : '해외 전일 대비 국내 익일 상관'}
      >
        <div className={`h-full ${meta.bar}`} style={{ width: `${corrPercent(coupling.strength)}%` }} />
      </div>

      <div className="flex items-end justify-between gap-3">
        <YearBars byYear={coupling.by_year} />
        <span className="tnum text-xs text-faint">
          {coupling.sample_from.slice(0, 4)}~ {coupling.sample_days}일
        </span>
      </div>
    </div>
  )
}
