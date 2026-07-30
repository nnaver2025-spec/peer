import { useState } from 'react'
import { topKeywords, zoneOf } from './fomo.js'
import EvidencePopover from './EvidencePopover.jsx'
import Freshness from './Freshness.jsx'
import IndexMood from './IndexMood.jsx'
import MarketGauge from './MarketGauge.jsx'
import ScoreTrend from './ScoreTrend.jsx'

// 시장 심리 눈금. 0~100 위에 현재 위치와 20/50/80 기준선을 둔다.
function MoodBar({ score, bar }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-sm bg-raised" aria-hidden="true">
      <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
      <span className="absolute inset-y-0 w-px bg-line" style={{ left: '20%' }} />
      <span className="absolute inset-y-0 w-px bg-line" style={{ left: '80%' }} />
      <span
        className={`absolute inset-y-0 w-[3px] rounded-sm ${bar}`}
        style={{ left: `calc(${score}% - 1.5px)` }}
      />
    </div>
  )
}

// 섹터 한 칸. 이름과 점수를 한 줄에 붙여 여러 섹터를 한눈에 훑게 한다.
//
// 종목 표를 뺀 뒤로는 눌러서 걸러낼 대상이 없다. 클릭 대신 호버 설명만 남긴다.
function SectorChip({ sector, minHits }) {
  const thin = sector.score === null
  const zone = zoneOf(sector)

  return (
    <span
      title={
        thin
          ? `${sector.sector} · 키워드 ${sector.hits}회 (최소 ${minHits}회 필요)`
          : `${sector.sector} · ${zone.label} · 탐욕 ${sector.greed_total} / 공포 ${sector.fear_total} · ${sector.stocks}종목`
      }
      className="flex items-baseline gap-2 rounded-md border border-line px-2.5 py-1"
    >
      <span className="text-[13px] text-muted">{sector.sector}</span>
      <span className={`tnum text-[14px] ${thin ? 'text-faint' : zone.text}`}>
        {thin ? '—' : sector.score.toFixed(0)}
      </span>
    </span>
  )
}

export default function MarketMood({
  market,
  minHits,
  minIndexHits,
  indices,
  gauge,
  generatedAt,
  intervalHours,
}) {
  const zone = zoneOf(market)
  const thin = market.score === null
  const { greed_leaning: greedLeaning, fear_leaning: fearLeaning, stocks } = market
  const evidence = market.evidence ?? []
  // 짧은 등락은 회차로, 추세는 일별로 본다. 하나만 두면 다른 쪽을 못 본다.
  const [range, setRange] = useState('daily')
  const daily = market.daily ?? []
  const trend = range === 'daily' && daily.length ? daily : market.history ?? []

  return (
    <section className="border-b border-line px-5 py-4">
      <div className="flex flex-wrap items-start gap-x-10 gap-y-5">
        <div className="min-w-[220px]">
          <div className="flex items-baseline gap-2">
            <p className="text-[12px] text-faint">여론 심리</p>
            <Freshness generatedAt={generatedAt} intervalHours={intervalHours} />
          </div>
          <div className="mt-1 flex items-baseline gap-2.5">
            <span className={`tnum text-[34px] font-medium leading-none ${zone.text}`}>
              {thin ? '—' : market.score.toFixed(1)}
            </span>
            <span className={`text-[14px] ${zone.text}`}>
              {thin ? `표본 부족 (${market.hits}/${minHits})` : zone.label}
            </span>
          </div>
          <div className="mt-3 w-[240px]">
            {!thin && <MoodBar score={market.score} bar={zone.bar} />}
          </div>
          <p className="tnum mt-2 text-[12px] text-faint">
            키워드 {market.hits}회 · 게시글 {market.total_posts}개
          </p>
          {(market.hot_posts > 0 || market.dropped_posts > 0) && (
            <p
              className="tnum mt-1 text-[12px] text-faint"
              title="반응이 많은 글은 가중해서 세고, 조회수도 반응도 없는 글은 표본에서 뺍니다"
            >
              인기글 {market.hot_posts}개 · 제외 {market.dropped_posts}개
            </p>
          )}
        </div>

        {gauge && <MarketGauge gauge={gauge} />}

        <div className="min-w-[170px]">
          <p className="text-[12px] text-faint">기울기</p>
          <dl className="tnum mt-2 flex flex-col gap-1.5 text-[13px]">
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-warn">탐욕 우세</dt>
              <dd className="text-ink">{greedLeaning}종목</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-accent">공포 우세</dt>
              <dd className="text-ink">{fearLeaning}종목</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-faint">중립</dt>
              <dd className="text-muted">{stocks - greedLeaning - fearLeaning}종목</dd>
            </div>
          </dl>
        </div>

        <div className="min-w-[200px] flex-1">
          <p className="text-[12px] text-faint">많이 쓰인 말</p>
          <div className="mt-2 flex flex-col gap-1.5 text-[13px]">
            <p className="truncate text-warn">
              {topKeywords(market.keyword_totals?.greed, 5) || '없음'}
            </p>
            <p className="truncate text-accent">
              {topKeywords(market.keyword_totals?.fear, 5) || '없음'}
            </p>
          </div>
          {evidence.length > 0 && (
            <div className="mt-2">
              <EvidencePopover evidence={evidence} label="시장 전체 원글">
                <span className="border-b border-dotted border-line-strong">
                  원글 {evidence.length}개
                </span>
              </EvidencePopover>
            </div>
          )}
        </div>

        {trend.length > 0 && (
          <div className="min-w-[170px]">
            <div className="flex items-baseline gap-2">
              <p className="text-[12px] text-faint">여론 추이</p>
              {daily.length > 0 && market.history?.length > 0 && (
                <span className="flex gap-1 text-[11px]">
                  {[
                    ['daily', '일별'],
                    ['session', '회차'],
                  ].map(([id, text]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setRange(id)}
                      aria-pressed={range === id}
                      className={`rounded px-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
                        range === id ? 'text-ink' : 'text-faint hover:text-muted'
                      }`}
                    >
                      {text}
                    </button>
                  ))}
                </span>
              )}
            </div>
            <div className="mt-1 w-[170px]">
              <ScoreTrend
                points={trend}
                stroke={zone.stroke}
                label="시장 여론 점수 추이"
                className="h-10 w-full"
                unit={range === 'daily' ? '일' : '회차'}
              />
            </div>
          </div>
        )}
      </div>

      <div className="mt-5">
        <p className="text-[12px] text-faint">섹터별 (공포 순)</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {market.sectors.map((s) => (
            <SectorChip key={s.sector} sector={s} minHits={minHits} />
          ))}
        </div>
      </div>

      {indices?.length > 0 && (
        <div className="mt-5">
          <p className="text-[12px] text-faint">지수</p>
          <div className="mt-2">
          <IndexMood indices={indices} minHits={minIndexHits} />
          </div>
        </div>
      )}
    </section>
  )
}
