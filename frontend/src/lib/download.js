import { DIV, SEQ, monthColor } from './colors.js'
import { MONTHS, fmt } from './format.js'
import { countScale } from './world.js'

export function saveFile(name, content, type) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(content instanceof Blob ? content : new Blob([content], { type }))
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

const CSV_HEADER =
  'month,harmonized,range_low,range_high,median_of_calendar_month,times_median,rank_among_same_month,modis_as_detected,blind_test,source,share_from_noaa20,terra_share_lost,aqua_share_lost,month_in_progress'

export function monthlyCsv(rows, ranks) {
  const line = (r) =>
    [
      r.month,
      r.count,
      r.lo ?? '',
      r.hi ?? '',
      r.median ?? '',
      r.anomaly ?? '',
      ranks[r.month]?.[0] ?? '',
      r.modis ?? '',
      r.blind ?? '',
      r.source,
      r.fill || '',
      r.gap?.terra ?? '',
      r.gap?.aqua ?? '',
      r.partial ? 'yes' : '',
    ].join(',')
  return [CSV_HEADER, ...rows.map(line)].join('\n')
}

// The calendar as a PNG in the light theme, with its scale and notes.
export function calendarPng({ title, years, rows, mode }) {
  const byKey = Object.fromEntries(rows.map((r) => [r.month, r])),
    scale = countScale(rows),
    est = (d) => d.source === 'model' && d.count > 0
  const notes = [
    'Harmonized, VIIRS-equivalent hotspot counts.',
    rows.some(est) && 'Hatched cells (before February 2012) are estimated from MODIS.',
    rows.some((d) => d.partial) && 'Dashed outline: the month in progress, not compared with whole months.',
    'Data: NASA FIRMS (MODIS Collection 6.1; VIIRS on Suomi NPP and NOAA-20).',
  ].filter(Boolean)
  const cw = 46,
    ch = 22,
    left = 60,
    top = 70,
    W = left + cw * 12 + 24,
    H = top + ch * years.length + 52 + 17 * notes.length
  const c = Object.assign(document.createElement('canvas'), { width: W * 2, height: H * 2 }),
    g = c.getContext('2d')
  g.scale(2, 2)
  g.fillStyle = '#fff'
  g.fillRect(0, 0, W, H)
  g.fillStyle = '#16150f'
  g.font = '600 15px Inter, system-ui, sans-serif'
  g.fillText('Burning Activity Calendar', left, 24)
  g.font = '12px Inter, system-ui, sans-serif'
  g.fillStyle = '#55534b'
  g.fillText(title, left, 42)
  g.textAlign = 'center'
  MONTHS.forEach((m, i) => g.fillText(m, left + cw * i + cw / 2, top - 8))
  years.forEach((y, r) => {
    g.textAlign = 'right'
    g.fillStyle = '#55534b'
    g.fillText(y, left - 8, top + ch * r + 15)
    for (let i = 0; i < 12; i++) {
      const d = byKey[`${y}-${String(i + 1).padStart(2, '0')}`]
      if (!d) continue
      const fill = monthColor(d, mode, 'light', scale),
        px = left + cw * i + 1,
        py = top + ch * r + 1
      g.fillStyle = fill || '#faf9f6'
      g.fillRect(px, py, cw - 2, ch - 2)
      // no colour: an outlined empty cell; the month in progress: a dashed outline
      if (!fill || d.partial) {
        g.setLineDash(d.partial ? [3, 2] : [])
        g.strokeStyle = d.partial ? '#55534b' : '#d6d2c6'
        g.strokeRect(px + 0.5, py + 0.5, cw - 3, ch - 3)
        g.setLineDash([])
      }
      if (est(d)) {
        g.strokeStyle = 'rgba(255,255,255,.7)'
        g.beginPath()
        g.moveTo(px + 3, py + ch - 5)
        g.lineTo(px + cw - 5, py + 3)
        g.stroke()
        g.strokeStyle = 'rgba(22,21,15,.25)'
        g.beginPath()
        g.moveTo(px + 4, py + ch - 4)
        g.lineTo(px + cw - 4, py + 4)
        g.stroke()
      }
    }
  })
  const y = top + ch * years.length + 18,
    colors = mode === 'count' ? SEQ.light : DIV.light
  colors.forEach((col, i) => {
    g.fillStyle = col
    g.fillRect(left + i * 26, y, 26, 10)
  })
  g.textAlign = 'left'
  g.fillStyle = '#55534b'
  g.fillText(
    mode === 'count'
      ? `${fmt(scale.lo)} or fewer → ${fmt(scale.max)} hotspots a month (log scale)`
      : '⅛× → 8× the median of that calendar month',
    left + 26 * 7 + 10,
    y + 9,
  )
  notes.forEach((t, i) => g.fillText(t, left, y + 34 + 17 * i))
  return new Promise((res) => c.toBlob(res, 'image/png'))
}
