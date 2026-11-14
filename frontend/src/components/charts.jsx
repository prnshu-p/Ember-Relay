// Performance memoization for month transition
import { useCallback, useState } from 'react'
import { MONTHS, fmt, monthLabel, num, pct, x3 } from '../lib/format.js'

// round axis ticks from zero: about n steps of 1, 2 or 5 times a power of ten (never under 1), up to the first one
// at or above the maximum
const ticks = (max, n) => {
  const m = Math.max(max, 1),
    raw = m / n,
    p = 10 ** Math.floor(Math.log10(raw)),
    step = Math.max(1, [1, 2, 5, 10].find((k) => k * p >= raw) * p)
  return Array.from({ length: Math.ceil(m / step) + 1 }, (_, k) => k * step)
}
// axis labels: in full under 10,000, compact above; one style per axis
const tickFmt = (top) => (t) =>
  t === 0 ? '0' : top >= 1e6 ? `${+(t / 1e6).toFixed(2)}M` : top >= 1e4 ? `${+(t / 1e3).toFixed(1)}K` : fmt(t)

// A chart is drawn at the width it is given (one unit is one pixel), so its text keeps its size on a phone.
// Pointer or finger -> nearest data index. The read-out follows the mouse; after a tap it stays until a tap elsewhere.
function useChart() {
  const [W, setW] = useState(760),
    [i, setI] = useState(null)
  const ref = useCallback((el) => {
    const o = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))))
    o.observe(el)
    return () => o.disconnect()
  }, [])
  const bind = (xs) => {
    const near = (e) => {
      const x = e.clientX - e.currentTarget.getBoundingClientRect().left
      let best = 0
      xs.forEach((v, k) => {
        if (Math.abs(v - x) < Math.abs(xs[best] - x)) best = k
      })
      setI(best)
    }
    return {
      tabIndex: -1,
      onPointerMove: near,
      onPointerDown: near,
      onPointerLeave: (e) => e.pointerType === 'mouse' && setI(null),
      onBlur: () => setI(null),
    }
  }
  return [ref, W, i, bind]
}

// above the point, or below it when the point is in the upper half (so the tooltip never leaves the chart)
const Tip = ({ x, y, W, H, title, children }) => {
  const below = y < H * 0.5
  return (
    <div
      className="tip"
      style={{
        left: Math.max(100, Math.min(W - 100, x)),
        top: y + (below ? 14 : -10),
        transform: `translate(-50%, ${below ? '0' : '-100%'})`,
      }}
    >
      <h4>{title}</h4>
      {children}
    </div>
  )
}

// Yearly sums of the monthly rows. A year counts as estimated only if every month of it is (2012 has one such month).
function yearSums(rows) {
  const yrs = {}
  for (const d of rows) {
    const y = +d.month.slice(0, 4)
    const a = (yrs[y] ||= {
      y,
      h: 0,
      raw: 0,
      lo: 0,
      hi: 0,
      blind: 0,
      nb: 0,
      part: false,
      est: true,
      noraw: false,
    })
    a.h += d.count
    a.raw += d.source === 'model' ? d.modis : d.count
    a.lo += d.lo ?? d.count
    a.hi += d.hi ?? d.count
    if (d.blind != null) {
      a.blind += d.blind
      a.nb++
    }
    if (d.modis == null) a.noraw = true // a huge area, summed from 1 degree boxes, has no MODIS counts
    if (d.partial) a.part = true
    if (d.source !== 'model') a.est = false
  }
  return Object.values(yrs).sort((a, b) => a.y - b.y)
}

// Yearly totals: the naive join (MODIS until 2011, then VIIRS) jumps at 2012; the harmonized record does not.
export function Record({ rows, firstMonth }) {
  // whole years only (the record starts Nov 2000); the year in progress is one hollow point
  const all = yearSums(rows).filter(
    (r) => r.part || firstMonth.endsWith('-01') || r.y !== +firstMonth.slice(0, 4),
  )
  const [ref, W, hi, bind] = useChart(),
    H = 230,
    L = 50,
    R = 14,
    T = 14,
    B = 24
  const y0 = all[0]?.y,
    y1 = all.at(-1)?.y
  const X = (y) => L + (y1 > y0 ? (y - y0) / (y1 - y0) : 0.5) * (W - L - R) // a single year sits in the middle
  if (!all.length)
    return (
      <p className="note" style={{ marginTop: 10 }}>
        No whole year to show: the record starts in {monthLabel(firstMonth)}.
      </p>
    )
  const tk = ticks(Math.max(...all.map((r) => Math.max(r.h, r.hi, r.raw, r.blind))), 5),
    top = tk.at(-1),
    Y = (v) => T + (1 - v / top) * (H - T - B),
    tf = tickFmt(top)
  const line = (pts, f) =>
    pts.map((r, i) => `${i ? 'L' : 'M'}${X(r.y).toFixed(1)},${Y(f(r)).toFixed(1)}`).join('')
  const full = all.filter((r) => !r.part),
    est = full.filter((r) => r.y <= 2011),
    bl = full.filter((r) => r.y >= 2013 && r.nb >= 12)
  const band =
    est.length > 1 && est.some((r) => r.hi > r.lo)
      ? line(est, (r) => r.hi) +
        est
          .slice()
          .reverse()
          .map((r) => `L${X(r.y).toFixed(1)},${Y(r.lo).toFixed(1)}`)
          .join('') +
        'Z'
      : ''
  const seam = y0 <= 2011 && y1 >= 2012,
    cur = hi != null ? all[hi] : null,
    raw = !all.some((r) => r.noraw)
  return (
    <figure className="chart" ref={ref}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        {...bind(all.map((r) => X(r.y)))}
        role="img"
        aria-label="Hotspots per year: raw sensors joined, and the harmonized record"
      >
        {tk.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} className="gridline" />
            <text x={L - 8} y={Y(t) + 4} textAnchor="end">
              {tf(t)}
            </text>
          </g>
        ))}
        {all
          .filter((r) => all.length <= 8 || r.y % 5 === 0)
          .map((r) => (
            <text key={r.y} x={X(r.y)} y={H - 6} textAnchor="middle">
              {r.y}
            </text>
          ))}
        {seam && (
          <>
            <line x1={X(2011.5)} x2={X(2011.5)} y1={T} y2={H - B} className="seam" />
            <text x={X(2011.5) + 5} y={T + 9}>
              VIIRS begins
            </text>
          </>
        )}
        {band && <path d={band} className="band" />}
        {raw && <path d={line(full, (r) => r.raw)} className="raw" />}
        {bl.length > 1 && <path d={line(bl, (r) => r.blind)} className="blind" />}
        <path d={line(full, (r) => r.h)} className="harm" />
        {/* one or two years make no line worth the name: mark the values themselves */}
        {full.length < 3 &&
          full.map((r) => (
            <g key={r.y}>
              {raw && r.est && <circle cx={X(r.y)} cy={Y(r.raw)} r="4" className="dot r" />}
              <circle cx={X(r.y)} cy={Y(r.h)} r="4" className="dot" />
            </g>
          ))}
        {all
          .filter((r) => r.part)
          .map((r) => (
            <circle key={r.y} cx={X(r.y)} cy={Y(r.h)} r="4.5" className="part" />
          ))}
        {cur && (
          <>
            <line x1={X(cur.y)} x2={X(cur.y)} y1={T} y2={H - B} className="cross" />
            {raw && cur.est && <circle cx={X(cur.y)} cy={Y(cur.raw)} r="4" className="dot r" />}
            {cur.nb >= 12 && cur.y >= 2013 && (
              <circle cx={X(cur.y)} cy={Y(cur.blind)} r="4" className="dot b" />
            )}
            <circle cx={X(cur.y)} cy={Y(cur.h)} r="4.5" className={cur.part ? 'part' : 'dot'} />
          </>
        )}
      </svg>
      {cur && (
        <Tip
          x={X(cur.y)}
          y={Y(Math.max(cur.h, cur.est ? cur.hi : cur.blind))}
          W={W}
          H={H}
          title={`${cur.y}${cur.part ? ' (so far)' : ''}`}
        >
          <div>
            <span>
              <i />
              Harmonized
            </span>
            <b>{fmt(cur.h)}</b>
          </div>
          {cur.est && cur.hi > cur.lo && (
            <div>
              <span>Range</span>
              <b>
                {fmt(cur.lo)}–{fmt(cur.hi)}
              </b>
            </div>
          )}
          {raw && cur.est && (
            <div>
              <span>
                <i className="r" />
                MODIS as counted
              </span>
              <b>{fmt(cur.raw)}</b>
            </div>
          )}
          {cur.nb >= 12 && cur.y >= 2013 && (
            <div>
              <span>
                <i className="b" />
                Model, VIIRS hidden
              </span>
              <b>{fmt(cur.blind)}</b>
            </div>
          )}
        </Tip>
      )}
      <div className="keys">
        <span>
          <i />
          Harmonized record
        </span>
        {raw && (
          <span>
            <i className="k-raw" />
            Raw sensors joined (MODIS, then VIIRS)
          </span>
        )}
        {band && (
          <span>
            <i className="k-band" />
            Range of the estimates (monthly ranges added up)
          </span>
        )}
        {bl.length > 1 && (
          <span>
            <i className="k-blind" />
            Model with VIIRS hidden (blind test)
          </span>
        )}
        {all.some((r) => r.part) && (
          <span>
            <i className="k-part" />
            {y1} so far
          </span>
        )}
      </div>
    </figure>
  )
}

// Which part of the year burns: the median of each calendar month (whole record) against one year.
export function Season({ rows, year }) {
  const med = Array(12).fill(0),
    cur = Array(12).fill(null),
    part = Array(12).fill(false)
  rows.forEach((d) => {
    const i = +d.month.slice(5) - 1
    med[i] = d.median ?? 0
    if (+d.month.slice(0, 4) === year) {
      cur[i] = d.count
      part[i] = !!d.partial
    }
  })
  const [ref, W, i, bind] = useChart(),
    H = 200,
    L = 50,
    R = 14,
    T = 14,
    B = 24,
    bw = (W - L - R) / 12
  const X = (i) => L + bw * (i + 0.5)
  const tk = ticks(Math.max(...med, ...cur.map((v) => v ?? 0)), 3),
    top = tk.at(-1),
    Y = (v) => T + (1 - v / top) * (H - T - B),
    tf = tickFmt(top)
  const pts = cur.map((v, i) => (v == null ? null : [X(i), Y(v), i])).filter(Boolean)
  const w = Math.min(24, bw * 0.5)
  // a bar grows from the baseline: square foot, 4px rounded top
  const bar = (x, y) => {
    const h = H - B - y,
      r = Math.min(4, h)
    return h <= 0
      ? ''
      : `M${x - w / 2},${H - B}V${y + r}q0,${-r} ${r},${-r}H${x + w / 2 - r}q${r},0 ${r},${r}V${H - B}Z`
  }
  return (
    <figure className="chart" ref={ref}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        {...bind(MONTHS.map((_, k) => X(k)))}
        role="img"
        aria-label={`Median hotspots per calendar month, and ${year}`}
      >
        {tk.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} className="gridline" />
            <text x={L - 8} y={Y(t) + 4} textAnchor="end">
              {tf(t)}
            </text>
          </g>
        ))}
        {med.map((v, k) => (
          <path key={k} d={bar(X(k), Y(v))} className={`bar${k === i ? ' hot' : ''}`} />
        ))}
        {MONTHS.map((m, k) => (
          <text key={m} x={X(k)} y={H - 6} textAnchor="middle">
            {bw < 30 ? m[0] : m}
          </text>
        ))}
        {pts.length > 1 && (
          <path
            d={pts.map((p, k) => `${k ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('')}
            className="harm"
          />
        )}
        {pts.map((p) => (
          <circle
            key={p[2]}
            cx={p[0]}
            cy={p[1]}
            r={p[2] === i ? 5 : 4}
            className={part[p[2]] ? 'part' : 'dot'}
          />
        ))}
      </svg>
      {i != null && (
        <Tip x={X(i)} y={Y(Math.max(med[i], cur[i] ?? 0))} W={W} H={H} title={MONTHS[i]}>
          {cur[i] != null && (
            <div>
              <span>
                <i />
                {year}
                {part[i] ? ' (so far)' : ''}
              </span>
              <b>{fmt(cur[i])}</b>
            </div>
          )}
          <div>
            <span>
              <i className="g" />
              Median, all years
            </span>
            <b>{num(med[i])}</b>
          </div>
          {cur[i] != null && med[i] > 0 && !part[i] && (
            <div>
              <span>Times the median</span>
              <b>{x3(cur[i] / med[i])}×</b>
            </div>
          )}
        </Tip>
      )}
      <div className="keys">
        <span>
          <i className="k-bar" />
          Median for that month, all years
        </span>
        <span>
          <i />
          {year}
        </span>
        {part.some(Boolean) && (
          <span>
            <i className="k-part" />
            month in progress
          </span>
        )}
      </div>
    </figure>
  )
}

// horizontal comparison bars: error of several methods on one scale (shorter is better)
export function Versus({ rows, unit = pct }) {
  const top = Math.max(...rows.map((r) => r.v ?? 0), 1e-9)
  return (
    <div className="vs">
      {rows
        .filter((r) => r.v != null)
        .map((r) => (
          <div key={r.label} className={`vs-r ${r.kind || ''}`}>
            <span>{r.label}</span>
            <i>
              <b style={{ width: `${Math.max(2, (r.v / top) * 100)}%` }} />
            </i>
            <em>{unit(r.v)}</em>
          </div>
        ))}
    </div>
  )
}
