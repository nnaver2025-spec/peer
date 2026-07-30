import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import EvidenceList from './EvidenceList.jsx'
import ScoreTrend from './ScoreTrend.jsx'
import { topKeywords, zoneOf } from './fomo.js'

const SOURCE_LABELS = {
  naver: '네이버',
  dc_krstock: '디시 한국주식',
  dc_stockus: '디시 미국주식',
  dc_neostock: '디시 주식',
  dc_jusik: '디시 실전투자',
  arca: '아카라이브',
  fmkorea: '에펨코리아',
  ppomppu: '뽐뿌',
  fmkorea_pop: '에펨 인기글',
}

// 접힌 상태의 요약. 점수와 추이만 보여 4개를 나란히 훑게 한다.
function Summary({ index, zone, thin, trend, useDaily }) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="truncate text-[14px] text-ink">{index.label}</h3>
        <span className="shrink-0 text-[11px] text-faint">{index.market}</span>
      </div>

      <div className="mt-2 flex items-start justify-between gap-3">
        <div>
          <div className={`tnum text-[26px] font-medium leading-none ${zone.text}`}>
            {thin ? '—' : index.score.toFixed(1)}
          </div>
          <div className={`mt-1 text-[12px] ${zone.text}`}>{zone.label}</div>
        </div>
        {trend.length > 0 && (
          <div className="w-[92px] shrink-0">
            <ScoreTrend
              points={trend}
              stroke={zone.stroke}
              label={`${index.label} 여론 점수 추이`}
              className="h-8 w-full"
              showCaption={false}
              unit={useDaily ? '일' : '회차'}
            />
          </div>
        )}
      </div>

      <p className="tnum mt-2 text-[11px] text-faint">
        게시글 {index.total_posts}개 · 키워드 {index.hits}회
        {index.lookback_days ? ` · ${index.lookback_days}일` : ''}
      </p>
    </>
  )
}

// 펼친 내용. 카드 아래 전체 폭을 써서 화제글을 넉넉히 펼친다. 카드 안에 넣으면
// 한 칸만 세로로 길어져 나머지 세 칸 옆이 비고, 목록도 좁은 폭에 눌린다.
function Detail({ index, zone, trend, useDaily }) {
  const greed = topKeywords(index.greed_counts, 6)
  const fear = topKeywords(index.fear_counts, 6)
  const evidence = index.evidence ?? []
  const sources = (index.per_source ?? []).filter((s) => s.count > 0 || s.error)

  return (
    <div className="mt-2 rounded-md border border-line-strong bg-surface px-4 py-3">
      <div className="flex flex-col gap-4 lg:flex-row">
        {/* 왼쪽은 맥락(추이·키워드·수집), 오른쪽은 원글. 읽는 순서가 그대로다. */}
        <div className="flex shrink-0 flex-col gap-3 lg:w-[260px]">
          <div>
            <h3 className="text-[13px] text-ink">
              {index.label}
              <span className="ml-1.5 text-[11px] text-faint">{index.market}</span>
            </h3>
          </div>

          {trend.length > 1 && (
            <div>
              <p className="text-[11px] text-faint">
                점수 추이 · 최근 {trend.length}
                {useDaily ? '일' : '회차'}
              </p>
              <div className="mt-1">
                <ScoreTrend
                  points={trend}
                  stroke={zone.stroke}
                  label={`${index.label} 여론 점수 추이`}
                  className="h-12 w-full"
                  showCaption={false}
                  unit={useDaily ? '일' : '회차'}
                />
              </div>
            </div>
          )}

          <div>
            <p className="text-[11px] text-faint">많이 쓰인 말</p>
            <p className="mt-1 text-[12px] text-warn">{greed || '없음'}</p>
            <p className="text-[12px] text-accent">{fear || '없음'}</p>
          </div>

          <div>
            <p className="text-[11px] text-faint">수집 내역</p>
            <ul className="tnum mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
              {sources.map((s) => (
                <li key={s.key} className={s.error ? 'text-faint' : 'text-muted'}>
                  {SOURCE_LABELS[s.key] ?? s.key} {s.error ? '실패' : s.count}
                </li>
              ))}
            </ul>
            {(index.hot_posts > 0 || index.dropped_posts > 0) && (
              <p
                className="tnum mt-1.5 text-[11px] text-faint"
                title="반응이 많은 글은 가중해서 세고, 조회수도 반응도 없는 글은 표본에서 뺍니다"
              >
                인기글 {index.hot_posts}개 · 제외 {index.dropped_posts}개
              </p>
            )}
            <p className="mt-1 text-[11px] text-faint">
              검색어 {index.aliases?.join(' / ')}
            </p>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-faint">
            화제글 {evidence.length}개 · 반응 많은 순
          </p>
          <div className="mt-1 max-h-[420px] overflow-y-auto pr-1">
            <EvidenceList evidence={evidence} />
          </div>
        </div>
      </div>
    </div>
  )
}

function trendOf(index) {
  // 일별이 두 점 이상 쌓이면 그쪽을 쓴다. 한 달 추세가 회차 등락보다 읽기 쉽다.
  const daily = index.daily ?? []
  const useDaily = daily.length > 1
  return { trend: useDaily ? daily : index.history ?? [], useDaily }
}

function IndexCell({ index, open, onToggle, panelId }) {
  const zone = zoneOf(index)
  const { trend, useDaily } = trendOf(index)

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls={panelId}
      className={`flex flex-col rounded-md border px-3.5 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
        open
          ? 'border-line-strong bg-surface'
          : 'border-line hover:border-line-strong'
      }`}
    >
      <Summary
        index={index}
        zone={zone}
        thin={index.score === null}
        trend={trend}
        useDaily={useDaily}
      />
      <span
        className={`mt-2 flex items-center gap-1 text-[11px] ${
          open ? 'text-ink' : 'text-muted'
        }`}
      >
        <ChevronDown
          size={12}
          aria-hidden="true"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        />
        {open ? '접기' : `화제글 ${index.evidence?.length ?? 0}개`}
      </span>
    </button>
  )
}

export default function IndexMood({ indices }) {
  // 한 번에 하나만 펼친다. 카드 높이를 고정해 네 칸을 계속 나란히 비교하게 하고,
  // 펼친 내용은 아래 전체 폭에 둔다.
  const [openKey, setOpenKey] = useState(null)
  if (!indices?.length) return null

  const active = indices.find((i) => i.key === openKey) ?? null
  const panelId = 'index-detail-panel'

  return (
    <div>
      <div className="grid grid-cols-1 items-start gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {indices.map((index) => (
          <IndexCell
            key={index.key}
            index={index}
            open={openKey === index.key}
            panelId={panelId}
            onToggle={() => setOpenKey(openKey === index.key ? null : index.key)}
          />
        ))}
      </div>

      {active && (
        <div id={panelId}>
          <Detail
            index={active}
            zone={zoneOf(active)}
            {...trendOf(active)}
          />
        </div>
      )}
    </div>
  )
}
