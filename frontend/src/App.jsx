import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  LayoutGrid,
  List,
  Moon,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Sun,
  X,
} from 'lucide-react'
import GroupTable from './GroupTable.jsx'
import GroupCard from './GroupCard.jsx'
import DetailPanel from './DetailPanel.jsx'
import FomoTab from './FomoTab.jsx'
import BacktestTab from './BacktestTab.jsx'
import Freshness from './Freshness.jsx'
import Disclaimer from './Disclaimer.jsx'
import TabGuide from './TabGuide.jsx'
import { THRESHOLD, isTrusted } from './zone.js'
import { clearLegacySkin, useTheme } from './theme.js'

function ThemeToggle({ theme, onToggle }) {
  const next = theme === 'dark' ? '라이트' : '다크'
  return (
    <button
      type="button"
      onClick={onToggle}
      title={`${next} 모드로 전환`}
      aria-label={`${next} 모드로 전환`}
      className="rounded-md p-1.5 text-faint transition-colors hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
    >
      {theme === 'dark' ? (
        <Sun size={15} aria-hidden="true" />
      ) : (
        <Moon size={15} aria-hidden="true" />
      )}
    </button>
  )
}

const TABS = [
  // id는 ?tab= 링크와 localStorage에 저장된 값이라 라벨만 바꾼다.
  { id: 'spread', label: '괴리' },
  { id: 'backtest', label: '기록' },
  { id: 'fomo', label: '민심' },
]

const FILTERS = [
  { id: 'all', label: '전체' },
  { id: 'trusted', label: '커플링 유효' },
  { id: 'alert', label: '경고' },
  { id: 'overshoot', label: '오버슈팅' },
  { id: 'undershoot', label: '언더슈팅' },
]

const TAB_KEY = 'peer:tab'
const VIEW_KEY = 'peer:view'
const DEFAULT_TAB = 'spread'

// 사이드바와 모바일 시트가 같은 목록을 쓴다. 한쪽만 고치는 실수를 막는다.
function FilterGroups({ sector, sectors, onSector }) {
  const itemClass = (active) =>
    `block w-full rounded-md px-2 py-1.5 text-left text-[14px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
      active ? 'bg-raised text-ink' : 'text-muted hover:bg-surface hover:text-ink'
    }`

  return (
    <div>
      <p className="px-2 pb-1.5 text-[12px] text-faint">섹터</p>
        {['all', ...sectors].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSector(s)}
            aria-pressed={sector === s}
            className={itemClass(sector === s)}
          >
            {s === 'all' ? '전체 섹터' : s}
          </button>
        ))}
      </div>
  )
}

// 정렬 값 추출. 커플링은 실제 강도로 비교한다. 등급으로 묶으면 같은 등급
// 안에서 0.28까지 벌어진 차이가 정렬에 반영되지 않는다.
function sortValue(group, key) {
  if (key === 'coupling') return group.coupling?.strength ?? -1
  if (key === 'zscore' || key === 'spread') return Math.abs(group[key])
  // 등급이 없는 그룹은 항상 뒤로 보낸다.
  if (key === 'bellwether_rs_rating') return group[key] ?? -1
  return group[key]
}

function compare(a, b, sort) {
  const va = sortValue(a, sort.key)
  const vb = sortValue(b, sort.key)
  let diff
  if (typeof va === 'string') diff = va.localeCompare(vb, 'ko')
  else diff = va - vb
  return sort.dir === 'asc' ? diff : -diff
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [theme, toggleTheme] = useTheme()
  // 실험 중 저장된 스킨 값을 한 번 정리한다.
  useEffect(() => {
    clearLegacySkin()
  }, [])
  const [filter, setFilter] = useState('all')
  const [sector, setSector] = useState('all')
  const [query, setQuery] = useState('')
  // 우선순위는 URL > 지난 방문 기록 > 스프레드. 첫 방문은 항상 스프레드로 연다.
  const [tab, setTab] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('tab')
    if (TABS.some((t) => t.id === fromUrl)) return fromUrl
    const saved = localStorage.getItem(TAB_KEY)
    if (TABS.some((t) => t.id === saved)) return saved
    return DEFAULT_TAB
  })
  // 뷰 선택은 로컬에 남겨 다음 방문에도 유지한다. ?view=card로도 열 수 있다.
  const [view, setView] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('view')
    if (fromUrl === 'card' || fromUrl === 'table') return fromUrl
    return localStorage.getItem(VIEW_KEY) ?? 'table'
  })
  // 선택 그룹을 URL 해시에 실어 새로고침/공유에도 상세가 유지되게 한다.
  const [selectedKey, setSelectedKey] = useState(
    () => window.location.hash.replace(/^#/, '') || null
  )
  const [sort, setSort] = useState({ key: 'zscore', dir: 'desc' })
  const isSpread = tab === DEFAULT_TAB
  // 좁은 화면에는 사이드바가 없다. 필터를 여는 경로를 하나 둔다.
  const [filterOpen, setFilterOpen] = useState(false)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}dashboard_data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  // Esc로 닫는다. 필터 시트가 열려 있으면 그쪽이 먼저다.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      if (filterOpen) setFilterOpen(false)
      else setSelectedKey(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [filterOpen])

  useEffect(() => {
    // 상세 해시는 스프레드 전용이다. 다른 탭에서 남으면 링크의 탭과 해시가 어긋난다.
    const next = isSpread && selectedKey ? `#${selectedKey}` : ''
    if (window.location.hash !== next) {
      const { pathname, search } = window.location
      window.history.replaceState(null, '', `${pathname}${search}${next}`)
    }
  }, [selectedKey, isSpread])

  useEffect(() => {
    localStorage.setItem(VIEW_KEY, view)
  }, [view])

  useEffect(() => {
    localStorage.setItem(TAB_KEY, tab)
    // 주소도 함께 맞춘다. ?tab=fomo로 들어온 뒤 다른 탭으로 옮겼을 때 주소가
    // 그대로면 새로고침이나 링크 공유에서 의도와 다른 탭이 열린다.
    const { pathname, search, hash } = window.location
    const params = new URLSearchParams(search)
    params.set('tab', tab)
    const next = `${pathname}?${params}${hash}`
    if (`${pathname}${search}${hash}` !== next) {
      window.history.replaceState(null, '', next)
    }
  }, [tab])

  const sectors = useMemo(
    () => (data ? [...new Set(data.groups.map((g) => g.sector))] : []),
    [data]
  )

  const groups = useMemo(() => {
    if (!data) return []
    let all = [...data.groups]
    if (sector !== 'all') all = all.filter((g) => g.sector === sector)
    if (filter === 'trusted') all = all.filter(isTrusted)
    if (filter === 'alert') all = all.filter((g) => g.alert)
    if (filter === 'overshoot') all = all.filter((g) => g.zscore >= THRESHOLD)
    if (filter === 'undershoot') all = all.filter((g) => g.zscore <= -THRESHOLD)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      all = all.filter((g) => {
        const haystack = [
          g.desc,
          g.sector,
          g.bellwether_name ?? '',
          ...g.lead_tickers.map((t) => t.label),
          ...g.lag_tickers.map((t) => t.label),
        ]
        return haystack.some((v) => v.toLowerCase().includes(q))
      })
    }
    return all.sort((a, b) => compare(a, b, sort))
  }, [data, filter, sector, query, sort])

  // 필터를 바꿔도 열어둔 상세가 닫히지 않도록 전체 목록에서 찾는다.
  const selected = useMemo(
    () => data?.groups.find((g) => g.key === selectedKey) ?? null,
    [data, selectedKey]
  )

  const handleSelect = (key) =>
    setSelectedKey((prev) => (prev === key ? null : key))

  const onSort = (key) =>
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: key === 'desc' || key === 'sector' ? 'asc' : 'desc' }
    )

  if (error) {
    return (
      <main className="relative flex min-h-screen items-center justify-center px-6 text-center">
        <div className="absolute right-4 top-4">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">dashboard_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python peer_tracker.py</p>
        </div>
      </main>
    )
  }

  if (!data) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <RefreshCw className="animate-spin text-line-strong" aria-hidden="true" />
      </main>
    )
  }

  // 필터를 걸면 함께 움직여야 하는 값이다. 헤더에 있을 때는 전체 값만 보여줘서
  // 방산만 골라도 '그룹 32'가 그대로였다.
  const alertCount = groups.filter((g) => g.alert).length
  const trustedCount = groups.filter(isTrusted).length

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-line bg-surface px-5 py-2.5">
        {/* 헤더에는 탭과 무관하게 유효한 것만 둔다. Z 기준이나 그룹 수는
            스프레드 전용이라 그 탭 안으로 내렸다. */}
        <div className="flex min-w-0 items-center gap-x-2.5">
          <button
            type="button"
            onClick={() => {
              setTab(DEFAULT_TAB)
              setSelectedKey(null)
            }}
            title="갭(스프레드) 탭으로 이동"
            className="flex items-baseline gap-x-2.5 rounded text-left transition-opacity hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <h1 className="text-[22px] font-medium leading-tight text-ink">엇박</h1>
            <p className="truncate text-[13px] text-faint max-[560px]:hidden">
              해외가 먼저 간 자리
            </p>
          </button>
          {/* 갱신 주기와 맞춰야 한다. Pages 무료 빌드 한도 때문에 워크플로를
              2시간 주기로 두었다(.github/workflows/update-data.yml). 0.5를 쓰면
              정상 갱신인데도 1시간 뒤부터 경고가 뜬다. */}
          <Freshness generatedAt={data.generated_at} intervalHours={2} />
        </div>

        <div className="flex w-full items-center justify-between gap-3 border-t border-line pt-2.5 sm:w-auto sm:border-t-0 sm:pt-0">
          {/* 활성 탭만 배경을 채우는 알약형 스위처. 밑줄보다 시선이 덜 분산된다. */}
          <nav aria-label="지표 선택" className="flex items-center gap-0.5 rounded-lg bg-raised p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                aria-current={tab === t.id ? 'page' : undefined}
                className={`rounded-md px-3 py-1.5 text-[13px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                  tab === t.id
                    ? 'bg-canvas text-ink shadow-sm ring-1 ring-line'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-0.5">
            <TabGuide tab={tab} />
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {isSpread && (
        <nav className="hidden w-[200px] shrink-0 flex-col gap-6 overflow-y-auto border-r border-line px-3 py-4 lg:flex">
          <FilterGroups
            sector={sector}
            sectors={sectors}
            onSector={setSector}
          />
        </nav>
        )}

        {tab === 'fomo' ? (
          <FomoTab />
        ) : tab === 'backtest' ? (
          <BacktestTab />
        ) : (
        <main className="flex min-w-0 flex-1 flex-col">
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

            <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 max-sm:w-full">
              {FILTERS.map((f) => {
                const active = filter === f.id
                const badgeStyle =
                  f.id === 'alert'
                    ? active
                      ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/40 font-medium'
                      : 'text-faint hover:text-ink hover:bg-surface border-transparent'
                    : f.id === 'overshoot'
                      ? active
                        ? 'bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/40 font-medium'
                        : 'text-faint hover:text-ink hover:bg-surface border-transparent'
                      : f.id === 'undershoot'
                        ? active
                          ? 'bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border-cyan-500/40 font-medium'
                          : 'text-faint hover:text-ink hover:bg-surface border-transparent'
                        : f.id === 'trusted'
                          ? active
                            ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/40 font-medium'
                            : 'text-faint hover:text-ink hover:bg-surface border-transparent'
                          : active
                            ? 'bg-raised text-ink border-line-strong font-medium'
                            : 'text-faint hover:text-ink hover:bg-surface border-transparent'

                const labelWithIcon =
                  f.id === 'alert'
                    ? '⚠️ 경고'
                    : f.id === 'trusted'
                      ? '⚡ 커플링 유효'
                      : f.id === 'overshoot'
                        ? '🔥 오버슈팅'
                        : f.id === 'undershoot'
                          ? '🧊 언더슈팅'
                          : f.label

                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilter(f.id)}
                    aria-pressed={active}
                    className={`shrink-0 rounded-full border px-2.5 py-1 text-[12px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${badgeStyle}`}
                  >
                    {labelWithIcon}
                  </button>
                )
              })}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                data-testid="mobile-filter-toggle"
                onClick={() => setFilterOpen(true)}
                aria-expanded={filterOpen}
                title="필터"
                aria-label="필터"
                className="relative rounded-md border border-line p-1.5 text-faint transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 lg:hidden"
              >
                <SlidersHorizontal size={14} aria-hidden="true" />
                {(filter !== 'all' || sector !== 'all') && (
                  <span
                    className="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-accent"
                    aria-hidden="true"
                  />
                )}
              </button>
              <dl
                data-testid="spread-counts"
                className="tnum flex items-baseline gap-3 text-[13px] sm:gap-4"
              >
                <div className="flex items-baseline gap-1.5">
                  <dt className="text-faint">그룹</dt>
                  <dd className="text-ink">{groups.length}</dd>
                </div>
                <div className="flex items-baseline gap-1.5">
                  <dt className="text-faint">경고</dt>
                  <dd className={alertCount ? 'text-warn' : 'text-ink'}>{alertCount}</dd>
                </div>
                <div className="flex items-baseline gap-1.5 max-[420px]:hidden">
                  <dt className="text-faint">커플링</dt>
                  <dd className="text-ink">{trustedCount}</dd>
                </div>
              </dl>
              <div
                role="group"
                aria-label="보기 방식"
                className="flex rounded-md border border-line p-0.5"
              >
                <button
                  type="button"
                  onClick={() => setView('table')}
                  aria-pressed={view === 'table'}
                  title="표로 보기"
                  className={`rounded p-1.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                    view === 'table' ? 'bg-raised text-ink' : 'text-faint hover:text-ink'
                  }`}
                >
                  <List size={14} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => setView('card')}
                  aria-pressed={view === 'card'}
                  title="카드로 보기"
                  className={`rounded p-1.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                    view === 'card' ? 'bg-raised text-ink' : 'text-faint hover:text-ink'
                  }`}
                >
                  <LayoutGrid size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {groups.length === 0 ? (
              <p className="mt-16 text-center text-[14px] text-faint">
                조건에 맞는 그룹이 없습니다.
              </p>
            ) : view === 'table' ? (
              <GroupTable
                groups={groups}
                sort={sort}
                onSort={onSort}
                selectedKey={selectedKey}
                onSelect={handleSelect}
                strongFloor={data.coupling_tiers?.strong}
              />
            ) : (
              <section className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {groups.map((g) => (
                  <GroupCard key={g.key} group={g} onSelect={handleSelect} />
                ))}
              </section>
            )}

            <footer className="tnum mt-8 text-[12px] text-faint">
              {data.z_window}일 Z · 임계 |Z| {data.alert_threshold} · {data.period.start} ~{' '}
              {data.period.end}
              <Disclaimer />
            </footer>
          </div>
        </main>
        )}

        {isSpread && filterOpen && (
          <div className="fixed inset-0 z-30 lg:hidden">
            <button
              type="button"
              onClick={() => setFilterOpen(false)}
              aria-label="필터 닫기"
              className="absolute inset-0 bg-canvas/70"
            />
            <div
              data-testid="mobile-filter-sheet"
              className="absolute inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t-lg border-t border-line bg-surface px-3 pb-6 pt-3"
            >
              <div className="mb-2 flex items-center justify-between px-2">
                <p className="text-[14px] text-ink">필터</p>
                <button
                  type="button"
                  onClick={() => setFilterOpen(false)}
                  aria-label="필터 닫기"
                  title="닫기"
                  className="rounded p-1 text-faint transition-colors hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
              <div className="flex flex-col gap-5">
                <FilterGroups
                  sector={sector}
                  sectors={sectors}
                  onSector={(v) => {
                    setSector(v)
                    setFilterOpen(false)
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* 좁은 화면에서는 목록을 덮는 오버레이로, 넓은 화면에서는 우측 고정 패널로 둔다. */}
        {isSpread && selected && (
          <div className="fixed inset-0 z-20 bg-canvas md:static md:z-auto md:w-[360px] md:shrink-0">
            <DetailPanel group={selected} onClose={() => setSelectedKey(null)} />
          </div>
        )}
      </div>
    </div>
  )
}
