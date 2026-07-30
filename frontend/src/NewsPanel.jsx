import { useMemo, useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { bandOf, topKeywords } from './fomo.js'

// 섹터별 뉴스 논조. 커뮤니티 여론과 나란히 두되 점수는 섞지 않는다.
// 커뮤니티는 사람들이 무슨 말을 하는지, 뉴스는 매체가 어떻게 쓰는지 말해준다.

// 상대 시간. 뉴스는 반응 수치가 없어 최신성이 유일한 순서 신호다.
function timeAgo(iso) {
  if (!iso) return null
  const diff = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(diff)) return null
  const hours = Math.floor(diff / 3_600_000)
  if (hours < 1) return '방금'
  if (hours < 24) return `${hours}시간 전`
  return `${Math.floor(hours / 24)}일 전`
}

function Article({ item, side }) {
  const words = side === 'positive' ? item.positive : item.negative
  const tone = side === 'positive' ? 'text-warn/70' : 'text-accent/70'
  const ago = timeAgo(item.published)

  return (
    <li className="border-b border-line/70 last:border-b-0">
      <a
        href={item.url ?? undefined}
        target="_blank"
        rel="noopener noreferrer"
        className={`group flex flex-col gap-0.5 px-1 py-2 transition-colors hover:bg-surface ${
          item.url ? '' : 'pointer-events-none'
        }`}
      >
        <span className="flex items-start gap-1.5">
          <span className="min-w-0 flex-1 text-[13px] text-ink">{item.title}</span>
          {item.url && (
            <ExternalLink
              size={11}
              className="mt-0.5 shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100"
              aria-hidden="true"
            />
          )}
        </span>
        <span className="flex flex-wrap items-center gap-x-2 text-[11px] text-faint">
          {item.source && <span>{item.source}</span>}
          {ago && <span>{ago}</span>}
          <span className={tone}>{words.join(' · ')}</span>
        </span>
      </a>
    </li>
  )
}

function Column({ side, label, items, counts, total }) {
  const accent = side === 'positive' ? 'text-warn' : 'text-accent'

  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline justify-between gap-2 border-b border-line pb-1.5">
        <span className={`text-[13px] ${accent}`}>{label}</span>
        <span className="tnum text-[12px] text-faint">{total}회</span>
      </div>
      <p className={`mt-1.5 truncate text-[12px] ${accent}/80`}>
        {topKeywords(counts, 5) || '\u00a0'}
      </p>
      {items.length === 0 ? (
        <p className="py-4 text-[12px] text-faint">해당 기사가 없습니다.</p>
      ) : (
        <ul className="mt-1 flex flex-col">
          {items.map((item, i) => (
            <Article key={`${item.url ?? item.title}-${i}`} item={item} side={side} />
          ))}
        </ul>
      )}
    </div>
  )
}

// 섹터 탭. 부정이 심한 쪽부터 늘어놓아 위험 신호가 먼저 눈에 들어오게 한다.
function SectorTab({ sector, active, onSelect }) {
  const thin = sector.score === null
  const band = thin ? null : bandOf(sector.score)
  const tone =
    band === 'extreme_greed' || band === 'greed'
      ? 'text-warn'
      : band === 'extreme_fear' || band === 'fear'
        ? 'text-accent'
        : 'text-ink'

  return (
    <button
      type="button"
      onClick={() => onSelect(sector.sector)}
      aria-pressed={active}
      title={
        sector.error
          ? `${sector.sector} · 수집 실패 (${sector.error})`
          : `${sector.sector} · 기사 ${sector.total}건 · 긍정 ${sector.positive_total} / 부정 ${sector.negative_total}`
      }
      className={`flex items-baseline gap-2 rounded-md border px-2.5 py-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
        active
          ? 'border-line-strong bg-raised'
          : 'border-line hover:border-line-strong'
      }`}
    >
      <span className={`text-[13px] ${active ? 'text-ink' : 'text-muted'}`}>
        {sector.sector}
      </span>
      <span className={`tnum text-[13px] ${thin ? 'text-faint' : tone}`}>
        {thin ? '—' : sector.score.toFixed(0)}
      </span>
    </button>
  )
}

export default function NewsPanel({ news }) {
  const sectors = useMemo(
    () =>
      [...(news?.sectors ?? [])].sort(
        (a, b) => (a.score ?? 999) - (b.score ?? 999)
      ),
    [news]
  )
  const [selected, setSelected] = useState(null)

  if (!news || sectors.length === 0) return null

  const active = sectors.find((s) => s.sector === selected) ?? sectors[0]
  const thin = news.score === null
  const band = thin ? null : bandOf(news.score)
  const tone =
    band === 'extreme_greed' || band === 'greed'
      ? 'text-warn'
      : band === 'extreme_fear' || band === 'fear'
        ? 'text-accent'
        : 'text-ink'

  return (
    <section>
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-[14px] text-ink">뉴스 논조</h2>
          <p className="mt-0.5 text-[12px] text-faint">
            섹터별 기사 제목의 방향. 커뮤니티 여론과 따로 센다.
          </p>
        </div>
        <div className="flex items-baseline gap-2.5">
          <span className={`tnum text-[22px] leading-none ${tone}`}>
            {thin ? '—' : news.score.toFixed(1)}
          </span>
          <span className={`text-[13px] ${tone}`}>{news.label}</span>
          <span className="tnum text-[12px] text-faint">
            기사 {news.total}건
            {news.lookback_days ? ` · ${news.lookback_days}일` : ''}
          </span>
        </div>
      </header>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {sectors.map((sector) => (
          <SectorTab
            key={sector.sector}
            sector={sector}
            active={active.sector === sector.sector}
            onSelect={setSelected}
          />
        ))}
      </div>

      {active.error ? (
        <p className="mt-4 text-[13px] text-faint">
          {active.sector} 뉴스를 받지 못했습니다 ({active.error})
        </p>
      ) : (
        <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:gap-8">
          <Column
            side="positive"
            label="긍정 기사"
            items={active.positive}
            counts={active.positive_counts}
            total={active.positive_total}
          />
          <Column
            side="negative"
            label="부정 기사"
            items={active.negative}
            counts={active.negative_counts}
            total={active.negative_total}
          />
        </div>
      )}
    </section>
  )
}
