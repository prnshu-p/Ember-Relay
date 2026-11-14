import { useState } from 'react'
import Icon from './Icon.jsx'
import MapView from './MapView.jsx'
import { SEQ, TREND } from '../lib/colors.js'
import { monthLabel } from '../lib/format.js'
import { fitBox } from '../lib/world.js'

const FIELDS = ['West', 'South', 'East', 'North']

function coordError(b) {
  if (!b.every(Number.isFinite)) return 'Fill in all four fields.'
  if (Math.abs(b[1]) > 85 || Math.abs(b[3]) > 85 || Math.abs(b[0]) > 180 || b[2] < -180 || b[2] > b[0] + 360)
    return 'Latitude runs from -85 to 85, West from -180 to 180. East may pass 180 to cross the date line (170 to 190).'
  if (!fitBox(b)) return 'West must be less than East, and South less than North, by at least 0.25°.'
  return null
}

const toBox = (texts) => texts.map((x) => (x === '' ? NaN : +x))

// The fields keep what is typed; the area follows on leaving a field or pressing Enter, and only when all four make
// a box, so half-typed numbers never become the area.
function Coords({ area, bbox, onChange }) {
  // own: this edit already has its history entry, so the next changes replace it
  const [draft, setDraft] = useState(null) // { for: area, v: four texts, own }
  const mine = draft?.for === area
  const typed = mine ? draft.v : bbox.map(String)
  const apply = () => {
    const b = toBox(typed)
    const a = coordError(b) ? area : `box:${fitBox(b).join(',')}`
    if (mine && a !== area) {
      onChange(a, !draft.own)
      setDraft({ for: a, v: typed, own: true })
    }
  }
  return (
    <details style={{ marginTop: 12 }}>
      <summary>Enter coordinates</summary>
      <div className="coords">
        {FIELDS.map((label, i) => (
          <label key={label}>
            {label}
            <input
              type="number"
              step="0.25"
              min={i % 2 ? -85 : -180}
              max={i % 2 ? 85 : i ? 540 : 180}
              value={typed[i]}
              onChange={(ev) =>
                setDraft({ for: area, v: typed.with(i, ev.target.value), own: mine && draft.own })
              }
              onBlur={apply}
              onKeyDown={(ev) => ev.key === 'Enter' && apply()}
            />
          </label>
        ))}
      </div>
      <p className="error" role="status" style={{ marginTop: 8 }}>
        {mine && coordError(toBox(typed))}
      </p>
    </details>
  )
}

export default function MapCard({
  layer,
  onLayer,
  theme,
  area,
  bbox,
  world,
  cells,
  busy,
  months,
  sel,
  yrs,
  huge,
  drawing,
  onDrawing,
  onArea,
  onClearMonth,
  onCoords,
}) {
  const trend = layer === 'trend'
  const lastYear = months?.findLast((m) => m.endsWith('-12'))?.slice(0, 4) ?? ''
  return (
    <section className="card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Where</h2>
        <div className="seg" role="group" aria-label="What the map shows">
          <button aria-pressed={!trend} onClick={() => onLayer('count')}>
            Hotspots
          </button>
          <button aria-pressed={trend} onClick={() => onLayer('trend')}>
            Trend
          </button>
        </div>
      </div>
      <MapView
        bbox={bbox}
        world={world}
        outline={area.startsWith('box:')}
        cells={cells}
        colors={trend ? TREND[theme] : SEQ[theme]}
        drawing={drawing}
        busy={busy}
        trend={trend}
        label={trend ? `2003–${lastYear}` : sel ? monthLabel(sel) : yrs}
        onBox={(b) => onArea(`box:${b.join(',')}`)}
      />
      <p className="note mapnote" style={{ marginTop: 10 }}>
        {trend ? (
          <>
            Where fire is changing: the trend of yearly hotspots per decade, as a share of a typical year.
            Blue is less fire, red is more, grey is little change. Raw counts joined at 2012 could not show
            this.
            {sel && (
              <>
                {' '}
                The trend is made of whole years: the month you picked, {monthLabel(sel)}, plays no part in
                it.
              </>
            )}
          </>
        ) : sel ? (
          <>
            Showing <b>{monthLabel(sel)}</b>.{' '}
            <button className="link" onClick={onClearMonth}>
              Show {yrs}
            </button>
          </>
        ) : (
          <>Hotspots per cell, {yrs}. Click a month in the calendar to map it.</>
        )}
        {huge &&
          ' This area is too large for 25 km cells: it is summed from 1° boxes, without MODIS counts, ranges or the blind test.'}
      </p>
      <div className="row" style={{ marginTop: 10 }}>
        <button className={`btn${drawing ? ' on' : ''}`} onClick={onDrawing}>
          <Icon d="M4 4h16v16H4z" />
          {drawing ? 'Click two opposite corners…' : 'Draw an area'}
        </button>
        {!world && (
          <button className="btn" onClick={() => onArea('country:world')}>
            Back to the world
          </button>
        )}
      </div>
      <Coords area={area} bbox={bbox} onChange={onCoords} />
    </section>
  )
}
