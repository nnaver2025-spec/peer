import { bandOf, zoneOf } from './fomo.js'

function Component({ item }) {
  const zone = zoneOf({ zone: bandOf(item.score) })
  const missing = item.score == null

  return (
    <div className="flex items-center gap-3" title={item.detail}>
      <span className="w-[68px] shrink-0 truncate text-[12px] text-muted">{item.label}</span>
      <span className="relative h-1.5 flex-1 overflow-hidden rounded-sm bg-raised">
        {!missing && (
          <span
            className={`absolute inset-y-0 w-[3px] rounded-sm ${zone.bar}`}
            style={{ left: `calc(${item.score}% - 1.5px)` }}
          />
        )}
      </span>
      <span className={`tnum w-[30px] shrink-0 text-right text-[12px] ${missing ? 'text-faint' : zone.text}`}>
        {missing ? '—' : Math.round(item.score)}
      </span>
    </div>
  )
}

export default function MarketGauge({ gauge }) {
  if (!gauge) return null
  const zone = zoneOf({ zone: bandOf(gauge.score) })

  return (
    <div className="min-w-[260px]">
      <p className="text-[12px] text-faint">시장 지표</p>
      <div className="mt-1 flex items-baseline gap-2.5">
        <span className={`tnum text-[34px] font-medium leading-none ${zone.text}`}>
          {gauge.score.toFixed(1)}
        </span>
        <span className={`text-[14px] ${zone.text}`}>{gauge.label}</span>
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        {gauge.components.map((item) => (
          <Component key={item.key} item={item} />
        ))}
      </div>
    </div>
  )
}
