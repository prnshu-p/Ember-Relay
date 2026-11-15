import { Versus } from './charts.jsx'
import { fmt, pct, signed, signedPct } from '../lib/format.js'

const SCALES = [
  ['Countries', 'country', pct],
  ['1° boxes', 'box', pct],
  ['25 km cells (log error)', 'cell', (v) => v.toFixed(2)],
]

// The tests of the whole record (index.json's "world"). filledMonths: months where NOAA-20 filled days Suomi NPP lost.
export default function Evidence({ stats: wt, filledMonths }) {
  // both time directions: trained on one half of the years, tested on the other, and the other way round
  const avg = (method, scale) => (wt.tests.forward[method][scale] + wt.tests.backward[method][scale]) / 2
  const hotspots = Object.values(wt.hotspots).reduce((a, b) => a + b, 0)
  return (
    <section className="card" id="evidence">
      <h2>How we know: the whole planet</h2>
      <h3>
        {fmt(wt.cells)} cells, {(hotspots / 1e6).toFixed(0)} million hotspots, {wt.countries_tested} countries
        tested
      </h3>
      <p className="cap">
        Error on years hidden from the model, at three sizes, both time directions. Blue is a second VIIRS
        (NOAA-20) predicting the first: how far two good sensors disagree. Shorter is better.
      </p>
      <div className="scales">
        {SCALES.map(([title, k, unit]) => (
          <div key={k}>
            <h4>{title}</h4>
            <Versus
              unit={unit}
              rows={[
                { label: 'Second VIIRS', v: wt.benchmark?.twin[k], kind: 'f' },
                { label: 'Our record', v: avg('record', k), kind: 'm' },
                { label: 'Local ratio + small fires', v: avg('best simple', k) },
                { label: 'Ratio per calendar month', v: avg('seasonal ratio', k) },
                { label: 'One ratio', v: avg('one ratio', k) },
              ]}
            />
          </div>
        ))}
      </div>
      <div className="facts four">
        <div>
          <b>{signedPct(wt.steps['2012'].record)}</b>
          <span>
            step at 2012 for the world, where VIIRS begins (raw sensors joined:{' '}
            {signed(wt.steps['2012']['raw join'])}); at July 2002, where Aqua joins:{' '}
            {signedPct(wt.steps['2002'].record)}
          </span>
        </div>
        <div>
          <b>
            {wt.countries_better['seasonal ratio']} of {wt.countries_tested}
          </b>
          <span>
            countries where the record beats a ratio per calendar month; with stable orbits the two are level
            for whole countries ({pct(wt.tests.analogue.record.country)} and{' '}
            {pct(wt.tests.analogue['seasonal ratio'].country)})
          </span>
        </div>
        {wt.fresh2026 && (
          <div>
            <b>{pct(wt.fresh2026.record.country, 0)}</b>
            <span>
              country error on {wt.fresh2026.months} months of 2026 that no model was trained on (ratio per
              calendar month: {pct(wt.fresh2026['seasonal ratio'].country, 0)}, one ratio:{' '}
              {pct(wt.fresh2026['one ratio'].country, 0)})
            </span>
          </div>
        )}
        <div>
          <b>{pct(wt.ranges.coverage.country.inside, 0)}</b>
          <span>
            of real values fall inside the range of an estimate, tested across periods, after the ranges were
            widened to make that true ({pct(wt.ranges.coverage['0.5 degree box'].inside, 0)} for 50 km boxes)
          </span>
        </div>
      </div>
      <ol className="steps">
        <li>
          <b>Every cell, every month.</b> The model estimates VIIRS counts even where MODIS saw nothing, so
          small fires are not lost.
        </li>
        <li>
          <b>Physics in the inputs.</b> Aqua and Suomi NPP were placed to cross the equator in the early
          afternoon, Terra in the morning: their counts enter separately, with fire power and how detections
          spread over days and pixels.
        </li>
        <li>
          <b>Data put in order first.</b> The days each of the four satellites lost are found and corrected;{' '}
          {wt.persistent_sources.cells} cells with lava or gas flares are left out; the model is trained on
          2012–2019, before the MODIS orbits drifted.
        </li>
        <li>
          <b>A second VIIRS.</b> NOAA-20 fills the days Suomi NPP lost ({filledMonths} months) and carries the
          record on after Suomi NPP&rsquo;s data ended in November 2026.
        </li>
      </ol>
      <p className="cap" style={{ marginTop: 12 }}>
        &ldquo;Local ratio + small fires&rdquo; is the best method without a model that we could build: a
        seasonal ratio per 1° box and, where MODIS saw nothing, each cell&rsquo;s usual small fires. The
        ratios per calendar month and the single ratio are fitted per country. Country errors are medians of
        monthly totals; cells are scored on a log scale where either sensor saw fire. Words: a <i>hotspot</i>{' '}
        is one fire pixel a satellite detected; <i>VIIRS-equivalent</i> counts are what VIIRS on Suomi NPP
        records, or would have recorded; a <i>blind test</i> hides real VIIRS data from the model and compares
        afterwards.
      </p>
    </section>
  )
}
