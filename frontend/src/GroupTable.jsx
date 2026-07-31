import { ArrowDown, ArrowUp } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import ZBar from './ZBar.jsx'
import { corrPercent, metaOf } from './coupling.js'
import { isTrusted, ratingTone, signed, zoneOf } from './zone.js'

export const COLUMNS = [
  { id: 'desc', label: '그룹', align: 'left', sortable: true },
  // 섹터는 왼쪽 사이드바 필터로도 확인되므로 가장 마지막에 접는다.
  {
    id: 'sector',
    label: '섹터',
    align: 'left',
    sortable: true,
    foldClass: '@max-[420px]:hidden',
  },
  // 셀 내용이 0을 중심으로 좌우 대칭이라 머리글도 가운데 세운다.
  { id: 'zscore', label: 'Z-Score', align: 'center', sortable: true },
  // Spread는 Z-Score와 같은 괴리를 다른 단위로 보여주므로 가장 좁을 때 접는다.
  {
    id: 'spread',
    label: 'Spread',
    align: 'right',
    sortable: true,
    foldClass: '@max-[560px]:hidden',
  },
  // 목록이 700px 아래로 좁아지면 접는다. 커플링/주도주/RS가 판단에 더 쓰인다.
  { id: 'trend', label: '추이', align: 'left', sortable: false, foldClass: '@max-[700px]:hidden' },
  // 좁을 때 셀은 색 점만 남으므로 헤더 글자도 줄바꿈 없이 흘린다.
  {
    id: 'coupling',
    label: '커플링',
    align: 'left',
    sortable: true,
    shortLabelClass: '@max-[420px]:hidden',
  },
  { id: 'bellwether', label: '주도주', align: 'left', sortable: false },
  { id: 'bellwether_rs_rating', label: 'RS', align: 'right', sortable: true },
]

// 상세 패널이 열리면 목록 폭이 1200px대에서 830px대로 줄어든다. 그때 8개 열을
// 모두 유지하려면 고정 폭이 아니라 컨테이너 폭에 따라 셀이 함께 좁아져야 한다.
const CELL_X = 'px-3 @max-[1000px]:px-2 @max-[420px]:px-1.5'

// 등급이 아니라 실제 강도를 보여준다.
//
// 3칸 막대로 등급만 보이던 때는 차이가 왜곡됐다. 강함 최하 0.31과 보통 최상
// 0.29는 0.02 차이인데 3칸 대 2칸으로 갈렸고, 0.59와 0.31은 두 배 차이인데
// 같은 3칸이었다. 등급은 색으로 남기고 길이와 숫자로 실제 값을 읽게 한다.
function StrengthGauge({ coupling, meta, threshold }) {
  const strength = coupling?.strength
  if (strength == null) {
    return <span className="text-[13px] text-faint">-</span>
  }

  return (
    <span className="flex items-center gap-2">
      <span
        className="relative h-2 w-[46px] shrink-0 overflow-hidden rounded-sm bg-line @max-[560px]:hidden"
        aria-hidden="true"
      >
        <span
          className={`absolute inset-y-0 left-0 ${meta.bar}`}
          style={{ width: `${corrPercent(strength)}%` }}
        />
        {/* 강함 경계에 눈금을 둔다. 0.28이 좋은 값인지 판단할 기준이 없었다.
            ZBar가 임계 +-1.5에 눈금을 두는 것과 같은 방식이다. */}
        {threshold != null && (
          <span
            className="absolute -top-0.5 -bottom-0.5 w-[1.5px] bg-line-strong"
            style={{ left: `${corrPercent(threshold)}%` }}
          />
        )}
      </span>
      {/* 좁으면 게이지를 접고 숫자만 남긴다. 숫자가 값을 그대로 말한다. */}
      <span className="tnum text-[13px]">{strength.toFixed(2)}</span>
    </span>
  )
}

function HeaderCell({ column, sort, onSort }) {
  const active = sort.key === column.id
  const alignClass =
    column.align === 'right'
      ? 'text-right'
      : column.align === 'center'
        ? 'text-center'
        : 'text-left'
  const fold = column.foldClass ?? ''
  // 라벨이 셀보다 길면 세 줄로 쪼개진다. 좁을 때 줄바꿈을 막는다.
  const labelClass = column.shortLabelClass ?? ''

  if (!column.sortable) {
    return (
      <th scope="col" className={`${CELL_X} py-2 font-normal text-faint ${alignClass} ${fold}`}>
        <span className={labelClass}>{column.label}</span>
      </th>
    )
  }

  return (
    <th scope="col" className={`${CELL_X} py-2 font-normal ${alignClass} ${fold}`}>
      <button
        type="button"
        onClick={() => onSort(column.id)}
        aria-label={`${column.label} 기준 정렬`}
        className={`inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          active ? 'text-ink' : 'text-faint'
        }`}
      >
        <span className={labelClass}>{column.label}</span>
        {active &&
          (sort.dir === 'asc' ? (
            <ArrowUp size={12} aria-hidden="true" />
          ) : (
            <ArrowDown size={12} aria-hidden="true" />
          ))}
      </button>
    </th>
  )
}

function Row({ group, selected, onSelect, strongFloor }) {
  const zone = zoneOf(group.zscore)
  const trusted = isTrusted(group)
  const coupling = metaOf(group.coupling)
  const tone = trusted ? zone.text : 'text-faint'

  return (
    <tr
      onClick={() => onSelect(group.key)}
      aria-selected={selected}
      className={`cursor-pointer border-b-[0.5px] border-line/70 transition-colors ${
        selected ? 'bg-accent-soft' : 'hover:bg-surface'
      }`}
    >
      <td
        className={`max-w-[220px] truncate ${CELL_X} py-2.5 @max-[1000px]:max-w-[150px] @max-[560px]:max-w-[108px]`}
      >
        <span className="text-ink">{group.desc}</span>
        {group.alert && (
          <span
            className={`ml-2 align-middle text-[11px] ${zone.text}`}
            title={`${zone.label} · ${zone.note}`}
          >
            {zone.label}
          </span>
        )}
      </td>
      <td className={`${CELL_X} py-2.5 text-muted @max-[420px]:hidden`}>{group.sector}</td>
      {/* Z-Score는 숫자와 바를 한 칸에 묶는다. 떨어뜨리면 시선이 두 번 움직인다. */}
      <td className={`w-[150px] ${CELL_X} py-2.5 @max-[1000px]:w-[96px]`}>
        {/* 바가 0을 중심으로 좌우 대칭이라 숫자도 같은 축에 세운다.
            오른쪽에 붙이면 숫자와 바의 중심이 어긋나 열이 기울어 보인다. */}
        <div className="flex flex-col items-center gap-1.5">
          <span className={`tnum text-[15px] leading-none ${tone}`}>{signed(group.zscore)}</span>
          <ZBar z={group.zscore} tone={trusted ? zone.bar : 'bg-line-strong'} />
        </div>
      </td>
      <td className={`tnum ${CELL_X} py-2.5 text-right text-muted @max-[560px]:hidden`}>
        {signed(group.spread)}
      </td>
      <td className={`w-[120px] ${CELL_X} py-2.5 @max-[1000px]:w-[72px] @max-[700px]:hidden`}>
        <Sparkline
          points={group.history}
          stroke={trusted ? zone.stroke : '--color-line-strong'}
          className="h-6 w-full"
        />
      </td>
      <td
        className={`${CELL_X} py-2.5`}
        title={[
          `커플링 ${coupling.label} · 상관 ${group.coupling?.strength ?? '-'}`,
          strongFloor != null ? `강함 기준 ${strongFloor} (눈금)` : null,
          coupling.note,
        ]
          .filter(Boolean)
          .join(' · ')}
      >
        <span className={`inline-flex items-center ${coupling.chip}`}>
          <StrengthGauge coupling={group.coupling} meta={coupling} threshold={strongFloor} />
        </span>
      </td>
      <td
        className={`max-w-[150px] truncate ${CELL_X} py-2.5 text-[13px] text-muted @max-[1000px]:max-w-[104px] @max-[560px]:max-w-[76px]`}
      >
        {group.bellwether_name ?? '-'}
      </td>
      <td
        className={`tnum ${CELL_X} py-2.5 text-right text-[13px]`}
        title={
          group.bellwether_rs_rating != null
            ? '국내 유니버스 백분위 · 100이 최상위'
            : undefined
        }
      >
        {group.bellwether_rs_rating != null ? (
          <span className={ratingTone(group.bellwether_rs_rating)}>
            {group.bellwether_rs_rating}
          </span>
        ) : (
          <span className="text-faint">-</span>
        )}
      </td>
    </tr>
  )
}

export default function GroupTable({ groups, sort, onSort, selectedKey, onSelect, strongFloor }) {
  return (
    <div
      data-testid="group-table"
      className="@container overflow-x-auto rounded-lg border border-line bg-surface/40"
    >
      <table className="w-full min-w-[320px] border-collapse text-[14px] @max-[1000px]:text-[13px]">
        <thead className="border-b border-line text-[13px] @max-[1000px]:text-[12px]">
          <tr>
            {COLUMNS.map((c) => (
              <HeaderCell key={c.id} column={c} sort={sort} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody>
            {groups.map((g) => (
              <Row
                key={g.key}
                group={g}
                selected={g.key === selectedKey}
                onSelect={onSelect}
                strongFloor={strongFloor}
              />
            ))}
        </tbody>
      </table>
    </div>
  )
}
