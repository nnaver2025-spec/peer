import { useCallback, useEffect, useRef, useState } from 'react'
import { CircleHelp } from 'lucide-react'

const PANEL_WIDTH = 380
const MARGIN = 12

// 탭마다 첫 화면에서 막히는 지점이 다르다. 여기 적는 건 기능 사용법이 아니라
// 숫자를 어떻게 읽는지다. Z-Score나 커플링을 모르면 표가 그냥 숫자 더미로 보인다.
const GUIDES = {
  spread: {
    title: '해외는 갔고 국내는 아직인 그룹 찾기',
    lines: [
      ['Z-Score', '해외 대비 국내가 평소보다 얼마나 벌어졌는지. 음수면 국내가 덜 올랐다는 뜻이다.'],
      ['커플링', '두 그룹이 실제로 같이 움직여온 정도. 막대 세 칸이 강함이고, 약하면 벌어져도 좁혀질 이유가 없다.'],
      ['주도주 · RS', 'RS는 국내 전체에서의 상승률 순위다. 100이 최상위.'],
    ],
    tail: '행을 누르면 구성 종목과 커플링 이력을 볼 수 있다.',
  },
  fomo: {
    title: '커뮤니티가 지금 어느 쪽으로 기울었는지',
    lines: [
      ['여론 심리', '게시글 제목의 탐욕·공포 표현을 센 값. 50이 중립이고 높을수록 과열이다.'],
      ['시장 지표', 'CNN 방식으로 가격·변동성만 본 값. 여론과 어긋나면 한쪽이 앞서간 상태다.'],
      ['표본 부족', '근거가 얇으면 점수를 내지 않고 보류한다.'],
    ],
    tail: '점수보다 원글을 먼저 보는 편이 낫다. 조롱과 환호는 같은 단어를 쓴다.',
  },
  backtest: {
    title: '벌어진 괴리가 실제로 좁혀졌는지',
    lines: [
      ['따라잡음', '과거 같은 상황에서 국내가 기준선까지 되돌아온 비율.'],
      ['95% 구간', '표본이 적으면 넓어진다. 구간이 50%를 걸치면 우연과 구분되지 않는다.'],
      ['수렴 유지', '닿기만 한 것과 그 상태를 지킨 것은 다르다.'],
    ],
    tail: '결론은 좁혀지되 머물지 않는다는 쪽이다. 진입 근거로 쓰기 전에 확인할 것.',
  },
}

export default function TabGuide({ tab }) {
  const [open, setOpen] = useState(false)
  const [style, setStyle] = useState(null)
  const triggerRef = useRef(null)
  const guide = GUIDES[tab]

  const place = useCallback(() => {
    const node = triggerRef.current
    if (!node) return
    const rect = node.getBoundingClientRect()
    const width = Math.min(PANEL_WIDTH, window.innerWidth - MARGIN * 2)
    const left = Math.min(rect.left, window.innerWidth - width - MARGIN)

    setStyle({ left: Math.max(MARGIN, left), width, top: rect.bottom + 8 })
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, place])

  // 탭을 옮기면 내용이 달라지므로 닫는다.
  useEffect(() => setOpen(false), [tab])

  if (!guide) return null

  const toggle = () => {
    if (open) return setOpen(false)
    place()
    setOpen(true)
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={toggle}
        aria-expanded={open}
        title="이 탭 읽는 법"
        aria-label="이 탭 읽는 법"
        className={`rounded p-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          open ? 'text-ink' : 'text-faint hover:text-ink'
        }`}
      >
        <CircleHelp size={14} aria-hidden="true" />
      </button>

      {open && style && (
        <>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="설명 닫기"
            className="fixed inset-0 z-20 cursor-default"
          />
          <div
            style={style}
            className="fixed z-30 rounded-md border border-line-strong bg-surface px-3.5 py-3 shadow-lg"
          >
            <p className="text-[13px] text-ink">{guide.title}</p>
            <dl className="mt-2.5 flex flex-col gap-2">
              {guide.lines.map(([term, desc]) => (
                <div key={term}>
                  <dt className="text-[12px] text-muted">{term}</dt>
                  <dd className="text-[12px] leading-5 text-faint">{desc}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2.5 border-t border-line pt-2 text-[12px] leading-5 text-faint">
              {guide.tail}
            </p>
          </div>
        </>
      )}
    </>
  )
}
