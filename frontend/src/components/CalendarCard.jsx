import { useMemo, useState } from 'react'
import Calendar from './Calendar.jsx'
import Readout from './Readout.jsx'
import { DIV, SEQ, monthColor } from '../lib/colors.js'
import { fmt, monthLabel, monthName, perDecade, x3, yearSpan } from '../lib/format.js'
import { busiest, countScale, monthRanks, trendOfRows } from '../lib/world.js'

function Stat({ value, title, children }) {
  return (
    <div className="stat" title={title}>
      <b>{value}</b>
      <span>{children}</span>
    </div>
  )
}

function Legend({ mode, theme, scale, inProgress }) {
  return (
    <div className="legend">
      {mode === 'count' ? (
        <>
          <span>≤ {fmt(scale.lo)}</span>
          <i style={{ background: `linear-gradient(90deg,${SEQ[theme]})` }} />
          <span>{fmt(scale.max)} hotspots a month</span>
          <span className="key">
            <b className="cell zero" />
            none
          </span>
        </>
      ) : (
        <>
          <span>⅛× the median</span>
          <i style={{ background: `linear-gradient(90deg,${DIV[theme]})` }} />
          <span>8×</span>
        </>
      )}
      <span className="key">
        <b
          className="cell est"
          style={{ backgroundColor: mode === 'count' ? SEQ[theme][2] : DIV[theme][3] }}
        />
        estimated from MODIS (before Feb 2012)
      </span>
      {inProgress && (
        <span className="key">
          <b className="cell zero part" />
          month in progress
        </span>
      )}
    </div>
  )
}

// The calendar card: headline numbers, the calendar and the read-out of one month.
// rows: the months of the years shown; all: the whole record.
export default function CalendarCard({
  area,
  rows,
  all,
  years,
  months,
  through,
  mode,
  onMode,
  theme,
  sel,
  onSelect,
  status,
  onRetry,
}) {
  const [hover, setHover] = useState(null) // the month under the mouse or the keyboard focus
  const [tab, setTab] = useState(null)
  const byKey = useMemo(() => Object.fromEntries(rows.map((r) => [r.month, r])), [rows])
  const scale = useMemo(() => countScale(rows), [rows])
  const ranks = useMemo(() => monthRanks(all), [all])
  const trend = useMemo(() => trendOfRows(all), [all])
  const peak = busiest(rows)
  const latest = all.findLast((r) => !r.partial)
  const inProgress = all.find((r) => r.partial)
  const yrs = yearSpan(years[0], years.at(-1))
  return (
    <section className="card">
      <div className="stats">
        <Stat value={latest?.anomaly != null ? `${x3(latest.anomaly)}×` : '–'}>
          {latest
            ? `${monthLabel(latest.month)}, against the median ${monthName(latest.month)} of all years`
            : 'Latest month against its median'}
        </Stat>
        <Stat value={peak.month?.count ? monthLabel(peak.month.month) : '–'}>
          Busiest month of {yrs}
          {peak.month?.count ? ` · ${fmt(peak.month.count)}` : ''}
        </Stat>
        <Stat value={peak.year?.[1] ? peak.year[0] : '–'}>
          Busiest year of {yrs}
          {peak.year?.[1] ? ` · ${fmt(peak.year[1])}` : ''}
        </Stat>
        <Stat
          value={trend ? perDecade(trend.v) : '–'}
          title="Theil–Sen slope of yearly totals, as a share of the median year"
        >
          {trend
            ? `Trend per decade, ${trend.from}–${trend.to} · 95% interval ${perDecade(trend.lo)} to ${perDecade(trend.hi)}`
            : 'Trend per decade'}
        </Stat>
      </div>
      <div className="row">
        <div className="seg" role="group" aria-label="What the colours show">
          <button aria-pressed={mode === 'count'} onClick={() => onMode('count')}>
            Hotspot count
          </button>
          <button aria-pressed={mode === 'anomaly'} onClick={() => onMode('anomaly')}>
            Against the median
          </button>
        </div>
        {inProgress && (
          <span className="note">
            {monthLabel(inProgress.month)} is in progress (data to day {+through.slice(8)}):{' '}
            {fmt(inProgress.count)} so far.
          </span>
        )}
      </div>
      {status === 'loading' && <div className="skeleton" style={{ height: 560, marginTop: 12 }} />}
      {status === 'tile-error' && (
        <p className="note" style={{ marginTop: 12 }}>
          The calendar needs the data that could not be loaded.{' '}
          <button className="link" onClick={onRetry}>
            Try again
          </button>
        </p>
      )}
      {status === 'ready' && !all.length && (
        <p className="note" style={{ marginTop: 12 }}>
          No hotspots were recorded in this area. Try a larger one.
        </p>
      )}
      {all.length > 0 && (
        <Calendar
          key={area} // a new area fades in
          years={years}
          months={months}
          rows={rows}
          byKey={byKey}
          sel={sel}
          tab={tab}
          colorOf={(r) => monthColor(r, mode, theme, scale)}
          onSelect={onSelect}
          onHover={setHover}
          onTab={setTab}
        />
      )}
      <Legend mode={mode} theme={theme} scale={scale} inProgress={!!byKey[inProgress?.month]} />
      <Readout row={byKey[hover] || byKey[sel]} ranks={ranks} all={all} />
    </section>
  )
}
