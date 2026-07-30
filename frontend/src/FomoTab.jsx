import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'
import FomoGauge from './FomoGauge.jsx'
import EvidencePopover from './EvidencePopover.jsx'
import IndexMood from './IndexMood.jsx'
import MarketMood from './MarketMood.jsx'
import ScoreTrend from './ScoreTrend.jsx'
import { failedSources, topKeywords, zoneOf } from './fomo.js'

const COLUMNS = [
  { id: 'name', label: '종목', align: 'left', sortable: true },
  { id: 'group_desc', label: '그룹', align: 'left', sortable: true },
  { id: 'score', label: '여론 점수', align: 'right', sortable: true },
  { id: 'label', label: '구간', align: 'left', sortable: false },
  { id: 'trend', label: '점수 추이', align: 'left', sortable: false },
  { id: 'keywords', label: '주요 키워드', align: 'left', sortable: false },
  { id: 'total_posts', label: '수집', align: 'right', sortable: true },
]

function compare(a, b, sort) {
  const va = a[sort.key]
  const vb = b[sort.key]
  const diff = typeof va === 'string' ? va.localeCompare(vb, 'ko') : va - vb
  return sort.dir === 'asc' ? diff : -diff
}

function HeaderCell({ column, sort, onSort }) {
  const alignClass = column.align === 'right' ? 'text-right' : 'text-left'
  if (!column.sortable) {
    return (
      <th scope="col" className={`px-3 py-2 font-normal text-faint ${alignClass}`}>
        {column.label}
      </th>
    )
  }

  const active = sort.key === column.id
  return (
    <th scope="col" className={`px-3 py-2 font-normal ${alignClass}`}>
      <button
        type="button"
        onClick={() => onSort(column.id)}
        aria-label={`${column.label} 기준 정렬`}
        className={`inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          active ? 'text-ink' : 'text-faint'
        }`}
      >
        {column.label}
        {active &&
          (sort.dir === 'asc' ? (
            <ArrowUp size={12} aria-hidden="true" />
          ) : (
            <ArrowDown size={12} aria-hidden="true" />
          ))}
      </button>
    </th>
  )
}

function Row({ stock }) {
  const zone = zoneOf(stock)
  const failed = failedSources(stock)
  const greed = topKeywords(stock.greed_counts)
  const fear = topKeywords(stock.fear_counts)
  const evidence = stock.evidence ?? []
  const daily = stock.daily ?? []
  const useDaily = daily.length > 1
  const trend = useDaily ? daily : stock.history ?? []

  return (
    <tr className="border-b border-line/70 transition-colors hover:bg-surface">
      <td className="max-w-[180px] px-3 py-2.5">
        {evidence.length > 0 ? (
          <EvidencePopover evidence={evidence} label={`${stock.name} 원글`}>
            <span className="truncate border-b border-dotted border-line-strong text-[14px] text-ink">
              {stock.name}
            </span>
          </EvidencePopover>
        ) : (
          <span className="truncate text-ink">{stock.name}</span>
        )}
      </td>
      <td className="max-w-[160px] truncate px-3 py-2.5 text-muted">{stock.group_desc}</td>
      {/* 점수와 게이지를 한 칸에 묶는다. 떨어뜨리면 시선이 두 번 움직인다. */}
      <td className="w-[140px] px-3 py-2.5">
        <div className="flex flex-col items-end gap-1.5">
          <span className={`tnum text-[15px] ${zone.text}`}>{stock.score.toFixed(1)}</span>
          <FomoGauge score={stock.score} bar={zone.bar} />
        </div>
      </td>
      <td className="px-3 py-2.5">
        <span className={`text-[13px] ${zone.text}`} title={zone.note}>
          {zone.label}
        </span>
      </td>
      <td className="w-[110px] px-3 py-2.5">
        <ScoreTrend
          points={trend}
          stroke={zone.stroke}
          label={`${stock.name} 여론 점수 추이`}
          className="h-6 w-full"
          showCaption={false}
          unit={useDaily ? '일' : '회차'}
        />
      </td>
      <td className="max-w-[240px] px-3 py-2.5 text-[13px]">
        {greed && <span className="text-warn">{greed}</span>}
        {greed && fear && <span className="text-line-strong"> · </span>}
        {fear && <span className="text-accent">{fear}</span>}
        {!greed && !fear && <span className="text-faint">없음</span>}
      </td>
      <td className="tnum px-3 py-2.5 text-right">
        <span className="text-muted">{stock.total_posts}</span>
        {failed > 0 && (
          <span className="ml-1.5 text-[12px] text-faint" title={`${failed}개 사이트 수집 실패`}>
            -{failed}
          </span>
        )}
      </td>
    </tr>
  )
}

// 좁은 화면용. 표를 그대로 밀어넣으면 열이 쪼개져 헤더가 세로로 눕는다.
function Card({ stock }) {
  const zone = zoneOf(stock)
  const failed = failedSources(stock)
  const greed = topKeywords(stock.greed_counts)
  const fear = topKeywords(stock.fear_counts)
  const evidence = stock.evidence ?? []
  const daily = stock.daily ?? []
  const useDaily = daily.length > 1
  const trend = useDaily ? daily : stock.history ?? []

  return (
    <article className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] text-ink">{stock.name}</h3>
          <p className="truncate text-[13px] text-faint">{stock.group_desc}</p>
        </div>
        <div className="shrink-0 text-right">
          <div className={`tnum text-[22px] leading-none ${zone.text}`}>
            {stock.score.toFixed(1)}
          </div>
          <div className={`mt-1 text-[12px] ${zone.text}`}>{zone.label}</div>
        </div>
      </header>

      <FomoGauge score={stock.score} bar={zone.bar} />

      {trend.length > 1 && (
        <ScoreTrend
          points={trend}
          stroke={zone.stroke}
          label={`${stock.name} 여론 점수 추이`}
          className="h-8 w-full"
          unit={useDaily ? '일' : '회차'}
        />
      )}

      <div className="flex flex-wrap items-baseline gap-x-2 text-[13px]">
        {greed && <span className="text-warn">{greed}</span>}
        {fear && <span className="text-accent">{fear}</span>}
        {!greed && !fear && <span className="text-faint">키워드 없음</span>}
      </div>

      <p className="tnum text-[12px] text-faint">
        수집 {stock.total_posts}개{failed > 0 && ` · 실패 ${failed}곳`}
        {stock.hot_posts > 0 && ` · 인기글 ${stock.hot_posts}개`}
      </p>

      {evidence.length > 0 && (
        <div className="self-start">
          <EvidencePopover evidence={evidence} label={`${stock.name} 원글`}>
            <span className="border-b border-dotted border-line-strong">
              원글 {evidence.length}개
            </span>
          </EvidencePopover>
        </div>
      )}
    </article>
  )
}

export default function FomoTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [sector, setSector] = useState(null)
  const [sort, setSort] = useState({ key: 'score', dir: 'desc' })

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}fomo_data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  const stocks = useMemo(() => {
    if (!data) return []
    let all = [...data.stocks]
    if (sector) all = all.filter((s) => (s.sector || '기타') === sector)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      all = all.filter((s) =>
        [s.name, s.group_desc, s.sector].some((v) => (v ?? '').toLowerCase().includes(q))
      )
    }
    return all.sort((a, b) => compare(a, b, sort))
  }, [data, query, sector, sort])

  const onSort = (key) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: key === 'name' || key === 'group_desc' ? 'asc' : 'desc' }
    )

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">fomo_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python fomo_watch.py</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <RefreshCw className="animate-spin text-line-strong" aria-hidden="true" />
      </div>
    )
  }

  // 점검용 부분 수집이 덮이거나 첫 실행이 덜 끝난 상태를 구분해 알린다.
  // 빈 화면만 보여주면 고장인지 데이터가 없는 건지 알 수 없다.
  if (!data.stocks?.length) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">수집된 종목이 없습니다</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python fomo_watch.py</p>
          <p className="mt-2 text-[12px] text-faint">
            마지막 갱신 {data.generated_at}
          </p>
        </div>
      </div>
    )
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      {data.market && (
        <MarketMood
          market={data.market}
          minHits={data.min_sentiment_hits ?? 10}
          sector={sector}
          onSector={setSector}
          indices={data.indices}
          gauge={data.market_gauge}
        />
      )}

      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-2.5">
        <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1.5 focus-within:border-line-strong sm:max-w-[320px]">
          <Search size={14} className="shrink-0 text-faint" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="종목, 그룹, 섹터"
            aria-label="종목 검색"
            className="min-w-0 flex-1 bg-transparent text-[14px] text-ink placeholder:text-faint focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="검색어 지우기"
              className="shrink-0 rounded text-faint transition-colors hover:text-ink"
            >
              <X size={13} aria-hidden="true" />
            </button>
          )}
        </label>

        <dl className="tnum flex items-baseline gap-5 text-[13px]">
          <div className="flex items-baseline gap-1.5">
            <dt className="text-faint">종목</dt>
            <dd className="text-ink">{stocks.length}</dd>
          </div>
          {sector && (
            <button
              type="button"
              onClick={() => setSector(null)}
              className="flex items-center gap-1 rounded text-[13px] text-muted transition-colors hover:text-ink"
            >
              {sector}
              <X size={12} aria-hidden="true" />
            </button>
          )}
        </dl>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {stocks.length === 0 ? (
          <p className="mt-16 text-center text-[14px] text-faint">
            조건에 맞는 종목이 없습니다.
          </p>
        ) : (
          <>
          {/* 좁은 화면은 카드, 넓은 화면은 표. 열 폭이 부족하면 표는 읽히지 않는다. */}
          <div className="flex flex-col gap-3 lg:hidden">
            {stocks.map((stock) => (
              <Card key={stock.key} stock={stock} />
            ))}
          </div>

          <table className="hidden w-full border-collapse text-[14px] lg:table">
            <thead className="border-b border-line text-[13px]">
              <tr>
                {COLUMNS.map((column) => (
                  <HeaderCell key={column.id} column={column} sort={sort} onSort={onSort} />
                ))}
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock) => (
                <Row key={stock.key} stock={stock} />
              ))}
            </tbody>
          </table>
          </>
        )}

        <footer className="tnum mt-8 text-[12px] text-faint">
          generated_at {data.generated_at} · {data.interval_hours}시간 주기 ·{' '}
          {data.sources.length}개 게시판
          {data.lookback_days && ` · 최근 ${data.lookback_days}일`}
          {data.us_index_lookback_days &&
            ` (미국 지수 ${data.us_index_lookback_days}일)`}
          {data.daily_points && ` · 추이 최대 ${data.daily_points}일`}
        </footer>
      </div>
    </main>
  )
}
