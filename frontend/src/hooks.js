import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { withTodaysNames } from './lib/places.js'
import { fetchBin } from './lib/world.js'

const BASE = `${import.meta.env.BASE_URL}world/`

// The address is the state: a = area, y = years, m = month, c = what the colours show, l = map layer.
const readHash = () => ({
  ...Object.fromEntries(new URLSearchParams(location.hash.slice(1))),
  '#': location.hash,
})
export const toHash = (o) =>
  `#${['a', 'y', 'm', 'c', 'l']
    .filter((k) => o[k])
    .map((k) => `${k}=${o[k]}`)
    .join('&')}`

export function useAddress() {
  const [nav, setNav] = useState(readHash)
  useEffect(() => {
    const moved = () => setNav(readHash())
    addEventListener('hashchange', moved)
    return () => removeEventListener('hashchange', moved)
  }, [])
  // a new area is a history entry (Back returns to the last one); other changes replace the current one
  const put = useCallback((patch, push) => {
    history[push ? 'pushState' : 'replaceState'](null, '', toHash({ ...readHash(), ...patch }))
    setNav(readHash())
  }, [])
  return [nav, put]
}

const storedTheme = () => {
  try {
    return localStorage.getItem('theme')
  } catch {
    return null
  }
}

// The theme follows the system until the reader chooses one; only that choice is stored.
export function useTheme() {
  const [theme, setTheme] = useState(
    () => storedTheme() || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const follow = () => storedTheme() || setTheme(mq.matches ? 'dark' : 'light')
    mq.addEventListener('change', follow)
    return () => mq.removeEventListener('change', follow)
  }, [])
  const toggle = () => {
    const t = theme === 'dark' ? 'light' : 'dark'
    try {
      localStorage.setItem('theme', t)
    } catch {
      /* private window */
    }
    setTheme(t)
  }
  return [theme, toggle]
}

// Loads the tiles an area needs. A failed download stops the loading until retry() or another area.
export function useTiles(need, enabled) {
  const [tiles, setTiles] = useState(() => new Map()) // id -> dataset
  const [failed, setFailed] = useState(null) // the tile list whose download failed
  const asked = useRef(new Set())
  useEffect(() => {
    if (!enabled || failed === need) return
    for (const id of need) {
      if (asked.current.has(id)) continue
      asked.current.add(id)
      fetchBin(`${BASE}tiles/${id}.bin.gz`)
        .then((d) => setTiles((m) => new Map(m).set(id, d)))
        .catch(() => {
          asked.current.delete(id)
          setFailed(need)
        })
    }
  }, [need, enabled, failed])
  const sets = useMemo(
    () => (enabled ? need.map((id) => tiles.get(id)).filter(Boolean) : []),
    [enabled, need, tiles],
  )
  return {
    sets,
    tilesIn: sets.length === need.length && sets.length > 0,
    tileError: enabled && failed === need,
    retry: () => setFailed(null),
  }
}

// The data files: index.json (months, tiles, the world's tests), countries.json and the 1 degree overview.
export function useWorldData() {
  const [index, setIndex] = useState(null)
  const [countries, setCountries] = useState(null)
  const [overview, setOverview] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    const getJson = (f) =>
      fetch(BASE + f).then((r) => {
        if (!r.ok) throw new Error(f)
        return r.json()
      })
    const failed = () => setError('The data could not be loaded.')
    getJson('index.json').then(setIndex).catch(failed)
    getJson('countries.json')
      .then((cs) => setCountries(withTodaysNames(cs)))
      .catch(failed)
    fetchBin(`${BASE}overview.bin.gz`)
      .then(setOverview)
      .catch(() => setError('The map data could not be loaded.'))
  }, [])
  return { index, countries, overview, error }
}
