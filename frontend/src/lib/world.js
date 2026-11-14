// The app's data and every number it shows, computed in the browser from public/world/ (written by
// pipeline/stage3_export.py). pipeline/test_app_data.py checks these functions against the Python arrays.
const Q = 5000 // h and blind are stored as round(log1p(value) * Q)
const EST_END = '2012-02' // months before this are model estimates (MODIS only)
const AQUA = '2002-07' // before this only Terra supplied data: a separate, less certain model
const K = 48,
  F = 5 // range rule, see rangesFor()
const ymi = (m) => +m.slice(0, 4) * 12 + +m.slice(5)
const yearOf = (m) => +m.slice(0, 4)

export function parse(buf) {
  const dv = new DataView(buf)
  if (String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3)) !== 'BAC2')
    throw new Error('not a data file')
  const n = dv.getUint32(4, true),
    months = dv.getUint32(8, true),
    rows = dv.getUint32(12, true),
    size = dv.getUint32(16, true) / 100
  let o = 20
  const take = (Type, len) => {
    const a = new Type(buf.slice(o, o + len * Type.BYTES_PER_ELEMENT))
    o += len * Type.BYTES_PER_ELEMENT
    return a
  }
  const ilat = take(Int16Array, n),
    ilon = take(Int16Array, n),
    country = take(Uint16Array, n) // "ci" in countries.json, 0 = none
  if (n % 2) o += 2
  const start = take(Uint32Array, months + 1),
    cell = take(Uint16Array, rows)
  const full = buf.byteLength - o >= rows * 6 // tiles carry modis and blind; the overview only h
  const modis = full ? take(Uint16Array, rows) : null,
    hq = take(Uint16Array, rows),
    bq = full ? take(Uint16Array, rows) : null
  const dec = (q) => Float32Array.from(q, (v) => Math.expm1(v / Q))
  return {
    size,
    lat: Float32Array.from(ilat, (v) => v * size),
    lon: Float32Array.from(ilon, (v) => v * size),
    country,
    start,
    cell,
    modis,
    h: dec(hq),
    blind: bq && dec(bq),
  }
}

export async function fetchBin(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status}`)
  // the files are gzip; some hosts unpack them on the way (Content-Encoding), others hand them over as they are
  let buf = await r.arrayBuffer()
  const b = new Uint8Array(buf, 0, 2)
  if (b[0] === 0x1f && b[1] === 0x8b)
    buf = await new Response(
      new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip')),
    ).arrayBuffer()
  return parse(buf)
}

// A box may run past 180 degrees east to cross the date line (170 to 190 is 170E to 170W): the part beyond is the far
// west of the data.
const split = ([w, s, e, n]) =>
  e > 180
    ? [
        [w, s, 180, n],
        [-180, s, e - 360, n],
      ]
    : [[w, s, e, n]]

// id of the 10 degree tile a point is in: 's10w060'
export function tileId(lat, lon) {
  const la = Math.floor(lat / 10) * 10,
    lo = Math.floor(lon / 10) * 10
  return `${la >= 0 ? 'n' : 's'}${String(Math.abs(la)).padStart(2, '0')}${lo >= 0 ? 'e' : 'w'}${String(Math.abs(lo)).padStart(3, '0')}`
}

// ids of the tiles a box overlaps, of those that exist
export function tilesFor(bbox, have) {
  const out = new Set()
  for (const [w, s, e, n] of split(bbox))
    for (let la = Math.floor(s / 10) * 10; la < n; la += 10)
      for (let lo = Math.floor(w / 10) * 10; lo < e; lo += 10) {
        const id = tileId(la, lo)
        if (have.has(id)) out.add(id)
      }
  return [...out]
}

// A box the app can use: four numbers, clamped to the map (85 degrees of latitude; west within one world, east at most
// once around from it) and at least one cell wide and tall. Anything else is null.
export function fitBox(b) {
  if (b.length !== 4 || !b.every(Number.isFinite)) return null
  const turn = b[0] >= 180 && b[0] < 540 ? -360 : 0 // drawn on the far side of a Pacific-centred map: one turn back
  const w = Math.max(-180, Math.min(180, b[0] + turn)),
    s = Math.max(-85, b[1]),
    e = Math.min(w + 360, b[2] + turn),
    n = Math.min(85, b[3])
  return e - w >= 0.25 && n - s >= 0.25 ? [w, s, e, n] : null
}

// Which cells of a dataset belong to an area {bbox, ci}: for a country (ci) the cells that are its own (a 1 degree box of
// the overview is counted with the country that has most of its hotspots: good enough to highlight it on the map);
// for a drawn box the cells that overlap it. Sharing only an edge does not count.
function members(d, { bbox, ci }) {
  const ok = new Uint8Array(d.lat.length),
    parts = split(bbox)
  for (let i = 0; i < ok.length; i++)
    ok[i] = ci
      ? d.country[i] === ci
      : parts.some(
          ([w, s, e, n]) => d.lon[i] + d.size > w && d.lon[i] < e && d.lat[i] + d.size > s && d.lat[i] < n,
        )
  return ok
}

// Monthly sums over the cells of these datasets that belong to the area: {h, modis, blind}, one value per month.
// modis and blind are null when the datasets do not carry them (the 1 degree overview).
export function seriesFor(datasets, area, T) {
  const h = new Float64Array(T),
    modis = new Float64Array(T),
    blind = new Float64Array(T),
    full = datasets.every((d) => d.modis)
  for (const d of datasets) {
    const ok = members(d, area)
    for (let t = 0; t < T; t++)
      for (let r = d.start[t]; r < d.start[t + 1]; r++) {
        if (!ok[d.cell[r]]) continue
        h[t] += d.h[r]
        if (full) {
          modis[t] += d.modis[r]
          blind[t] += d.blind[r]
        }
      }
  }
  return { h, modis: full ? modis : null, blind: full ? blind : null }
}

// Harmonized hotspots per cell summed over months t0..t1 (inclusive): [{lat, lon, size, v, own}], where own means the
// cell belongs to the area.
export function cellTotals(datasets, t0, t1, area) {
  const out = []
  for (const d of datasets) {
    const v = new Float64Array(d.lat.length),
      ok = area && members(d, area)
    for (let t = t0; t <= t1; t++) for (let r = d.start[t]; r < d.start[t + 1]; r++) v[d.cell[r]] += d.h[r]
    for (let i = 0; i < v.length; i++)
      if (v[i] > 0) out.push({ lat: d.lat[i], lon: d.lon[i], size: d.size, v: v[i], own: !ok || !!ok[i] })
  }
  return out
}

// Where is fire changing? Theil-Sen trend of each cell's yearly totals (whole years from 2003, after Aqua joined), as a
// share of its median year per decade. Cells with a median year under `floor` hotspots are left out (too noisy).
export function cellTrends(datasets, months, floor, area) {
  const yrs = [...new Set(months.map(yearOf))].filter(
    (y) => y >= 2003 && months.filter((m) => yearOf(m) === y).length === 12,
  )
  const yi = months.map((m) => yrs.indexOf(yearOf(m))),
    n = yrs.length,
    out = [],
    slopes = new Float64Array((n * (n - 1)) / 2),
    row = new Float64Array(n)
  for (const d of datasets) {
    const Y = new Float32Array(d.lat.length * n),
      ok = area && members(d, area)
    for (let t = 0; t < months.length; t++) {
      if (yi[t] < 0) continue
      for (let r = d.start[t]; r < d.start[t + 1]; r++) Y[d.cell[r] * n + yi[t]] += d.h[r]
    }
    for (let c = 0; c < d.lat.length; c++) {
      for (let j = 0; j < n; j++) row[j] = Y[c * n + j]
      const med = median(row)
      if (med < floor * d.size * d.size) continue
      let k = 0
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) slopes[k++] = (row[j] - row[i]) / (j - i)
      out.push({
        lat: d.lat[c],
        lon: d.lon[c],
        size: d.size,
        v: med,
        pct: (median(slopes) * 10) / med,
        own: !ok || !!ok[c],
      })
    }
  }
  return out
}

// numpy.quantile (linear interpolation)
function quantile(a, q) {
  const s = Float64Array.from(a).sort(),
    p = (s.length - 1) * q,
    i = Math.floor(p)
  return i + 1 < s.length ? s[i] + (p - i) * (s[i + 1] - s[i]) : s[i]
}
const median = (a) => quantile(a, 0.5)

// Trend of yearly totals [[year, total], ...]: Theil-Sen slope per decade as a share of the median year (robust to single
// extreme years), with Sen's 95 % interval. null with fewer than 10 years, or too little fire for a trend to mean
// anything.
function trendOf(pts) {
  const n = pts.length
  if (n < 10) return null
  const med = median(pts.map((p) => p[1]))
  if (med < 20) return null
  const sl = []
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++) sl.push((pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0]))
  sl.sort((a, b) => a - b)
  const N = sl.length,
    c = 1.96 * Math.sqrt((n * (n - 1) * (2 * n + 5)) / 18)
  const at = (k) => (sl[Math.max(0, Math.min(N - 1, k))] * 10) / med
  return {
    v: (median(sl) * 10) / med,
    lo: at(Math.floor((N - c) / 2)),
    hi: at(Math.ceil((N + c) / 2)),
    from: pts[0][0],
    to: pts.at(-1)[0],
  }
}

// totals of the whole calendar years from..to of a monthly series (the month in progress makes its year incomplete)
function yearTotals(months, values, partial, from = 2003, to = 9999) {
  const y = {}
  months.forEach((m, t) => {
    if (m !== partial) {
      const k = yearOf(m)
      y[k] ||= [0, 0]
      y[k][0] += values[t]
      y[k][1]++
    }
  })
  return Object.entries(y)
    .filter(([k, v]) => v[1] === 12 && +k >= from && +k <= to)
    .map(([k, v]) => [+k, v[0]])
}

// the month the data ends in is still in progress unless the last day is the month's last day
function partialMonth(through) {
  const [y, m, day] = through.split('-').map(Number)
  return day < new Date(y, m, 0).getDate() ? through.slice(0, 7) : null
}

// Range of each estimated month, from how far the blind test missed real VIIRS in this same area: of the K overlap
// months most similar in size, those within a factor F (at least 12), the stated percentiles of the log error. That
// alone proved too narrow when tested across periods, because the relation between the sensors drifts, so it is widened
// (R, from pipeline/stage2_model.py): by delta0 each side, the amount that put the real value inside 9 times in 10; by
// slope_per_year for each year before 2012; and the error part by terra_factor before Aqua. The estimate is always inside.
const NO_RANGE = { quantiles: [0.03, 0.97], delta0: 0.1, slope_per_year: 0.005, terra_factor: 1.5 }
function rangesFor(months, s, R = NO_RANGE) {
  const lr = [],
    lb = [],
    lo = {},
    hi = {}
  if (!s.blind) return { lo, hi }
  months.forEach((m, t) => {
    if (m >= EST_END && m < '2026-01' && s.blind[t] > 0) {
      lr.push(Math.log1p(s.h[t]) - Math.log1p(s.blind[t]))
      lb.push(Math.log1p(s.blind[t]))
    }
  })
  months.forEach((m, t) => {
    if (m >= EST_END) return
    const le = Math.log1p(s.h[t])
    const order = lb
      .map((v, i) => [Math.abs(v - le), lr[i]])
      .sort((a, b) => a[0] - b[0])
      .slice(0, K)
    let near = order.filter((x) => x[0] <= Math.log(F))
    if (near.length < 12) near = order.slice(0, 12)
    if (near.length < 12) return
    near = near.map((x) => x[1])
    const wide = m < AQUA ? R.terra_factor : 1,
      d = R.delta0 + (R.slope_per_year * (ymi(EST_END) - ymi(m))) / 12
    lo[t] = Math.max(0, Math.expm1(le + wide * Math.min(quantile(near, R.quantiles[0]), 0) - d))
    hi[t] = Math.expm1(le + wide * Math.max(quantile(near, R.quantiles[1]), 0) + d)
  })
  return { lo, hi }
}

// One row per month of the record: count, median of that calendar month, times-median, range, blind test, MODIS.
// Empty if the area never had a hotspot. The month in progress gets no times-median (part of a month against whole
// months), and the ratio is taken from the rounded count, so the numbers shown together agree.
// filled: month -> share of the VIIRS count that came from NOAA-20 (days Suomi NPP lost; everything once its data had ended)
// gaps: month -> {satellite: share of the month's detections lost to an outage};  ranges: see rangesFor()
export function rowsFor(months, s, through, { filled = {}, gaps = {}, ranges } = {}) {
  const first = s.h.findIndex((v, t) => v > 0 || (s.modis && s.modis[t] > 0))
  if (first < 0) return []
  const partial = partialMonth(through),
    { lo, hi } = rangesFor(months, s, ranges),
    byCal = {}
  months.forEach((m, t) => {
    if (m !== partial) (byCal[+m.slice(5)] ||= []).push(s.h[t])
  })
  const med = Object.fromEntries(Object.entries(byCal).map(([c, v]) => [c, median(v)]))
  const r2 = (v) => Math.round(v * 100) / 100
  return months.map((m, t) => {
    const md = med[+m.slice(5)],
      est = m < EST_END,
      count = Math.round(s.h[t]),
      fill = !est && filled[m] ? filled[m] : 0
    const row = {
      month: m,
      t,
      count,
      median: r2(md),
      anomaly: md > 0 && m !== partial ? r2(count / md) : null,
      lo: lo[t] == null ? null : r2(lo[t]),
      hi: hi[t] == null ? null : r2(hi[t]),
      blind: !est && s.blind && s.blind[t] > 0 ? Math.round(s.blind[t]) : null,
      modis: s.modis ? Math.round(s.modis[t]) : null,
      source: est ? 'model' : fill >= 0.5 ? 'noaa20' : 'snpp',
      fill,
    }
    if (gaps[m]) row.gap = gaps[m]
    if (m === partial) row.partial = true
    return row
  })
}

// trend of the record as shown (rounded monthly counts), whole years from 2003
export function trendOfRows(rows) {
  const months = rows.map((r) => r.month),
    counts = rows.map((r) => r.count)
  return trendOf(yearTotals(months, counts, rows.find((r) => r.partial)?.month))
}

// colour scale of the calendar: from the 5th percentile of the months with hotspots to the busiest one
export function countScale(rows) {
  const counts = rows
    .map((r) => r.count)
    .filter((c) => c > 0)
    .sort((a, b) => a - b)
  return {
    lo: Math.max(1, counts[Math.floor(counts.length * 0.05)] || 1),
    max: Math.max(2, counts.at(-1) || 2),
  }
}

// where each whole month stands among the same calendar month of every year: month -> [rank, years], 1 = busiest
export function monthRanks(rows) {
  const rank = {}
  for (let m = 1; m <= 12; m++) {
    const same = rows.filter((r) => +r.month.slice(5) === m && !r.partial).sort((a, b) => b.count - a.count)
    for (const r of same) rank[r.month] = [same.findIndex((x) => x.count === r.count) + 1, same.length]
  }
  return rank
}

// the busiest month (a row) and the busiest year ([year, total]) of these rows; the first one wins a tie
export function busiest(rows) {
  const years = {}
  for (const r of rows) years[r.month.slice(0, 4)] = (years[r.month.slice(0, 4)] || 0) + r.count
  return {
    month: rows.reduce((p, r) => (!p || r.count > p.count ? r : p), null),
    year: Object.entries(years).sort((a, b) => b[1] - a[1])[0],
  }
}

// How well the conversion works in this area, from the blind test (model never saw the VIIRS data of those months):
// median error of monthly totals for the model, one ratio and a ratio per calendar month (the ratios are fitted, for each
// month, on the other years of this same area), the step at 2012 (harmonized / MODIS after 2012 over the same before,
// weighted by fire, calendar month by calendar month), and the trend of 2003-2019 in the record and in MODIS alone.
export function evidenceFor(months, s) {
  if (!s.modis || !s.blind) return null // summed from 1 degree boxes: no MODIS counts or blind-test values to judge by
  const indices = (keep) => months.map((m, t) => t).filter(keep)
  const idx = indices((t) => months[t] >= EST_END && months[t] < '2026-01' && s.blind[t] > 0 && s.h[t] >= 20)
  if (idx.length < 24) return null
  const sum = (f, ts = idx) => ts.reduce((a, t) => a + f(t), 0),
    yr = (t) => months[t].slice(0, 4),
    cal = (t) => +months[t].slice(5)
  const ratio = (ts) =>
    sum((u) => s.h[u], ts) /
    Math.max(
      sum((u) => s.modis[u], ts),
      1,
    )
  const ov = indices((t) => months[t] >= EST_END && months[t] < '2026-01')
  const others = (t) => ov.filter((u) => yr(u) !== yr(t))
  const one = (t) => ratio(others(t)) * s.modis[t]
  const seasonal = (t) => {
    const o = others(t),
      oc = o.filter((u) => cal(u) === cal(t))
    return ((sum((u) => s.h[u], oc) + 20 * ratio(o)) / (sum((u) => s.modis[u], oc) + 20)) * s.modis[t]
  }
  const err = (f) => median(idx.map((t) => Math.abs(f(t) - s.h[t]) / s.h[t]))
  let w = 0,
    st = 0
  for (let c = 1; c <= 12; c++) {
    const pick = (a, b) => indices((t) => months[t] >= a && months[t] < b && cal(t) === c)
    const pre = pick(AQUA, EST_END),
      post = pick(EST_END, '2020-01')
    const hp = sum((t) => s.h[t], pre),
      mp = sum((t) => s.modis[t], pre),
      ha = sum((t) => s.h[t], post),
      ma = sum((t) => s.modis[t], post)
    if (Math.min(hp, mp, ha, ma) > 0) {
      st += (mp + ma) * Math.log(ha / ma / (hp / mp))
      w += mp + ma
    }
  }
  return {
    months: idx.length,
    model: err((t) => s.blind[t]),
    one: err(one),
    seasonal: err(seasonal),
    ratio: ratio(ov),
    seam: w ? Math.expm1(st / w) : null,
    trend: trendOf(yearTotals(months, s.h, null, 2003, 2019)),
    trendModis: trendOf(yearTotals(months, s.modis, null, 2003, 2019)),
  }
}

// CSV of the area's cell-months in a month range (tiles only). Cells are named by their south-west corner; a cell-month
// with no hotspot (in MODIS or in the record) has no row; before 2012, estimates under a quarter of a hotspot are spread
// over the other cells of their 1 degree box (or kept in its largest cell where the whole box is under that).
export function cellCsv(datasets, months, area, t0, t1, filled = {}) {
  const lines = ['month,cell_south,cell_west,cell_size_degrees,modis,harmonized_viirs_equivalent,source']
  const own = datasets.map((d) => members(d, area))
  for (let t = t0; t <= t1; t++) {
    const src = months[t] < EST_END ? 'model' : filled[months[t]] >= 0.5 ? 'noaa20' : 'snpp'
    datasets.forEach((d, k) => {
      for (let r = d.start[t]; r < d.start[t + 1]; r++) {
        const i = d.cell[r]
        if (own[k][i] && (d.modis[r] > 0 || d.h[r] >= 0.005))
          lines.push(
            `${months[t]},${d.lat[i]},${d.lon[i]},${d.size},${d.modis[r]},${+d.h[r].toFixed(2)},${src}`,
          )
      }
    })
  }
  return lines.join('\n')
}
