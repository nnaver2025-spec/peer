import { AlertTriangle } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import CouplingMeter from './CouplingMeter.jsx'
import Bellwether from './Bellwether.jsx'
import ZBar from './ZBar.jsx'
import { metaOf } from './coupling.js'
import { isTrusted, signed, zoneOf } from './zone.js'

export default function GroupCard({ group, onSelect }) {
  const zone = zoneOf(group.zscore)
  const { Icon } = zone
  const coupling = metaOf(group.coupling)
  const trusted = isTrusted(group)
  const highs = group.recent_highs ?? []

  return (
    <article
      onClick={() => onSelect(group.key)}
      className="flex cursor-pointer flex-col gap-5 rounded-lg border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-medium leading-6 text-ink">
            {group.desc}
            {highs.length > 0 && (
              <span
                title={highs.map((h) => `${h.label} (${h.date})`).join('\n')}
                className="ml-1.5 inline-flex items-center gap-0.5 rounded bg-amber-500/[0.12] px-1.5 py-0.5 text-[11px] font-semibold text-amber-500"
              >
                🔥 {highs.length}
              </span>
            )}
          </h2>
          <p className="tnum mt-0.5 text-[13px] text-faint">
            {group.sector} · 해외 {group.lead_tickers.length} / 국내 {group.lag_tickers.length}
          </p>
        </div>
        <span
          title={coupling.note}
          className={`flex shrink-0 items-center gap-1.5 text-[13px] ${coupling.chip}`}
        >
          <span className={`size-1.5 rounded-full ${coupling.dot}`} aria-hidden="true" />
          {/* 카드에는 열 제목이 없으므로 무슨 값인지 밝힌다. */}
          커플링 {coupling.label}
        </span>
      </header>

      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-[13px] text-faint">Z-Score</div>
          <div
            className={`tnum mt-1 flex items-center gap-1.5 text-[34px] font-medium leading-none ${
              trusted ? zone.text : 'text-faint'
            }`}
          >
            {Icon && <Icon size={20} strokeWidth={2} aria-hidden="true" />}
            {signed(group.zscore)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[13px] text-faint">Spread</div>
          <div className="tnum mt-1 text-[17px] leading-none text-muted">
            {signed(group.spread)}
          </div>
        </div>
      </div>

      <ZBar z={group.zscore} tone={trusted ? zone.bar : 'bg-line-strong'} />
      <Sparkline points={group.history} stroke={trusted ? zone.stroke : '--color-line-strong'} />

      <div className="border-t border-line pt-4">
        <CouplingMeter coupling={group.coupling} />
      </div>

      <div className="border-t border-line pt-4">
        <Bellwether group={group} />
      </div>

      <p className="text-[13px] leading-6 text-faint">
        {group.alert ? (
          <span className={`inline-flex items-center gap-1.5 ${zone.text}`}>
            <AlertTriangle size={13} aria-hidden="true" />
            {zone.label} · {zone.note}
          </span>
        ) : group.z_extreme ? (
          <span>극단 Z이지만 커플링 근거 부족으로 경고 보류</span>
        ) : (
          coupling.note
        )}
      </p>
    </article>
  )
}
