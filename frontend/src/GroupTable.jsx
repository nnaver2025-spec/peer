import { ArrowDown, ArrowUp } from 'lucide-react'
import Sparkline from './Sparkline.jsx'
import ZBar from './ZBar.jsx'
import { metaOf } from './coupling.js'
import { isTrusted, ratingTone, signed, zoneOf } from './zone.js'

export const COLUMNS = [
  { id: 'desc', label: '그룹', align: 'left', sortable: true },
  { id: 'sector', label: '섹터', align: 'left', sortable: true },
  { id: 'zscore', label: 'Z-Score', align: 'right', sortable: true },
  { id: 'spread', label: 'Spread', align: 'right', sortable: true },
  { id: 'trend', label: '추이', align: 'left', sortable: false },
  { id: 'coupling', label: '커플링', align: 'left', sortable: true },
  { id: 'bellwether', label: '주도주', align: 'left', sortable: false },
  { id: 'bellwether_rs_rating', label: 'RS', align: 'right', sortable: true },
]

function HeaderCell({ column, sort, onSort }) {
  const active = sort.key === column.id
  const alignClass = column.align === 'right' ? 'text-right' : 'text-left'

  if (!column.sortable) {
    return (
      <th scope="col" className={`px-3 py-2 font-normal text-faint ${alignClass}`}>
        {column.label}
      </th>
    )
  }

  return (
    <th scope="col" className={`px-3 py-2 font-normal ${alignClass}`}>
      <button
        type="button"
        onClick={() => onSort(column.id)}
        aria-label={`${column.label} 기준 정렬`}
        className={`inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
          active ? 'text-ink' : 'text-faint'
        }`}
      >
        {column.label}
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

function Row({ group, selected, onSelect }) {
  const zone = zoneOf(group.zscore)
  const trusted = isTrusted(group)
  const coupling = metaOf(group.coupling)
  const tone = trusted ? zone.text : 'text-faint'

  return (
    <tr
      onClick={() => onSelect(group.key)}
      aria-selected={selected}
      className={`cursor-pointer border-b border-line/70 transition-colors ${
        selected ? 'bg-accent-soft' : 'hover:bg-surface'
      }`}
    >
      <td className="max-w-[220px] truncate px-3 py-2.5">
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
      <td className="px-3 py-2.5 text-muted">{group.sector}</td>
      {/* Z-Score는 숫자와 바를 한 칸에 묶는다. 떨어뜨리면 시선이 두 번 움직인다. */}
      <td className="w-[150px] px-3 py-2.5">
        <div className="flex flex-col items-end gap-1.5">
          <span className={`tnum text-[15px] leading-none ${tone}`}>{signed(group.zscore)}</span>
          <ZBar z={group.zscore} tone={trusted ? zone.bar : 'bg-line-strong'} />
        </div>
      </td>
      <td className="tnum px-3 py-2.5 text-right text-muted">{signed(group.spread)}</td>
      <td className="w-[120px] px-3 py-2.5">
        <Sparkline
          points={group.history}
          stroke={trusted ? zone.stroke : '--color-line-strong'}
          className="h-6 w-full"
        />
      </td>
      <td className="px-3 py-2.5">
        <span className={`inline-flex items-center gap-1.5 text-[13px] ${coupling.chip}`}>
          <span className={`size-1.5 rounded-full ${coupling.dot}`} aria-hidden="true" />
          {coupling.label}
        </span>
      </td>
      <td className="max-w-[150px] truncate px-3 py-2.5 text-[13px] text-muted">
        {group.bellwether_name ?? '-'}
      </td>
      <td
        className="tnum px-3 py-2.5 text-right text-[13px]"
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

export default function GroupTable({ groups, sort, onSort, selectedKey, onSelect }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface/40">
      <table className="w-full min-w-[900px] border-collapse text-[14px]">
        <thead className="border-b border-line text-[13px]">
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
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
