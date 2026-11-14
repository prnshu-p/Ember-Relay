import Icon from './Icon.jsx'
import { monthLabel } from '../lib/format.js'

// The area's name and the period shown, with the downloads.
export default function Header({
  name,
  months,
  span,
  from,
  to,
  onYears,
  period,
  isBox,
  hasRows,
  hasCells,
  onTable,
  onCells,
  onImage,
}) {
  const years = Array.from({ length: span[1] - span[0] + 1 }, (_, i) => span[0] + i)
  const options = years.map((y) => <option key={y}>{y}</option>)
  return (
    <div className="head">
      <div>
        <h1>{name || ' '}</h1>
        <p className="sub">
          Fire hotspots from MODIS and VIIRS as one consistent record,{' '}
          {months ? `${monthLabel(months[0])} to ${monthLabel(months.at(-1))}` : '2000 to today'}. Counts are
          VIIRS-equivalent: what VIIRS records, or would have recorded.
        </p>
      </div>
      <div className="tools">
        <label className="field">
          From
          <select value={from} onChange={(ev) => onYears(+ev.target.value, Math.max(to, +ev.target.value))}>
            {options}
          </select>
        </label>
        <label className="field">
          to
          <select value={to} onChange={(ev) => onYears(Math.min(from, +ev.target.value), +ev.target.value)}>
            {options}
          </select>
        </label>
        <button className="btn" onClick={onTable} disabled={!hasRows}>
          <Icon d="M12 4v11m0 0l-4-4m4 4l4-4M5 20h14" />
          Monthly table
        </button>
        <button
          className="btn"
          onClick={onCells}
          disabled={!hasCells}
          title={
            hasCells
              ? `Hotspots per 25 km cell and month, ${period}${isBox ? '' : '. The cells where this country has most of the hotspots, inside the map frame: cells on a border are shared in the monthly table, so the sums can differ'}`
              : 'Available for areas up to about 40° by 50°'
          }
        >
          Cells
        </button>
        <button className="btn" onClick={onImage} disabled={!hasRows}>
          Calendar image
        </button>
      </div>
    </div>
  )
}
