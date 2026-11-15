import { Versus } from './charts.jsx'
import { perDecade, signedPct, x3 } from '../lib/format.js'

// The test of a country from the pipeline when there is one, else the blind test of the area computed here.
function Test({ name, world, tests, evidence, huge, status }) {
  if (tests?.record != null)
    return (
      <>
        <h3>{name}: tested on years the model never saw</h3>
        <p className="cap">
          Median error of monthly totals. The model was trained on one half of 2012–2025 and tested on the
          other, both ways. The simple methods use MODIS counts and a ratio fitted on the same training years.
        </p>
        <Versus
          rows={[
            { label: 'Our record', v: tests.record, kind: 'm' },
            { label: 'Local ratio + small fires', v: tests.best_simple },
            { label: 'Ratio per calendar month', v: tests.seasonal_ratio },
            { label: 'One ratio', v: tests.one_ratio },
          ]}
        />
      </>
    )
  if (evidence)
    return (
      <>
        <h3>{world ? 'The world: the blind test' : `${name}: the blind test in this area`}</h3>
        <p className="cap">
          Median error of monthly totals over {evidence.months} months whose VIIRS data the model was not
          shown. The simple ratios are fitted, for each month, on the other years of this same area.
        </p>
        <Versus
          rows={[
            { label: 'Our record', v: evidence.model, kind: 'm' },
            { label: 'Ratio per calendar month', v: evidence.seasonal },
            { label: 'One ratio', v: evidence.one },
          ]}
        />
      </>
    )
  if (huge) return <p className="note">Draw a smaller area to see its blind test.</p>
  if (status === 'ready')
    return (
      <p className="note">Not enough fire here for a test: fewer than 24 months with 20 or more hotspots.</p>
    )
  if (status === 'loading') return <div className="skeleton" style={{ height: 120 }} />
  return <p className="note">The data for this area could not be loaded.</p>
}

export default function QualityCard({ name, world, tests, evidence, huge, status, worldSeam }) {
  return (
    <section className="card">
      <h2>How good is the record here?</h2>
      <Test name={name} world={world} tests={tests} evidence={evidence} huge={huge} status={status} />
      {evidence && (
        <div className="facts">
          <div>
            <b>{x3(tests?.ratio ?? evidence.ratio)}×</b>
            <span>VIIRS fire pixels per MODIS one here</span>
          </div>
          <div>
            <b>{signedPct(world ? worldSeam : tests ? tests.seam : evidence.seam)}</b>
            <span>step at 2012, where VIIRS begins (0 is none)</span>
          </div>
          <div>
            <b>
              {evidence.trend && evidence.trendModis
                ? `${perDecade(evidence.trend.v)} / ${perDecade(evidence.trendModis.v)}`
                : '–'}
            </b>
            <span>trend per decade, 2003–2019: this record / MODIS alone</span>
          </div>
        </div>
      )}
    </section>
  )
}
