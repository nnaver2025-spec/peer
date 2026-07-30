import EvidencePopover from './EvidencePopover.jsx'
import ScoreTrend from './ScoreTrend.jsx'
import { topKeywords, zoneOf } from './fomo.js'

// 지수 한 칸. 종목보다 표본이 두꺼워 점수를 크게 세우고 추이를 옆에 붙인다.
function IndexCell({ index }) {
  const zone = zoneOf(index)
  const thin = index.score === null
  const greed = topKeywords(index.greed_counts, 3)
  const fear = topKeywords(index.fear_counts, 3)
  const evidence = index.evidence ?? []
  // 일별이 두 점 이상 쌓이면 그쪽을 쓴다. 한 달 추세가 회차 등락보다 읽기 쉽다.
  const daily = index.daily ?? []
  const useDaily = daily.length > 1
  const trend = useDaily ? daily : index.history ?? []

  return (
    <article
      className="flex flex-col gap-2.5 rounded-md border border-line px-3.5 py-3"
      title={`검색어: ${index.aliases?.join(' / ')}`}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="truncate text-[14px] text-ink">{index.label}</h3>
        <span className="shrink-0 text-[11px] text-faint">{index.market}</span>
      </header>

      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`tnum text-[26px] font-medium leading-none ${zone.text}`}>
            {thin ? '—' : index.score.toFixed(1)}
          </div>
          <div className={`mt-1 text-[12px] ${zone.text}`}>{zone.label}</div>
        </div>
        {trend.length > 0 && (
          <div className="w-[104px] shrink-0">
            <ScoreTrend
              points={trend}
              stroke={zone.stroke}
              label={`${index.label} 여론 점수 추이`}
              className="h-8 w-full"
              unit={useDaily ? '일' : '회차'}
            />
          </div>
        )}
      </div>

      <div className="flex flex-col gap-0.5 text-[12px]">
        <span className="truncate text-warn">{greed || '\u00a0'}</span>
        <span className="truncate text-accent">{fear || '\u00a0'}</span>
      </div>

      <p className="tnum text-[11px] text-faint">
        게시글 {index.total_posts}개 · 키워드 {index.hits}회
        {index.lookback_days && ` · ${index.lookback_days}일`}
      </p>
      {(index.hot_posts > 0 || index.dropped_posts > 0) && (
        <p
          className="tnum text-[11px] text-faint"
          title="반응이 많은 글은 가중해서 세고, 조회수도 반응도 없는 글은 표본에서 뺍니다"
        >
          인기글 {index.hot_posts}개 · 제외 {index.dropped_posts}개
        </p>
      )}

      {evidence.length > 0 && (
        <div className="self-start">
          <EvidencePopover evidence={evidence} label={`${index.label} 원글`}>
            <span className="border-b border-dotted border-line-strong">
              원글 {evidence.length}개
            </span>
          </EvidencePopover>
        </div>
      )}
    </article>
  )
}

export default function IndexMood({ indices }) {
  if (!indices?.length) return null

  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      {indices.map((index) => (
        <IndexCell key={index.key} index={index} />
      ))}
    </div>
  )
}
