import { useMemo, useState } from 'react'
import EvidenceList from './EvidenceList.jsx'

// 반응이 검증된 화제글 목록.
//
// 종목별 여론 점수를 대신해 이 자리에 둔다. 종목 점수는 키워드 표본이 얇아
// (30종목 중 24종목이 키워드 3개 차이로 구간이 뒤집혔다) 소수점을 보여줄 근거가
// 없었다. 화제글은 추천 중위 86, 최대 201로 반응이 실제로 검증된 표본이다.
const FILTERS = [
  { id: 'all', label: '전체' },
  { id: 'greed', label: '탐욕' },
  { id: 'fear', label: '공포' },
  { id: 'plain', label: '태그 없음' },
]

function sideOf(item) {
  if (!item.greed.length && !item.fear.length) return 'plain'
  return item.greed.length > item.fear.length ? 'greed' : 'fear'
}

export default function HotFeed({ feed, sources }) {
  const [filter, setFilter] = useState('all')
  const [source, setSource] = useState('all')

  const counts = useMemo(() => {
    const acc = { all: feed.length, greed: 0, fear: 0, plain: 0 }
    feed.forEach((item) => {
      acc[sideOf(item)] += 1
    })
    return acc
  }, [feed])

  // 피드에 실제로 들어온 게시판만 버튼으로 노출한다.
  const boards = useMemo(() => {
    const keys = new Set(feed.map((i) => i.source))
    return (sources ?? []).filter((s) => keys.has(s.key))
  }, [feed, sources])

  const rows = useMemo(
    () =>
      feed.filter(
        (item) =>
          (filter === 'all' || sideOf(item) === filter) &&
          (source === 'all' || item.source === source)
      ),
    [feed, filter, source]
  )

  if (!feed.length) return null

  return (
    <section className="mt-8 flex flex-col border-t border-line pt-5">
      <header className="flex flex-wrap items-center justify-between gap-3 pb-2">
        <div>
          <h2 className="text-[14px] text-ink">시장 화제글</h2>
          <p className="mt-0.5 text-[12px] text-faint">
            커뮤니티에서 추천을 많이 받은 글. 종목 검색으로는 안 잡히는 분위기를 담는다.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`tnum rounded-md border px-2 py-1 text-[12px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                filter === f.id
                  ? 'border-line-strong bg-raised text-ink'
                  : 'border-line text-muted hover:border-line-strong'
              }`}
            >
              {f.label} {counts[f.id]}
            </button>
          ))}
        </div>
      </header>

      {boards.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5 pb-2">
          <button
            type="button"
            onClick={() => setSource('all')}
            aria-pressed={source === 'all'}
            className={`rounded px-1.5 py-0.5 text-[12px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
              source === 'all' ? 'text-ink' : 'text-faint hover:text-muted'
            }`}
          >
            모든 게시판
          </button>
          {boards.map((b) => (
            <button
              key={b.key}
              type="button"
              onClick={() => setSource(b.key)}
              aria-pressed={source === b.key}
              className={`rounded px-1.5 py-0.5 text-[12px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                source === b.key ? 'text-ink' : 'text-faint hover:text-muted'
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
      )}

      {rows.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-faint">
          조건에 맞는 글이 없습니다.
        </p>
      ) : (
        <EvidenceList evidence={rows} />
      )}
    </section>
  )
}
