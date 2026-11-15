import { useEffect, useMemo, useState } from 'react'
import CalendarCard from './components/CalendarCard.jsx'
import Evidence from './components/Evidence.jsx'
import Header from './components/Header.jsx'
import MapCard from './components/MapCard.jsx'
import QualityCard from './components/QualityCard.jsx'
import Stories from './components/Stories.jsx'
import TopBar from './components/TopBar.jsx'
import { Record, Season } from './components/charts.jsx'
import { toHash, useAddress, useTheme, useTiles, useWorldData } from './hooks.js'
import { calendarPng, monthlyCsv, saveFile } from './lib/download.js'
import { describeBox, monthLabel, yearSpan } from './lib/format.js'
import { STORIES, findCountry, slug } from './lib/places.js'
import {
  cellCsv,
  cellTotals,
  cellTrends,
  evidenceFor,
  fitBox,
  monthRanks,
  rowsFor,
  seriesFor,
  tileId,
  tilesFor,
} from './lib/world.js'

const WORLD = [-170, -56, 180, 74]
const MAX_TILES = 20 // a box may load this many 10 degree tiles; beyond that the 1 degree overview answers
const yearOf = (m) => +m.slice(0, 4)

// An area the app can show: a usable box, or a known country (any country until the list is in). Anything else is
// the world.
function areaOf(a = '', countries) {
  const box = a.startsWith('box:') && fitBox(a.slice(4).split(',').map(Number))
  if (box) return `box:${box.join(',')}`
  const known = a.startsWith('country:') && (!countries || countries.some((c) => c.id === a.slice(8)))
  return known ? a : 'country:world'
}

// the months t0..t1 the map shows: the picked month, or the years shown
function mapMonths(months, sel, from, to) {
  if (!months) return [0, 0]
  if (sel) return [months.indexOf(sel), months.indexOf(sel)]
  return [
    Math.max(
      0,
      months.findIndex((m) => yearOf(m) >= from),
    ),
    months.findLastIndex((m) => yearOf(m) <= to),
  ]
}

// 25 km cells wherever a tile is loaded, 1 degree boxes elsewhere (tiles are 10 degrees, so the two line up)
const withTiles = (boxes, cells, tiles) => [
  ...boxes.filter((c) => !tiles.includes(tileId(c.lat, c.lon))),
  ...cells,
]

export default function App() {
  const [nav, put] = useAddress()
  const [theme, toggleTheme] = useTheme()
  const { index, countries, overview, error } = useWorldData()
  const [drawing, setDrawing] = useState(false)
  const [query, setQuery] = useState('')
  const [miss, setMiss] = useState(false) // the search found no country

  // Escape leaves drawing mode, or else clears the picked month (not while typing in a field)
  useEffect(() => {
    const onKey = (ev) => {
      if (ev.key !== 'Escape' || ev.target.closest('input, select')) return
      if (drawing) setDrawing(false)
      else put({ m: null })
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [drawing, put])

  // What the address asks for, made safe: an unknown area is the world, a malformed range or month is none.
  const months = index?.months
  const T = months?.length || 0
  const area = areaOf(nav.a, countries) // 'country:<id>' or 'box:w,s,e,n'
  const span = months ? [yearOf(months[0]), yearOf(months.at(-1))] : [2000, 2026]
  const ys = /^(\d{4})(?:-(\d{4}))?$/.exec(nav.y || '')
  const range = ys && [+ys[1], +(ys[2] || ys[1])]
  const from = Math.max(span[0], Math.min(span[1], range ? range[0] : span[0]))
  const to = Math.max(from, Math.min(span[1], range ? range[1] : span[1]))
  const inYears = (m) => yearOf(m) >= from && yearOf(m) <= to
  // the month picked in the calendar, which the map shows: a month of the record, inside the years shown
  const sel =
    /^\d{4}-\d\d$/.test(nav.m || '') && (!months || (months.includes(nav.m) && inYears(nav.m))) ? nav.m : null
  const mode = nav.c === 'anomaly' ? 'anomaly' : 'count' // what the calendar's colours show
  const layer = nav.l === 'trend' ? 'trend' : 'count' // the map: hotspots of the period, or the trend per decade
  useEffect(() => {
    // A mistyped address is corrected once the data can tell, unless the address has moved on and its hashchange
    // is still on the way.
    const want = toHash({
      a: area,
      y: range && `${from}-${to}`,
      m: sel,
      c: mode !== 'count' && mode,
      l: layer !== 'count' && layer,
    })
    if (months && countries && location.hash === nav['#'] && location.hash !== want)
      history.replaceState(null, '', want)
  })

  const isBox = area.startsWith('box:')
  const country = !isBox && countries ? countries.find((c) => c.id === area.slice(8)) || countries[0] : null
  const world = country?.id === 'world'
  const bbox = useMemo(
    () => (isBox ? area.slice(4).split(',').map(Number) : (!world && country?.bbox) || WORLD),
    [area, isBox, world, country],
  )
  // what belongs to the area: a country's own 25 km cells (ci), or whatever overlaps the box
  const zone = useMemo(
    () => ({ bbox, ci: isBox || world ? 0 : country?.ci || 0 }),
    [bbox, isBox, world, country],
  )
  const have = useMemo(() => new Set((index?.tiles || []).map((t) => t.id)), [index])
  const need = useMemo(() => (index && !world ? tilesFor(bbox, have) : []), [index, world, bbox, have])
  const fine = need.length > 0 && need.length <= MAX_TILES // 25 km cells can be loaded for this area
  const huge = isBox && need.length > MAX_TILES // summed from 1 degree boxes, which carry no MODIS or blind-test columns
  const coarse = isBox && !fine // no cell data: a huge box, or one with no data tile at all (open sea)
  const { sets, tilesIn, tileError, retry } = useTiles(need, fine)

  // the area's monthly series: a country's comes ready-made; a box is summed from its tiles, or from the overview
  // when it is huge
  const series = useMemo(() => {
    if (!index) return null
    if (!isBox) return country
    if (fine) return tilesIn ? seriesFor(sets, zone, T) : null
    return overview ? seriesFor([overview], zone, T) : null
  }, [index, isBox, country, fine, tilesIn, sets, overview, zone, T])
  const status = series ? 'ready' : tileError ? 'tile-error' : error ? 'error' : 'loading'
  const all = useMemo(
    () =>
      series && months
        ? rowsFor(months, series, index.through, {
            filled: index.filled,
            gaps: index.gaps,
            ranges: index.world.ranges,
          })
        : [],
    [series, months, index],
  )
  const data = useMemo(
    () => all.filter((r) => yearOf(r.month) >= from && yearOf(r.month) <= to),
    [all, from, to],
  )
  const evidence = useMemo(
    () => (series && months && !coarse ? evidenceFor(months, series) : null),
    [series, months, coarse],
  )
  const years = Array.from({ length: to - from + 1 }, (_, i) => from + i)

  const [t0, t1] = mapMonths(months, sel, from, to)
  const trends = useMemo(() => {
    // slow to compute for the whole planet, so only when asked for
    if (layer !== 'trend' || !overview || !months) return null
    const own = world ? null : zone
    const boxes = cellTrends([overview], months, 24, own)
    return world || !tilesIn ? boxes : withTiles(boxes, cellTrends(sets, months, 24, own), need)
  }, [layer, overview, months, world, zone, tilesIn, sets, need])
  const cells = useMemo(() => {
    if (trends) return trends
    if (!overview || !months || t0 < 0) return []
    const floor = Math.max(1, (t1 - t0 + 1) / 24) // hides stray detections on ice and open sea
    const own = world ? null : zone
    const boxes = cellTotals([overview], t0, t1, own).filter((c) => c.v >= floor)
    return world || !tilesIn ? boxes : withTiles(boxes, cellTotals(sets, t0, t1, own), need)
  }, [trends, overview, months, t0, t1, world, zone, tilesIn, sets, need])

  // to another area; a story also picks its month, and resets the years if they leave that month out
  const go = (a, m = null) => {
    const patch = { a, m }
    if (m && !inYears(m)) patch.y = null
    put(patch, a !== area)
    setDrawing(false)
    setQuery('')
    setMiss(false)
  }
  // a miss is reported only when the reader asked (Enter), not while a suggestion is being chosen
  const pick = (q, quiet) => {
    const c = findCountry(countries, q)
    if (c) go(`country:${c.id}`)
    else setMiss(!quiet && !!slug(q))
  }

  const where = describeBox(bbox)
  const name = isBox ? STORIES.find((s) => s.area === area)?.title || where : country?.name || ''
  useEffect(() => {
    document.title = name ? `${name} · Burning Activity Calendar` : 'Burning Activity Calendar'
  }, [name])
  const yrs = yearSpan(from, to)
  const seasonYear = sel ? yearOf(sel) : +(all.at(-1)?.month.slice(0, 4) || to)

  const id = isBox ? 'area' : country?.id
  const file = `${id}_${from === to ? from : `${from}-${to}`}`
  const saveTable = () => saveFile(`${file}_monthly.csv`, monthlyCsv(data, monthRanks(all)), 'text/csv')
  const saveCells = () =>
    saveFile(
      `${id}_${sel || `${from}-${to}`}_cells.csv`,
      cellCsv(sets, months, zone, t0, t1, index.filled),
      'text/csv',
    )
  const saveImage = () =>
    calendarPng({ title: `${isBox ? where : name}, ${yrs}`, years, rows: data, mode }).then((png) =>
      saveFile(`${file}_calendar.png`, png),
    )

  return (
    <>
      <a
        className="btn skip"
        href="#main"
        onClick={(ev) => {
          ev.preventDefault()
          document.getElementById('main').focus()
        }}
      >
        Skip to the content
      </a>
      <TopBar
        countries={countries}
        query={query}
        miss={miss}
        onQuery={(q) => {
          setQuery(q)
          setMiss(false)
        }}
        onPick={pick}
        onWorld={() => go('country:world')}
        theme={theme}
        onTheme={toggleTheme}
      />

      <main className="page" id="main" tabIndex={-1}>
        {error && (
          <p className="error" role="alert">
            {error}{' '}
            <button className="link" onClick={() => location.reload()}>
              Reload
            </button>
          </p>
        )}
        {tileError && (
          <p className="error" role="alert">
            Part of this area's data could not be loaded.{' '}
            <button className="link" onClick={retry}>
              Try again
            </button>
          </p>
        )}
        <Header
          name={name}
          months={months}
          span={span}
          from={from}
          to={to}
          onYears={(f, t) => put({ y: `${f}-${t}`, m: null })}
          period={sel ? monthLabel(sel) : yrs}
          isBox={isBox}
          hasRows={data.length > 0}
          hasCells={tilesIn}
          onTable={saveTable}
          onCells={saveCells}
          onImage={saveImage}
        />
        <Stories area={area} sel={sel} onPick={(s) => go(s.area, s.month)} />

        <div className="grid">
          <div className="col">
            <MapCard
              layer={layer}
              onLayer={(l) => put({ l })}
              theme={theme}
              area={area}
              bbox={bbox}
              world={world}
              cells={cells}
              busy={!error && (!overview || (fine && !tilesIn && !tileError))}
              months={months}
              sel={sel}
              yrs={yrs}
              huge={huge}
              drawing={drawing}
              onDrawing={() => setDrawing((d) => !d)}
              onArea={go}
              onClearMonth={() => put({ m: null })}
              onCoords={(a, push) => put({ a }, push)}
            />
            <QualityCard
              name={name}
              world={world}
              tests={country?.tests}
              evidence={evidence}
              huge={huge}
              status={status}
              worldSeam={index?.world.steps['2012'].record}
            />
          </div>
          <CalendarCard
            area={area}
            rows={data}
            all={all}
            years={years}
            months={months}
            through={index?.through}
            mode={mode}
            onMode={(c) => put({ c })}
            theme={theme}
            sel={sel}
            onSelect={(m) => put({ m })}
            status={status}
            onRetry={retry}
          />
        </div>

        {all.length > 0 && (
          <div className="two">
            <section className="card">
              <h3>Fire season</h3>
              <p className="cap">
                A typical year against {seasonYear}.{' '}
                {sel
                  ? 'The year of the month you picked.'
                  : 'Pick a month in the calendar to compare its year.'}
              </p>
              <Season rows={all} year={seasonYear} />
            </section>
            <section className="card">
              <h3>One consistent record</h3>
              <p className="cap">
                {coarse
                  ? 'Hotspots per year in the harmonized record.'
                  : 'Hotspots per year. Joined as counted, the record jumps when VIIRS begins. Harmonized, it does not.'}
              </p>
              <Record rows={data} firstMonth={months[0]} />
            </section>
          </div>
        )}

        {index?.world && <Evidence stats={index.world} filledMonths={Object.keys(index.filled).length} />}

        <footer>
          Data: NASA FIRMS active fire detections (MODIS Collection 6.1; VIIRS 375 m on Suomi NPP and NOAA-20)
          {index && <>, to {index.through}</>}. Presumed vegetation fires (FIRMS type 0) of nominal or high
          confidence, per 0.25° cell and month; the months from August 2026 are near-real-time data, filtered
          by place. Estimates before February 2012 come from a model and carry a range. We acknowledge the use
          of data from NASA&rsquo;s Fire Information for Resource Management System (FIRMS), part of
          NASA&rsquo;s Earth Science Data and Information System (ESDIS). Base map © OpenStreetMap contributors.
        </footer>
      </main>
    </>
  )
}
