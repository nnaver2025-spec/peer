import { ExternalLink } from 'lucide-react'
import { topKeywords } from './fomo.js'

// 긍정/부정 기사를 두 열로 나눠 보여준다. 섹터 패널과 지수 카드가 함께 쓴다.

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
          {item.provider && (
            <span
              className={`rounded px-1 py-0.2 text-[10px] font-medium ${
                item.provider === 'naver'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                  : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
              }`}
            >
              {item.provider === 'naver' ? '네이버' : '구글'}
            </span>
          )}
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

export default function NewsColumns({ tone, gap = 'lg:gap-8' }) {
  if (!tone) return null

  return (
    <div className={`flex flex-col gap-6 lg:flex-row ${gap}`}>
      <Column
        side="positive"
        label="긍정 기사"
        items={tone.positive ?? []}
        counts={tone.positive_counts}
        total={tone.positive_total}
      />
      <Column
        side="negative"
        label="부정 기사"
        items={tone.negative ?? []}
        counts={tone.negative_counts}
        total={tone.negative_total}
      />
    </div>
  )
}
