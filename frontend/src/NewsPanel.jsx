import { useMemo, useState } from 'react'
import NewsColumns from './NewsColumns.jsx'
import { bandOf } from './fomo.js'

// 섹터별 뉴스 논조. 커뮤니티 여론과 나란히 두되 점수는 섞지 않는다.
// 커뮤니티는 사람들이 무슨 말을 하는지, 뉴스는 매체가 어떻게 쓰는지 말해준다.

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
        <div className="mt-4">
          <NewsColumns tone={active} />
        </div>
      )}
    </section>
  )
}
