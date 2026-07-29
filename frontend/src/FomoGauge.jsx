// 0~100 여론 게이지. 50(중립) 위치에 눈금을 두어 어느 쪽으로 기울었는지 먼저 읽히게 한다.
export default function FomoGauge({ score, bar }) {
  return (
    <div className="relative h-1.5 w-full overflow-hidden rounded-sm bg-raised" aria-hidden="true">
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
