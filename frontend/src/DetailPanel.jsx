import { X } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import CouplingMeter from './CouplingMeter.jsx'
import Bellwether from './Bellwether.jsx'
import TickerTag from './TickerTag.jsx'
import { metaOf } from './coupling.js'
import { isTrusted, signed, zoneOf } from './zone.js'

function TickerList({ label, tickers, index }) {
  return (
    <section>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[13px] text-faint">{label}</h3>
        <span className="tnum text-[14px] text-ink">{index.toFixed(1)}</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-1 gap-y-0.5">
        {tickers.map((t) => (
          <TickerTag key={t.ticker} ticker={t} />
        ))}
      </div>
    </section>
  )
}

function Metric({ label, value, tone = 'text-ink' }) {
  return (
    <div>
      <dt className="text-[13px] text-faint">{label}</dt>
      <dd className={`tnum mt-0.5 text-[22px] leading-none ${tone}`}>{value}</dd>
    </div>
  )
}

export default function DetailPanel({ group, onClose }) {
  const zone = zoneOf(group.zscore)
  const trusted = isTrusted(group)
  const coupling = metaOf(group.coupling)

  return (
    <aside className="flex h-full flex-col gap-6 overflow-y-auto border-l border-line bg-surface p-6">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[17px] font-medium leading-6 text-ink">{group.desc}</h2>
          <p className="tnum mt-1 text-[13px] text-faint">
            {group.sector} · 해외 {group.lead_tickers.length} / 국내 {group.lag_tickers.length} ·{' '}
            {group.base_date}~
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="상세 닫기"
          title="닫기"
          className="shrink-0 rounded p-1 text-faint transition-colors hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </header>

      <dl className="flex items-end justify-between gap-4">
        <Metric
          label="Z-Score"
          value={signed(group.zscore)}
          tone={trusted ? zone.text : 'text-faint'}
        />
        <Metric label="Spread" value={signed(group.spread)} tone="text-muted" />
        <Metric label="Lead" value={group.lead_index.toFixed(1)} tone="text-muted" />
        <Metric label="Lag" value={group.lag_index.toFixed(1)} tone="text-muted" />
      </dl>

      <Sparkline points={group.history} stroke={trusted ? zone.stroke : '--color-line-strong'} />

      <p className="text-[13px] leading-6 text-muted">
        {group.alert
          ? `${zone.label} · ${zone.note}`
          : group.z_extreme
            ? '극단 Z이지만 커플링 근거 부족으로 경고 보류'
            : coupling.note}
      </p>

      <div className="border-t border-line pt-5">
        <CouplingMeter coupling={group.coupling} />
      </div>

      <div className="flex flex-col gap-5 border-t border-line pt-5">
        <TickerList label="Lead 해외" tickers={group.lead_tickers} index={group.lead_index} />
        <TickerList label="Lag 국내" tickers={group.lag_tickers} index={group.lag_index} />
      </div>

      <div className="border-t border-line pt-5">
        <Bellwether group={group} />
      </div>
    </aside>
  )
}
