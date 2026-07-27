import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, ExternalLink, RefreshCw } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import CouplingMeter from './CouplingMeter.jsx'
import { metaOf } from './coupling.js'

const THRESHOLD = 1.5

// Z-Score 구간별 카드 테두리 / 강조 색상
function zoneOf(z) {
  if (z >= THRESHOLD) {
    return {
      label: '오버슈팅',
      border: 'border-rose-500/70',
      ring: 'shadow-[0_0_0_1px_rgba(244,63,94,0.35)]',
      text: 'text-rose-400',
      chip: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
      stroke: '#fb7185',
      Icon: ArrowUpRight,
      note: '국내가 해외보다 과도하게 앞섬',
    }
  }
  if (z <= -THRESHOLD) {
    return {
      label: '언더슈팅',
      border: 'border-sky-500/70',
      ring: 'shadow-[0_0_0_1px_rgba(14,165,233,0.35)]',
      text: 'text-sky-400',
      chip: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
      stroke: '#38bdf8',
      Icon: ArrowDownRight,
      note: '국내 갭 확대, 따라잡기 여지',
    }
  }
  return {
    label: '중립',
    border: 'border-neutral-800',
    ring: '',
    text: 'text-neutral-300',
    chip: 'bg-neutral-800/60 text-neutral-400 border-neutral-700',
    stroke: '#a3a3a3',
    Icon: null,
    note: '통계적 정상 범위',
  }
}

// 국내 종목은 네이버 금융, 해외는 Yahoo Finance로 연결한다.
function quoteUrl(ticker) {
  const kr = ticker.match(/^(\d{6})\.(KS|KQ)$/i)
  return kr
    ? `https://finance.naver.com/item/main.naver?code=${kr[1]}`
    : `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}`
}

function TickerRow({ label, tickers, index, accent }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-normal text-neutral-500">{label}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {tickers.map((t) => (
            <a
              key={t.ticker}
              href={quoteUrl(t.ticker)}
              target="_blank"
              rel="noopener noreferrer"
              title={
                t.missing
                  ? `${t.ticker} · 가격 데이터 없음 (계산 제외)`
                  : `${t.ticker} 시세 보기`
              }
              className={`group inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-neutral-400 ${
                t.missing
                  ? 'border-neutral-800 text-neutral-600 line-through hover:text-neutral-500'
                  : 'border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-neutral-500 hover:text-neutral-50'
              }`}
            >
              {t.label}
              <ExternalLink
                size={9}
                aria-hidden="true"
                className="shrink-0 opacity-0 transition-opacity group-hover:opacity-70"
              />
            </a>
          ))}
        </div>
      </div>
      <div className={`shrink-0 text-right font-mono text-sm ${accent}`}>{index.toFixed(1)}</div>
    </div>
  )
}

function GroupCard({ group }) {
  const zone = zoneOf(group.zscore)
  const { Icon } = zone
  const coupling = metaOf(group.coupling)
  const trusted = group.coupling?.tier === 'strong' || group.coupling?.tier === 'moderate'

  return (
    <article
      className={`flex flex-col gap-4 rounded-lg border bg-neutral-950/80 p-4 ${
        trusted ? `${zone.border} ${zone.ring}` : 'border-neutral-800'
      }`}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="rounded bg-neutral-800/80 px-1.5 py-0.5 text-[10px] text-neutral-400">
              {group.sector}
            </span>
            <h2 className="truncate text-base font-semibold text-neutral-100">{group.desc}</h2>
          </div>
          <p className="mt-0.5 font-mono text-[11px] text-neutral-500">
            {group.lead_tickers.length} vs {group.lag_tickers.length} 종목
          </p>
        </div>
        <span
          title={coupling.note}
          className={`flex shrink-0 items-center gap-1 rounded border px-2 py-0.5 text-[11px] ${coupling.chip}`}
        >
          {coupling.label}
        </span>
      </header>

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase text-neutral-500">Z-Score</div>
          <div
            className={`flex items-center gap-1 font-mono text-3xl font-semibold ${
              trusted ? zone.text : 'text-neutral-500'
            }`}
          >
            {Icon && <Icon size={20} aria-hidden="true" />}
            {group.zscore > 0 ? '+' : ''}
            {group.zscore.toFixed(2)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] uppercase text-neutral-500">Spread</div>
          <div className="font-mono text-lg text-neutral-200">
            {group.spread > 0 ? '+' : ''}
            {group.spread.toFixed(2)}
          </div>
        </div>
      </div>

      <Sparkline points={group.history} stroke={trusted ? zone.stroke : '#525252'} />

      <div className="border-t border-neutral-800 pt-3">
        <CouplingMeter coupling={group.coupling} />
      </div>

      <div className="flex flex-col gap-3 border-t border-neutral-800 pt-3">
        <TickerRow
          label="Lead 해외"
          tickers={group.lead_tickers}
          index={group.lead_index}
          accent="text-neutral-400"
        />
        <TickerRow
          label="Lag 국내"
          tickers={group.lag_tickers}
          index={group.lag_index}
          accent="text-neutral-200"
        />
      </div>

      <p className="text-[11px] text-neutral-500">
        {group.alert ? (
          <span className={`inline-flex items-center gap-1 ${zone.text}`}>
            <AlertTriangle size={11} aria-hidden="true" />
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

const FILTERS = [
  { id: 'all', label: '전체' },
  { id: 'trusted', label: '커플링 유효' },
  { id: 'alert', label: '경고' },
  { id: 'overshoot', label: '오버슈팅' },
  { id: 'undershoot', label: '언더슈팅' },
]

const TIER_RANK = { strong: 0, moderate: 1, weak: 2, unknown: 3 }

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [sector, setSector] = useState('all')

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}dashboard_data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  const sectors = useMemo(() => {
    if (!data) return []
    return [...new Set(data.groups.map((g) => g.sector))]
  }, [data])

  const groups = useMemo(() => {
    if (!data) return []
    let all = [...data.groups].sort((a, b) => {
      const ra = TIER_RANK[a.coupling?.tier ?? 'unknown']
      const rb = TIER_RANK[b.coupling?.tier ?? 'unknown']
      return ra !== rb ? ra - rb : Math.abs(b.zscore) - Math.abs(a.zscore)
    })
    if (sector !== 'all') all = all.filter((g) => g.sector === sector)
    if (filter === 'trusted') {
      return all.filter((g) => TIER_RANK[g.coupling?.tier ?? 'unknown'] <= 1)
    }
    if (filter === 'alert') return all.filter((g) => g.alert)
    if (filter === 'overshoot') return all.filter((g) => g.zscore >= THRESHOLD)
    if (filter === 'undershoot') return all.filter((g) => g.zscore <= -THRESHOLD)
    return all
  }, [data, filter, sector])

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-3 text-amber-400" aria-hidden="true" />
          <p className="text-neutral-200">dashboard_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-2 font-mono text-xs text-neutral-500">python peer_tracker.py</p>
        </div>
      </main>
    )
  }

  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <RefreshCw className="animate-spin text-neutral-600" aria-hidden="true" />
      </main>
    )
  }

  const alertCount = data.groups.filter((g) => g.alert).length
  const trustedCount = data.groups.filter(
    (g) => TIER_RANK[g.coupling?.tier ?? 'unknown'] <= 1
  ).length

  return (
    <div className="min-h-screen text-neutral-200">
      <header className="border-b border-neutral-800 bg-neutral-950/60 px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-neutral-50">Peer Spread Tracker</h1>
            <p className="mt-1 text-xs text-neutral-500">
              Lag(국내) - Lead(해외) 정규화 인덱스 스프레드 · {data.z_window}일 Z-Score · 임계 |Z|{' '}
              {data.alert_threshold} · 커플링 표본 {data.coupling_start}~
            </p>
          </div>
          <dl className="flex items-end gap-6 text-right">
            <div>
              <dt className="text-[11px] uppercase text-neutral-500">그룹</dt>
              <dd className="font-mono text-lg text-neutral-200">{data.groups.length}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase text-neutral-500">경고</dt>
              <dd className={`font-mono text-lg ${alertCount ? 'text-rose-400' : 'text-neutral-200'}`}>
                {alertCount}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase text-neutral-500">커플링 유효</dt>
              <dd className="font-mono text-lg text-neutral-200">{trustedCount}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase text-neutral-500">기준일</dt>
              <dd className="font-mono text-sm text-neutral-400">{data.period.end}</dd>
            </div>
          </dl>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-5">
        <div
          role="group"
          aria-label="Z-Score 구간 필터"
          className="inline-flex rounded border border-neutral-800 bg-neutral-950 p-0.5"
        >
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`rounded px-3 py-1.5 text-xs transition-colors ${
                filter === f.id
                  ? 'bg-neutral-800 text-neutral-100'
                  : 'text-neutral-500 hover:text-neutral-300'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-1" role="group" aria-label="섹터 필터">
          {['all', ...sectors].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSector(s)}
              aria-pressed={sector === s}
              className={`rounded border px-2.5 py-1 text-xs transition-colors ${
                sector === s
                  ? 'border-neutral-600 bg-neutral-800 text-neutral-100'
                  : 'border-neutral-800 text-neutral-500 hover:border-neutral-700 hover:text-neutral-300'
              }`}
            >
              {s === 'all' ? '전체 섹터' : s}
            </button>
          ))}
        </div>

        <section className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => (
            <GroupCard key={g.key} group={g} />
          ))}
        </section>

        {groups.length === 0 && (
          <p className="mt-10 text-center text-sm text-neutral-500">해당 구간의 그룹이 없습니다.</p>
        )}

        <footer className="mt-8 border-t border-neutral-800 pt-4 font-mono text-[11px] text-neutral-600">
          generated_at {data.generated_at} · {data.period.start} ~ {data.period.end}
        </footer>
      </div>
    </div>
  )
}
