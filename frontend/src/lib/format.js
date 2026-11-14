export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const fmt = (n) => (n == null ? '–' : Math.round(n).toLocaleString('en-US'))
export const pct = (v, d = 1) => (v == null ? '–' : `${(v * 100).toFixed(d)}%`)
// about three significant figures, never more than two decimals: 0.99, 4.00, 20.6, 484
export const x3 = (v) => (v == null ? '–' : v >= 99.95 ? fmt(v) : v.toFixed(v >= 9.995 ? 1 : 2))
// a median can be 1.5: do not round it to 2
export const num = (n) => (n >= 99.95 ? fmt(n) : `${+x3(n)}`)
export const hs = (n) => `${fmt(n)} hotspot${Math.round(n) === 1 ? '' : 's'}`

// a share as a whole percentage with its sign: +25%, -3%, 0%
export const signed = (v) => {
  const r = Math.round(v * 100)
  return `${r > 0 ? '+' : ''}${r}%`
}
// the same with one decimal: +3.2%
export const signedPct = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`)
// a trend cannot take away more than everything
export const perDecade = (v) => signed(Math.max(v, -1))

export const monthName = (m) => MONTHS[+m.slice(5) - 1]
export const monthLabel = (m) => `${monthName(m)} ${m.slice(0, 4)}`
export const yearSpan = (from, to) => (from === to ? `${from}` : `${from}–${to}`)
export const ordinal = (n) =>
  `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th'}`

const deg = (v, pos, neg) => (v ? `${Math.abs(v)}°${v > 0 ? pos : neg}` : '0°')
// an east edge past 180 has crossed the date line: 190 is 170°W
export const describeBox = ([w, s, e, n]) =>
  `${deg(s, 'N', 'S')}–${deg(n, 'N', 'S')}, ${deg(w, 'E', 'W')}–${deg(e > 180 ? e - 360 : e, 'E', 'W')}`
