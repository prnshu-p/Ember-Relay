import { fmt, monthLabel, monthName, num, ordinal, pct, x3 } from '../lib/format.js'

const SATELLITES = { terra: 'Terra', aqua: 'Aqua' }

const outages = (gap) =>
  Object.entries(SATELLITES)
    .filter(([k]) => gap?.[k] >= 0.05)
    .map(([k, name]) => `${name} lost ${pct(gap[k], 0)} of this month to an outage`)
    .join(', ')

// rank: [where the month stands among the same calendar month of every year, how many years]
function MonthText({ r, rank }) {
  const mon = monthName(r.month),
    estimated = r.source === 'model'
  return (
    <>
      <b>{monthLabel(r.month)}</b> · <b>{fmt(r.count)}</b> hotspot{r.count === 1 ? '' : 's'}
      {r.partial && ' so far'}
      {r.anomaly != null ? (
        <>
          {' '}
          · <b>{x3(r.anomaly)}×</b> the median {mon} ({num(r.median)})
        </>
      ) : r.partial ? (
        ' · month in progress, no comparison yet'
      ) : (
        ' · no usual value (median 0)'
      )}
      {rank && r.count > 0 && (
        <>
          {' '}
          · {rank[0] === 1 ? 'busiest' : `${ordinal(rank[0])} busiest`} {mon} of {rank[1]}
        </>
      )}
      {estimated &&
        (r.lo != null ? (
          <>
            {' '}
            · estimated, likely between {fmt(r.lo)} and {fmt(r.hi)}
          </>
        ) : (
          ' · estimated'
        ))}
      {estimated && r.count > 0 && outages(r.gap) && (
        <> · {outages(r.gap)}: scaled up from the days observed</>
      )}
      {!estimated && r.blind != null && (
        <> · the model, not shown this month's VIIRS data, said {fmt(r.blind)}</>
      )}
      {!estimated &&
        r.count > 0 &&
        r.fill >= 0.03 &&
        (r.month >= '2026-11'
          ? " · from NOAA-20 (Suomi NPP's data has ended)"
          : ` · ${pct(r.fill, 0)} filled from NOAA-20 (Suomi NPP lost days)`)}
    </>
  )
}

// The numbers of one month. The box is always as tall as its longest text would be at this width (two invisible
// copies size it), so pointing at a month never moves the page.
export default function Readout({ row, ranks, all }) {
  const big = Math.max(0, ...all.flatMap((r) => [r.count, r.hi ?? 0, r.blind ?? 0, r.median]))
  const widest = {
    month: '2000-05',
    count: big,
    median: big,
    anomaly: Math.max(8888, ...all.map((r) => r.anomaly ?? 0)),
    lo: big,
    hi: big,
    blind: big,
    fill: 0.44,
    gap: { terra: 0.55, aqua: 0.55 },
  }
  return (
    <div className="detail num" aria-live="polite">
      {['noaa20', 'model'].map((source) => (
        <span key={source} className="sizer" aria-hidden="true">
          <MonthText r={{ ...widest, source }} rank={[28, 28]} />
        </span>
      ))}
      <span>
        {row ? (
          <MonthText r={row} rank={ranks[row.month]} />
        ) : (
          'Pick a month for its numbers and to see where it burned.'
        )}
      </span>
    </div>
  )
}
