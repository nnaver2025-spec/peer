import { ExternalLink, Eye, MessageSquare, ThumbsUp } from 'lucide-react'

// 소스 키 -> 짧은 표시명. 목록에서 어느 게시판 글인지 한눈에 알게 한다.
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

// 1,234 / 1.2만. 목록 폭이 좁아 만 단위는 접는다.
function formatCount(value) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}만`
  return value.toLocaleString('ko-KR')
}

function Reaction({ icon: Icon, value, title }) {
  if (value === null || value === undefined) return null
  return (
    <span className="inline-flex items-center gap-0.5" title={title}>
      <Icon size={10} aria-hidden="true" />
      {formatCount(value)}
    </span>
  )
}

function Row({ item }) {
  const words = [...item.greed, ...item.fear]
  // 피드에는 키워드가 안 잡힌 글도 들어온다. 방향이 없는 글을 탐욕으로 칠하면
  // 실제로 없는 신호를 만들어낸다.
  const side = words.length === 0
    ? null
    : item.greed.length >= item.fear.length
      ? 'greed'
      : 'fear'
  const sideText =
    side === 'greed' ? 'text-warn' : side === 'fear' ? 'text-accent' : 'text-faint'

  return (
    <li className="border-b border-line/70 last:border-b-0">
      <a
        href={item.url ?? undefined}
        target="_blank"
        rel="noopener noreferrer"
        className={`group flex items-start gap-2.5 px-1 py-2 transition-colors hover:bg-surface ${
          item.url ? '' : 'pointer-events-none'
        }`}
      >
        <span
          className={`mt-0.5 w-[22px] shrink-0 text-[11px] ${sideText}`}
          title={
            side === 'greed'
              ? '탐욕 신호'
              : side === 'fear'
                ? '공포 신호'
                : '감정 키워드가 잡히지 않은 화제글'
          }
        >
          {side === 'greed' ? '탐욕' : side === 'fear' ? '공포' : '·'}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className="truncate text-[13px] text-ink">{item.title}</span>
            {item.url && (
              <ExternalLink
                size={11}
                className="shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100"
                aria-hidden="true"
              />
            )}
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-faint">
            {item.stock && <span>{item.stock}</span>}
            <span>{SOURCE_LABELS[item.source] ?? item.source}</span>
            <Reaction icon={Eye} value={item.views} title="조회수" />
            <Reaction icon={ThumbsUp} value={item.votes} title="추천" />
            <Reaction icon={MessageSquare} value={item.comments} title="댓글" />
            {words.length > 0 && (
              <span className={side === 'greed' ? 'text-warn/70' : 'text-accent/70'}>
                {words.join(' · ')}
              </span>
            )}
          </span>
        </span>
      </a>
    </li>
  )
}

export default function EvidenceList({ evidence }) {
  if (!evidence?.length) {
    return (
      <p className="py-3 text-[13px] text-faint">
        키워드가 잡힌 글이 없습니다.
      </p>
    )
  }

  return (
    <ul className="flex flex-col">
      {evidence.map((item, i) => (
        <Row key={`${item.url ?? item.title}-${i}`} item={item} />
      ))}
    </ul>
  )
}
