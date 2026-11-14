import { MONTHS, hs, monthLabel, x3 } from '../lib/format.js'

const ARROWS = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -12, ArrowDown: 12 }

// One row per year, a cell per month. The grid is a single tab stop; the arrow keys move by a month or a year.
// tab: the month that last held the focus.
export default function Calendar({
  years,
  months,
  rows,
  byKey,
  sel,
  tab,
  colorOf,
  onSelect,
  onHover,
  onTab,
}) {
  const tabKey = byKey[tab] ? tab : byKey[sel] ? sel : rows.at(-1)?.month
  const move = (ev) => {
    const d = ARROWS[ev.key],
      r = d && byKey[ev.target.dataset.m]
    if (!r) return
    ev.preventDefault()
    ev.currentTarget.querySelector(`[data-m="${months[r.t + d]}"]`)?.focus()
  }
  return (
    <div
      className="cal fade"
      role="group"
      aria-label="Hotspots per month, a row for each year. The arrow keys move between months."
      onKeyDown={move}
    >
      <div className="cal-r">
        <span />
        {MONTHS.map((m) => (
          <span key={m}>{m[0]}</span>
        ))}
      </div>
      {years.map((y) => (
        <div className="cal-r" key={y}>
          <span className="y">{y}</span>
          {MONTHS.map((_, i) => {
            const key = `${y}-${String(i + 1).padStart(2, '0')}`,
              r = byKey[key]
            if (!r) return <span key={i} className="cell none" />
            const fill = colorOf(r)
            const className = [
              'cell',
              r.source === 'model' && r.count && 'est',
              !fill && 'zero',
              r.partial && 'part',
              sel === key && 'sel',
            ]
            return (
              <button
                key={i}
                data-m={key}
                tabIndex={key === tabKey ? 0 : -1}
                className={className.filter(Boolean).join(' ')}
                style={{ backgroundColor: fill || undefined }}
                aria-label={`${monthLabel(key)}: ${hs(r.count)}${r.anomaly != null ? `, ${x3(r.anomaly)} times the median` : ''}${r.source === 'model' ? ', estimated' : ''}${r.partial ? ', month in progress' : ''}`}
                aria-pressed={sel === key}
                // the read-out follows the mouse and the keyboard focus, never a finger: a tap selects, and the
                // selection has its own read-out
                onPointerEnter={(ev) => ev.pointerType === 'mouse' && onHover(key)}
                onPointerLeave={() => onHover(null)}
                onFocus={(ev) => {
                  onTab(key)
                  if (ev.target.matches(':focus-visible')) onHover(key)
                }}
                onBlur={() => onHover(null)}
                onClick={() => onSelect(sel === key ? null : key)}
              />
            )
          })}
        </div>
      ))}
    </div>
  )
}
