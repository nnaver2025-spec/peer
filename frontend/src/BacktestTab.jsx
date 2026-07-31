import { Fragment, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDown, ArrowUp, RefreshCw, Search, X } from 'lucide-react'
import { isTrusted, signed } from './zone.js'
import EpisodeChart from './EpisodeChart.jsx'
import Disclaimer from './Disclaimer.jsx'

const COLUMNS = [
  { id: 'desc', label: '그룹', align: 'left', sortable: true },
  { id: 'sector', label: '섹터', align: 'left', sortable: true },
  { id: 'episodes', label: '괴리 사례', align: 'right', sortable: true },
  { id: 'half_rate', label: '따라잡음 (95% 구간)', align: 'right', sortable: true },
  { id: 'median_recovery', label: '중위 회복률', align: 'right', sortable: true },
]

// 그룹별 표본은 30~55건뿐이라 비율 하나로 순위를 만들 수 없다. 등급을 매기는 대신
// 신뢰구간을 함께 보여주고 색은 쓰지 않는다. 구간이 겹치는지는 눈으로 확인한다.

function summaryOf(group, horizon) {
  return group.summary[`h${horizon}`] ?? {}
}

function sortValue(group, key, horizon) {
  const s = summaryOf(group, horizon)
  if (key === 'episodes') return group.summary.resolved
  if (key === 'half_rate') return s.half_rate ?? -1
  if (key === 'median_recovery') return s.median_recovery ?? -99
  return group[key]
}

function compare(a, b, sort, horizon) {
  const va = sortValue(a, sort.key, horizon)
  const vb = sortValue(b, sort.key, horizon)
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

// 결론 카드. 표본 1,183건의 합산 통계는 오차가 ±3%p로 좁아 단정할 수 있다.
// 그룹별 순위(표본 40건, ±14%p)와 달리 이쪽이 이 탭에서 가장 단단한 근거다.
// 닿음/유지는 신호 이후 최장 구간(60일) 경로 전체를 훑어 재는 값이라
// 20일/60일 버튼과 무관하다. 라벨에 구간을 박아 혼동을 막는다.
function Verdict({ stats, horizon, maxHorizon }) {
  const s = stats[`h${horizon}`] ?? {}
  // 합산 표본은 1,000건을 넘어 구간이 ±3%p다. 여기서는 50%보다 낮다고 단정할 수
  // 있으므로 색을 쓴다. 그룹별(표본 40건)과 달리 근거가 충분하다.
  const belowChance = s.high != null && s.high < 50

  return (
    <section className="shrink-0 border-b border-line px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-[15px] text-ink">괴리는 좁혀지되 머물지 않는다</h2>
        <span className="tnum text-[12px] text-faint">
          확정 사례 {stats.resolved}건 · 그룹 {stats.groups}개
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
        <Figure
          label={`수렴에 닿음 (${maxHorizon}일)`}
          value={stats.touched_rate}
          ci={stats.touched_ci}
          note={`${maxHorizon}일 안에 기준선까지 한 번이라도 되돌아옴`}
        />
        <Figure
          label={`수렴 유지 (${maxHorizon}일)`}
          value={stats.held_rate}
          ci={stats.held_ci}
          note={`${maxHorizon}일 시점에도 그 상태를 지킴`}
          tone="text-warn"
        />
        <Figure
          label={`${horizon}일 절반 회복`}
          value={s.half_rate}
          ci={[s.low, s.high]}
          note="괴리를 절반 이상 좁힌 비율"
          tone={belowChance ? 'text-warn' : 'text-ink'}
        />
      </div>

      {stats.touched_rate != null && stats.held_rate != null && (
        <p className="mt-3 text-[13px] text-muted">
          <span className="tnum text-ink">
            {(stats.touched_rate - stats.held_rate).toFixed(0)}%p
          </span>
          가 수렴에 닿았다가 되돌아갔다. 절반 회복까지는 중위{' '}
          <span className="tnum text-ink">{stats.median_days_to_half}일</span>이 걸렸지만,{' '}
          {horizon}일 시점 절반 회복은{' '}
          <span className="tnum text-ink">{Math.round(s.half_rate)}%</span>
          로 우연(50%)보다 확실히 낮다.
        </p>
      )}
    </section>
  )
}

// 값과 신뢰구간을 한 덩어리로 둔다. 구간을 떼어놓으면 숫자만 읽고 지나간다.
function Figure({ label, value, ci, note, tone = 'text-ink' }) {
  const [low, high] = ci ?? []
  return (
    <div className="min-w-[128px]">
      <p className="text-[12px] text-faint" title={note}>
        {label}
      </p>
      <p className={`tnum text-[24px] leading-tight ${tone}`}>
        {value != null ? `${Math.round(value)}%` : '-'}
      </p>
      <p className="tnum text-[11px] text-faint">
        {low != null ? `95% ${Math.round(low)}~${Math.round(high)}%` : '표본 부족'}
      </p>
    </div>
  )
}

// 무효 결과. "괴리가 크면 더 좁혀진다" 같은 직관을 데이터로 반박하는 근거다.
function Breakdown({ breakdown, horizon }) {
  const axesData = breakdown?.[`h${horizon}`]
  if (!axesData) return null
  const axes = [
    { key: 'direction', label: '방향' },
    { key: 'gap', label: '괴리 크기' },
    { key: 'tier', label: '커플링 등급' },
  ]

  // 축 안의 구간이 모두 겹치면 "차이 없음"이 확인된 것이다. 하나라도 벌어지면
  // 그렇게 단정할 수 없으므로 문구를 바꾼다(20일 괴리 크기 39% vs 30%가 그 예).
  const overlaps = (items) =>
    items.every((a) => items.every((b) => a.low <= b.high && b.low <= a.high))
  const allSame = axes.every(({ key }) => overlaps(axesData[key] ?? []))

  return (
    <section className="shrink-0 border-b border-line px-5 py-3">
      <p className="text-[12px] text-faint">
        {allSame
          ? `어느 조건으로 갈라도 결과가 같다 (${horizon}일 기준)`
          : `조건별 대비 (${horizon}일 기준)`}{' '}
        — 구간이 서로 겹치면 차이가 없다는 뜻
      </p>
      <div className="mt-2 flex flex-wrap gap-x-8 gap-y-2">
        {axes.map(({ key, label }) => (
          <div key={key} className="text-[13px]">
            <p className="text-[12px] text-faint">{label}</p>
            <div className="tnum mt-0.5 flex flex-wrap gap-x-4">
              {(axesData[key] ?? []).map((s) => (
                <span key={s.label} className="text-muted">
                  {s.label}{' '}
                  <span className="text-ink">
                    {s.rate != null ? `${Math.round(s.rate)}%` : '-'}
                  </span>
                  {s.low != null && (
                    <span className="text-faint">
                      {' '}
                      ({Math.round(s.low)}~{Math.round(s.high)})
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function Row({ group, horizon, expanded, onToggle, chartBefore, zWindow }) {
  const s = summaryOf(group, horizon)

  return (
    <>
      <tr
        onClick={() => onToggle(group.key)}
        aria-expanded={expanded}
        className={`cursor-pointer border-b border-line/70 transition-colors ${
          expanded ? 'bg-accent-soft' : 'hover:bg-surface'
        }`}
      >
        <td className="max-w-[220px] truncate px-3 py-2.5 text-ink">{group.desc}</td>
        <td className="px-3 py-2.5 text-muted">{group.sector}</td>
        <td className="tnum px-3 py-2.5 text-right text-muted">{group.summary.resolved}</td>
        {/* 비율과 구간을 붙여 둔다. 비율만 보면 표본 40건의 57%를 확정으로 읽는다. */}
        <td className="tnum px-3 py-2.5 text-right">
          {s.half_rate != null ? (
            <>
              <span className="text-ink">{Math.round(s.half_rate)}%</span>
              <span className="ml-1.5 text-[12px] text-faint">
                {Math.round(s.low)}~{Math.round(s.high)}
              </span>
            </>
          ) : (
            <span className="text-faint">-</span>
          )}
        </td>
        <td className="tnum px-3 py-2.5 text-right text-muted">
          {s.median_recovery != null ? signed(s.median_recovery) : '-'}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-line/70 bg-surface">
          <td colSpan={COLUMNS.length} className="px-3 py-3">
            <EpisodeList
              group={group}
              horizon={horizon}
              chartBefore={chartBefore}
              zWindow={zWindow}
            />
          </td>
        </tr>
      )}
    </>
  )
}

// 개별 사례. 합산 비율만 보면 "언제 어떤 괴리가 어떻게 끝났는지"가 사라진다.
function EpisodeList({ group, horizon, chartBefore, zWindow }) {
  const current = group.current
  // 현재 괴리를 기본으로 펼친다. 목록에 들어오면 가장 먼저 볼 값이다.
  const [openDate, setOpenDate] = useState(current ? current.date : null)
  const episodes = [...group.episodes]
    .filter((e) => e.resolved)
    .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap))
    .slice(0, 8)

  if (episodes.length === 0 && !current) {
    return <p className="text-[13px] text-faint">확정된 괴리 사례가 없습니다.</p>
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[12px] text-faint">
        현재 괴리 + 과거 사례 {episodes.length}건 · 시점을 누르면 전후 차트 · 표본{' '}
        {group.sample_from}~ ({group.sample_days}거래일)
      </p>
      <table className="tnum w-full text-[13px]">
        <thead className="text-faint">
          <tr>
            <th scope="col" className="py-1 text-left font-normal">시점</th>
            <th scope="col" className="py-1 text-left font-normal">방향</th>
            <th
              scope="col"
              className="py-1 text-right font-normal"
              title="60일 이동평균 기준선과의 차이. 차트의 괴리는 구간 기준이라 값이 다르다."
            >
              괴리 (기준선 대비)
            </th>
            <th scope="col" className="py-1 text-right font-normal">{horizon}일 회복률</th>
            <th scope="col" className="py-1 text-right font-normal">국내-해외</th>
            <th scope="col" className="py-1 text-right font-normal">절반까지</th>
          </tr>
        </thead>
        <tbody>
          {current && (
            <Fragment key="current">
              <tr className="border-t border-line/60">
                <td className="py-1">
                  <button
                    type="button"
                    onClick={() =>
                      setOpenDate(openDate === current.date ? null : current.date)
                    }
                    aria-expanded={openDate === current.date}
                    className={`rounded border-b border-dotted border-line-strong transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                      openDate === current.date ? 'text-ink' : 'text-muted'
                    }`}
                  >
                    {current.date}
                  </button>
                  <span
                    className="ml-2 text-[11px] text-accent"
                    title="백테스트와 같은 60일 기준선으로 잰 값. 스프레드 탭은 20일 기준이라 값이 다르다."
                  >
                    현재
                  </span>
                </td>
                <td className="py-1 text-muted">
                  {current.direction === 'undershoot' ? '국내 뒤처짐' : '국내 앞섬'}
                </td>
                <td className="py-1 text-right text-ink">{signed(current.gap, 1)}%p</td>
                {/* 현재 건은 아직 결과가 없다. 대신 지금 Z와 조건 충족 여부를 놓는다. */}
                <td className="py-1 text-right text-faint" title="결과는 아직 확정되지 않았다">
                  진행 중
                </td>
                <td className="py-1 text-right text-muted">Z {signed(current.z)}</td>
                <td className="py-1 text-right">
                  {current.active ? (
                    <span className="text-warn" title={`|Z| ≥ ${1.5} 이고 괴리 ≥ 5%p`}>
                      괴리 확대
                    </span>
                  ) : (
                    <span className="text-faint">정상 범위</span>
                  )}
                </td>
              </tr>
              {openDate === current.date && (
                <tr className="border-t border-line/60">
                  <td colSpan={6} className="py-3">
                    {/* 같은 그룹의 Z가 스프레드 탭과 다를 수 있다. 툴팁만으로는 놓치므로
                        차트 위에 기준을 적어 둔다(실측 10개 그룹에서 판단이 갈렸다). */}
                    <p className="mb-2 text-[12px] text-faint">
                      백테스트 기준: {zWindow}일 이동평균 · 6년 로그 상대지수. 스프레드 탭은
                      20일 기준 · 최근 6개월 정규화라 같은 그룹의 Z가 다르게 나온다.
                    </p>
                    <EpisodeChart
                      group={group}
                      episode={current}
                      // 현재 건은 신호 이후 구간이 없다. 앞 구간을 넓혀
                      // 오른쪽 절반이 빈 채로 그려지는 것을 막는다.
                      before={chartBefore + horizon}
                      after={horizon}
                    />
                  </td>
                </tr>
              )}
            </Fragment>
          )}
          {episodes.map((e) => {
            const h = e.horizons[horizon] ?? {}
            const caught = (h.recovery ?? 0) >= 0.5
            const open = openDate === e.date
            return (
              <Fragment key={e.date}>
              <tr className="border-t border-line/60">
                <td className="py-1">
                  <button
                    type="button"
                    onClick={() => setOpenDate(open ? null : e.date)}
                    aria-expanded={open}
                    className={`rounded border-b border-dotted border-line-strong transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                      open ? 'text-ink' : 'text-muted'
                    }`}
                  >
                    {e.date}
                  </button>
                </td>
                <td className="py-1 text-muted">
                  {e.direction === 'undershoot' ? '국내 뒤처짐' : '국내 앞섬'}
                </td>
                <td className="py-1 text-right text-muted">{signed(e.gap, 1)}%p</td>
                <td className={`py-1 text-right ${caught ? 'text-good' : 'text-warn'}`}>
                  {h.recovery != null ? signed(h.recovery) : '-'}
                </td>
                <td className="py-1 text-right text-muted">
                  {h.excess != null ? `${signed(h.excess, 1)}%p` : '-'}
                </td>
                <td className="py-1 text-right text-muted">
                  {e.days_to_half != null ? `${e.days_to_half}일` : '미도달'}
                </td>
              </tr>
              {open && (
                <tr className="border-t border-line/60">
                  <td colSpan={6} className="py-3">
                    <EpisodeChart
                      group={group}
                      episode={e}
                      before={chartBefore}
                      after={horizon}
                    />
                  </td>
                </tr>
              )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function BacktestTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [horizon, setHorizon] = useState(60)
  const [onlyCoupled, setOnlyCoupled] = useState(true)
  const [expanded, setExpanded] = useState(null)
  // 기본 정렬을 표본 크기로 둔다. 비율 내림차순이 기본이면 표본 40건의 1위가
  // 가장 좋은 그룹처럼 읽히는데, 그 순위는 기간을 나누면 뒤집힌다.
  const [sort, setSort] = useState({ key: 'episodes', dir: 'desc' })

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}backtest_data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((json) => {
        setData(json)
        setHorizon(json.horizons.at(-1))
      })
      .catch((err) => setError(err.message))
  }, [])

  const groups = useMemo(() => {
    if (!data) return []
    let all = [...data.groups]
    if (onlyCoupled) all = all.filter(isTrusted)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      all = all.filter((g) =>
        [g.desc, g.sector, ...g.lead_labels, ...g.lag_labels].some((v) =>
          (v ?? '').toLowerCase().includes(q)
        )
      )
    }
    return all.sort((a, b) => compare(a, b, sort, horizon))
  }, [data, query, onlyCoupled, sort, horizon])

  const onSort = (key) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: key === 'desc' || key === 'sector' ? 'asc' : 'desc' }
    )

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">backtest_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python catchup_backtest.py</p>
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

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <Verdict
        stats={onlyCoupled ? data.coupled : data.overall}
        horizon={horizon}
        maxHorizon={data.horizons.at(-1)}
      />
      <Breakdown
        breakdown={(onlyCoupled ? data.coupled : data.overall).breakdown}
        horizon={horizon}
      />

      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-2.5">
        <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1.5 focus-within:border-line-strong sm:max-w-[320px]">
          <Search size={14} className="shrink-0 text-faint" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="그룹, 섹터, 종목"
            aria-label="그룹 검색"
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

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setOnlyCoupled((v) => !v)}
            aria-pressed={onlyCoupled}
            className={`rounded-md border border-line px-2.5 py-1.5 text-[13px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
              onlyCoupled ? 'bg-raised text-ink' : 'text-muted hover:text-ink'
            }`}
          >
            커플링 유효만
          </button>
          <div role="group" aria-label="측정 구간" className="flex rounded-md border border-line p-0.5">
            {data.horizons.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setHorizon(h)}
                aria-pressed={horizon === h}
                className={`tnum rounded px-2 py-1 text-[13px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                  horizon === h ? 'bg-raised text-ink' : 'text-faint hover:text-ink'
                }`}
              >
                {h}일
              </button>
            ))}
          </div>
          <span className="tnum text-[13px] text-faint">{groups.length}개</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {groups.length === 0 ? (
          <p className="mt-16 text-center text-[14px] text-faint">
            조건에 맞는 그룹이 없습니다.
          </p>
        ) : (
          // 모바일에서 표가 뷰포트를 넘겨 마지막 열이 잘렸다. 가로로 밀어 볼 수 있게 둔다.
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[14px]">
              <thead className="border-b border-line text-[13px]">
                <tr>
                  {COLUMNS.map((column) => (
                    <HeaderCell key={column.id} column={column} sort={sort} onSort={onSort} />
                  ))}
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <Row
                    key={g.key}
                    group={g}
                    horizon={horizon}
                    expanded={expanded === g.key}
                    onToggle={(key) => setExpanded((prev) => (prev === key ? null : key))}
                    chartBefore={data.chart_before ?? 60}
                    zWindow={data.z_window}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="tnum mt-8 text-[12px] text-faint">
          기준선 {data.z_window}일 이동평균 · |Z| ≥ {data.threshold} · 최소 괴리{' '}
          {data.min_gap}%p · 회복률 1.0이면 기준선까지 완전히 되돌아온 것 · 판정은 Wilson
          95% 구간이 50%를 벗어날 때만 확정
          <br />
          generated_at {data.generated_at} · {data.period.start} ~ {data.period.end}
          <Disclaimer />
        </footer>
      </div>
    </main>
  )
}
