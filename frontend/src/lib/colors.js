// Colour-blind safe ramps. On a dark surface "more" is brighter, on a light one darker. The first step of SEQ is
// told apart from "no hotspots" (an outlined, empty cell) by more than its hue.
export const SEQ = {
  light: ['#ffe9a0', '#fed976', '#fdbb4a', '#f99b2b', '#ea6f12', '#c64a05', '#8a2d04'],
  dark: ['#52280f', '#76340d', '#9b4410', '#cb5f15', '#ea8a2c', '#f6b957', '#fde8a2'],
}
export const DIV = {
  light: ['#2166ac', '#67a9cf', '#d1e5f0', '#f3f2ee', '#fddbc7', '#ef8a62', '#b2182b'],
  dark: ['#58a6e0', '#2f6ea3', '#22405a', '#2a2925', '#5c2f26', '#a8432f', '#f0704f'],
}
// for the trend map: the middle is a grey that stands out from the land, so "no change" is still a cell
export const TREND = {
  light: ['#2166ac', '#4393c3', '#92c5de', '#c6c3b8', '#f4a582', '#d6604d', '#b2182b'],
  dark: ['#6db3ea', '#3d86c2', '#2a5f8f', '#5a5850', '#8f4634', '#c4553a', '#f0704f'],
}

export const ramp = (cols, t) =>
  cols[Math.max(0, Math.min(cols.length - 1, Math.round(t * (cols.length - 1))))]
// where v sits between lo and hi on a log scale, 0 to 1
export const logT = (v, lo, hi) =>
  (Math.log(Math.max(v, lo)) - Math.log(lo)) / (Math.log(hi) - Math.log(lo) || 1)

// The colour of a calendar month, or null for a neutral cell: no hotspots, or, against the median, the month in
// progress (it cannot be compared with whole months).
export function monthColor(r, mode, theme, { lo, max }) {
  if (mode === 'count') return r.count ? ramp(SEQ[theme], logT(r.count, lo, max)) : null
  if (r.partial) return null
  // 1/8x to 8x the median. One hotspot is added on both sides, so tiny counts stay calm: 0 against a median of 1
  // is not the far end, 3 against a median of 0 has a colour.
  return ramp(DIV[theme], 0.5 + Math.log2((r.count + 1) / (r.median + 1)) / 6)
}
