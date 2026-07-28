import { THRESHOLD } from './zone.js'

const MAX_Z = 3 // 표시 한계. 이보다 큰 값은 바가 끝까지 찬 상태로 둔다.

// 0을 중심으로 좌우로 뻗는 Z-Score 바. 32행을 훑을 때 숫자보다 먼저 읽힌다.
// 임계 +-1.5 위치에 눈금을 두어 경고 여부를 읽지 않고 판단하게 한다.
export default function ZBar({ z, tone }) {
  const ratio = Math.min(Math.abs(z) / MAX_Z, 1)
  const half = ratio * 50
  const tick = (THRESHOLD / MAX_Z) * 50

  return (
    <div className="relative h-1.5 w-full overflow-hidden rounded-sm bg-raised" aria-hidden="true">
      <span className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
      <span
        className="absolute inset-y-0 w-px bg-line"
        style={{ left: `calc(50% - ${tick}%)` }}
      />
      <span
        className="absolute inset-y-0 w-px bg-line"
        style={{ left: `calc(50% + ${tick}%)` }}
      />
      <span
        className={`absolute inset-y-0 ${tone}`}
        style={
          z >= 0
            ? { left: '50%', width: `${half}%` }
            : { right: '50%', width: `${half}%` }
        }
      />
    </div>
  )
}
