import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, Rectangle, CircleMarker, useMap, useMapEvents } from 'react-leaflet'
import { logT, ramp } from '../lib/colors.js'
import { hs, signed, x3 } from '../lib/format.js'
import { fitBox } from '../lib/world.js'

// one world: its copies to the left and right would have no cells. An area that crosses the date line is shown on the
// world from 0 to 360 degrees east (Pacific in the middle), with the cells of the western half moved across.
const EDGE = (wrap) => [
  [-85, wrap ? 0 : -180],
  [85, wrap ? 360 : 180],
]
const PAD = [14, 14]
// hotspots per square degree: 1 degree boxes and 0.25 degree cells share one scale
const dens = (c) => c.v / (c.size * c.size)

function Fit({ bbox: [w, s, e, n], wrap }) {
  const map = useMap()
  // zooming out stops when the whole world is in view
  useEffect(() => {
    map.setMinZoom(map.getBoundsZoom(EDGE(wrap)))
  }, [map, wrap])
  // No animation may outlive the map (it is rebuilt when the view turns to the Pacific); by then the map may already
  // be gone.
  useEffect(
    () => () => {
      try {
        map.stop()
      } catch {
        /* removed before us */
      }
    },
    [map],
  )
  useEffect(() => {
    const fit = () =>
      map.fitBounds(
        [
          [s, w],
          [n, e],
        ],
        { padding: PAD, animate: true, duration: 0.6 },
      )
    // Leaflet ignores a move that arrives while a zoom is animating: let that zoom end first
    if (map._animatingZoom) map.once('zoomend', fit)
    else fit()
    return () => map.off('zoomend', fit)
  }, [map, w, s, e, n])
  return null
}

// Two clicks draw a box: the first corner is marked and the box follows the pointer until the second click.
// Mounted only while drawing, so a first corner never outlives it.
function Draw({ onBox }) {
  const [a, setA] = useState(null),
    [b, setB] = useState(null)
  useMapEvents({
    click(e) {
      if (!a) return setA(e.latlng)
      const c = e.latlng,
        box = fitBox(
          [
            Math.min(a.lng, c.lng),
            Math.min(a.lat, c.lat),
            Math.max(a.lng, c.lng),
            Math.max(a.lat, c.lat),
          ].map((v) => +v.toFixed(2)),
        )
      if (box) onBox(box) // under one cell (a double click, say): keep waiting for the opposite corner
    },
    mousemove(e) {
      if (a) setB(e.latlng)
    },
  })
  if (!a) return null
  return (
    <>
      <CircleMarker
        center={a}
        radius={5}
        pathOptions={{ color: '#1f6fb2', fillOpacity: 1, interactive: false }}
      />
      {b && (
        <Rectangle
          bounds={[a, b]}
          pathOptions={{ color: '#1f6fb2', weight: 2, dashArray: '5 4', fill: false, interactive: false }}
        />
      )}
    </>
  )
}

// Hotspots per cell for the chosen period, on canvas under the outlines. Cells outside the area are dimmed.
// One tooltip follows the pointer (cheaper than thousands of them).
function Cells({ cells, colors, wrap, lo, hi }) {
  const map = useMap(),
    tip = useRef(null)
  useEffect(() => {
    if (!cells.length) return
    // Two canvases, each drawn solid and faded as a whole. Cells that are translucent one by one overlap at their edges
    // and show as a lattice.
    const canvas = (pane, opacity) => {
      Object.assign((map.getPane(pane) || map.createPane(pane)).style, { zIndex: 390, opacity })
      return L.canvas({ pane, padding: 0.3 })
    }
    const own = canvas('cells', 0.82),
      context = canvas('context', 0.25),
      byKey = new Map()
    const group = L.layerGroup(
      cells.map((c) => {
        // trend layer: the cell carries its own position on a diverging scale (-80 % .. +80 % per decade)
        const fill =
          c.pct != null
            ? ramp(colors, 0.5 + Math.max(-0.8, Math.min(0.8, c.pct)) / 1.6)
            : ramp(colors, logT(dens(c), lo, hi))
        byKey.set(`${c.size}|${Math.round(c.lat / c.size)}|${Math.round(c.lon / c.size)}`, c)
        const x = wrap && c.lon < 0 ? c.lon + 360 : c.lon
        return L.rectangle(
          [
            [c.lat, x],
            [c.lat + c.size, x + c.size],
          ],
          {
            renderer: c.own ? own : context,
            interactive: false,
            color: fill,
            weight: 1, // a stroke in the same colour closes the seams between cells under a pixel wide
            fillColor: fill,
            fillOpacity: 1,
          },
        )
      }),
    ).addTo(map)
    const sizes = [...new Set(cells.map((c) => c.size))]
    const out = () => {
      if (tip.current) {
        map.closeTooltip(tip.current)
        tip.current = null
      }
    }
    const move = (e) => {
      const lng = (((e.latlng.lng % 360) + 540) % 360) - 180 // back to -180..180, where the cells are
      const c = sizes
        .map((s) => byKey.get(`${s}|${Math.floor(e.latlng.lat / s)}|${Math.floor(lng / s)}`))
        .find(Boolean)
      if (!c) return out()
      tip.current ||= L.tooltip({ direction: 'top', offset: [0, -6], opacity: 1 })
      tip.current
        .setLatLng(e.latlng)
        .setContent(c.pct != null ? `${signed(c.pct)} per decade · typically ${hs(c.v)} a year` : hs(c.v))
        .addTo(map)
    }
    map.on('mousemove click', move) // click: a tap on a touch screen
    map.on('mouseout', out)
    return () => {
      group.remove()
      own.remove()
      context.remove()
      map.off('mousemove click', move)
      map.off('mouseout', out)
      out()
    }
  }, [map, cells, colors, wrap, lo, hi])
  return null
}

export default function MapView({ bbox, world, outline, cells, colors, drawing, onBox, busy, label, trend }) {
  const [w, s, e, n] = bbox,
    wrap = e > 180
  // the colour scale spans the selected area (the rest of the map is context): its 5th to 99.5th percentile
  const { lo, hi, count, per } = useMemo(() => {
    const own = cells.filter((c) => c.own),
      vs = own.map(dens).sort((a, b) => a - b),
      lo = Math.max(1e-6, vs[Math.floor(vs.length * 0.05)] || 1)
    return {
      lo,
      hi: Math.max(lo * 2, vs[Math.floor(vs.length * 0.995)] || 2),
      count: vs.length,
      per: own.reduce((m, c) => Math.min(m, c.size), 1),
    }
  }, [cells])
  const bar = <i style={{ background: `linear-gradient(90deg,${colors})` }} />
  return (
    <div
      className={`map${drawing ? ' drawing' : ''}`}
      role="region"
      aria-label={`Map of ${trend ? 'the trend in fire' : 'fire hotspots'} per cell, ${label}`}
    >
      <MapContainer
        key={wrap}
        bounds={[
          [s, w],
          [n, e],
        ]}
        boundsOptions={{ padding: PAD }}
        minZoom={0}
        zoomSnap={0.1}
        maxBounds={EDGE(wrap)}
        maxBoundsViscosity={1}
        attributionControl
      >
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="© OpenStreetMap contributors"
          noWrap={!wrap}
          bounds={EDGE(wrap)}
        />
        <Fit bbox={bbox} wrap={wrap} />
        <Cells cells={cells} colors={colors} wrap={wrap} lo={lo} hi={hi} />
        {!world && outline && (
          <Rectangle
            bounds={[
              [s, w],
              [n, e],
            ]}
            pathOptions={{
              color: 'currentColor',
              weight: 1.5,
              fill: false,
              interactive: false,
              className: 'aoi',
            }}
          />
        )}
        {drawing && <Draw onBox={onBox} />}
      </MapContainer>
      <div className="maplegend">
        {trend ? (
          <>
            <span>{signed(-0.8)}</span>
            {bar}
            <span>{signed(0.8)}</span>
            <span>per decade · {label}</span>
          </>
        ) : count ? (
          <>
            <span>≤ {x3(lo * per * per)}</span>
            {bar}
            <span>≥ {x3(hi * per * per)}</span>
            <span>
              per {per}° cell · {label}
            </span>
          </>
        ) : (
          label
        )}
      </div>
      {busy ? (
        <div className="mapbusy" role="status">
          Loading cells…
        </div>
      ) : (
        !count &&
        cells.length > 0 && (
          <div className="mapbusy" role="status">
            {trend ? 'Too little fire here for a trend' : `No hotspots here in ${label}`}
          </div>
        )
      )}
    </div>
  )
}
