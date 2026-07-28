import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, ExternalLink, RefreshCw } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import CouplingMeter from './CouplingMeter.jsx'
import Bellwether from './Bellwether.jsx'
import { metaOf } from './coupling.js'

const THRESHOLD = 1.5

// Z-Score 구간별 강조. 색은 숫자와 추이선에만 쓰고 카드 테두리는 항상 회색으로 둔다.
function zoneOf(z) {
  if (z >= THRESHOLD) {
    return {
      label: '오버슈팅',
      text: 'text-warn',
      stroke: '#d92d4b',
      Icon: ArrowUpRight,
      note: '국내가 해외보다 과도하게 앞섬',
    }
  }
  if (z <= -THRESHOLD) {
    return {
      label: '언더슈팅',
      text: 'text-accent',
      stroke: '#3d5afe',
      Icon: ArrowDownRight,
      note: '국내 갭 확대, 따라잡기 여지',
    }
  }
  return {
    label: '중립',
    text: 'text-zinc-900',
    stroke: '#a1a1aa',
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
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-xs text-zinc-400">{label}</div>
        <div className="mt-2 flex flex-wrap gap-x-1.5 gap-y-1">
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
              className={`group inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[13px] leading-6 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${
                t.missing
                  ? 'text-zinc-300 line-through hover:text-zinc-400'
                  : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
              }`}
            >
              {t.label}
              <ExternalLink
                size={11}
                aria-hidden="true"
                className="shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
              />
            </a>
          ))}
        </div>
      </div>
      <div className={`tnum shrink-0 text-right text-[15px] ${accent}`}>{index.toFixed(1)}</div>
    </div>
  )
}

function GroupCard({ group }) {
  const zone = zoneOf(group.zscore)
  const { Icon } = zone
  const coupling = metaOf(group.coupling)
  const trusted = group.coupling?.tier === 'strong' || group.coupling?.tier === 'moderate'

  return (
    <article className="flex flex-col gap-7 rounded-lg border border-line bg-surface p-5 sm:p-7">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-[17px] font-medium leading-7 text-zinc-900">{group.desc}</h2>
          <p className="tnum mt-1 text-[13px] text-zinc-400">
            {group.sector} · 해외 {group.lead_tickers.length} / 국내 {group.lag_tickers.length}
          </p>
        </div>
        <span
          title={coupling.note}
          className={`flex shrink-0 items-center gap-1.5 text-[13px] ${coupling.chip}`}
        >
          <span className={`size-1.5 rounded-full ${coupling.dot}`} aria-hidden="true" />
          {coupling.label}
        </span>
      </header>

      <div className="flex items-end justify-between gap-6">
        <div>
          <div className="text-[13px] text-zinc-400">Z-Score</div>
          <div
            className={`tnum mt-1 flex items-center gap-1.5 text-[44px] font-medium leading-none ${
              trusted ? zone.text : 'text-zinc-400'
            }`}
          >
            {Icon && <Icon size={26} strokeWidth={2} aria-hidden="true" />}
            {group.zscore > 0 ? '+' : ''}
            {group.zscore.toFixed(2)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[13px] text-zinc-400">Spread</div>
          <div className="tnum mt-1 text-xl leading-none text-zinc-700">
            {group.spread > 0 ? '+' : ''}
            {group.spread.toFixed(2)}
          </div>
        </div>
      </div>

      <Sparkline points={group.history} stroke={trusted ? zone.stroke : '#d4d4d8'} />

      <div className="border-t border-line pt-6">
        <CouplingMeter coupling={group.coupling} />
      </div>

      <div className="flex flex-col gap-5 border-t border-line pt-6">
        <TickerRow
          label="Lead 해외"
          tickers={group.lead_tickers}
          index={group.lead_index}
          accent="text-zinc-500"
        />
        <TickerRow
          label="Lag 국내"
          tickers={group.lag_tickers}
          index={group.lag_index}
          accent="text-zinc-800"
        />
        <Bellwether group={group} />
      </div>

      <p className="text-[13px] leading-6 text-zinc-500">
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
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-zinc-800">dashboard_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-3 font-mono text-sm text-zinc-400">python peer_tracker.py</p>
        </div>
      </main>
    )
  }

  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <RefreshCw className="animate-spin text-zinc-300" aria-hidden="true" />
      </main>
    )
  }

  const alertCount = data.groups.filter((g) => g.alert).length
  const trustedCount = data.groups.filter(
    (g) => TIER_RANK[g.coupling?.tier ?? 'unknown'] <= 1
  ).length

  return (
    <div className="min-h-screen text-zinc-800">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-end justify-between gap-x-8 gap-y-6 px-5 py-8 sm:px-8 sm:py-10">
          <div className="max-w-xl">
            <h1 className="text-2xl font-medium leading-8 text-zinc-900">Peer Spread Tracker</h1>
            <p className="mt-2 text-[15px] leading-7 text-zinc-500">
              Lag(국내) - Lead(해외) 정규화 인덱스 스프레드 · {data.z_window}일 Z-Score · 임계 |Z|{' '}
              {data.alert_threshold} · 커플링 표본 {data.coupling_start}~
            </p>
          </div>
          <dl className="flex flex-wrap items-end gap-x-10 gap-y-4 text-right">
            <div>
              <dt className="text-[13px] text-zinc-400">그룹</dt>
              <dd className="tnum mt-1 text-2xl leading-none text-zinc-900">{data.groups.length}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-zinc-400">경고</dt>
              <dd
                className={`tnum mt-1 text-2xl leading-none ${
                  alertCount ? 'text-warn' : 'text-zinc-900'
                }`}
              >
                {alertCount}
              </dd>
            </div>
            <div>
              <dt className="text-[13px] text-zinc-400">커플링 유효</dt>
              <dd className="tnum mt-1 text-2xl leading-none text-zinc-900">{trustedCount}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-zinc-400">기준일</dt>
              <dd className="tnum mt-1 text-[15px] leading-none text-zinc-500">{data.period.end}</dd>
            </div>
          </dl>
        </div>
      </header>

      <div className="mx-auto max-w-[1400px] px-5 py-8 sm:px-8 sm:py-10">
        <div className="flex flex-col gap-4">
          <div role="group" aria-label="Z-Score 구간 필터" className="-ml-3 flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                aria-pressed={filter === f.id}
                className={`rounded-md px-3 py-1.5 text-[14px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${
                  filter === f.id
                    ? 'bg-accent-soft text-accent'
                    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5" role="group" aria-label="섹터 필터">
            {['all', ...sectors].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSector(s)}
                aria-pressed={sector === s}
                className={`rounded-full border px-3 py-1 text-[13px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ${
                  sector === s
                    ? 'border-zinc-900 bg-zinc-900 text-white'
                    : 'border-line-strong text-zinc-500 hover:border-zinc-400 hover:text-zinc-800'
                }`}
              >
                {s === 'all' ? '전체 섹터' : s}
              </button>
            ))}
          </div>
        </div>

        <section className="mt-9 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => (
            <GroupCard key={g.key} group={g} />
          ))}
        </section>

        {groups.length === 0 && (
          <p className="mt-16 text-center text-[15px] text-zinc-400">해당 구간의 그룹이 없습니다.</p>
        )}

        <footer className="tnum mt-14 border-t border-line pt-6 text-[13px] text-zinc-400">
          generated_at {data.generated_at} · {data.period.start} ~ {data.period.end}
        </footer>
      </div>
    </div>
  )
}
