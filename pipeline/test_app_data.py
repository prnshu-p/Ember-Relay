"""Parity test: the app's data files against stage 2's arrays, and the browser code (frontend/src/lib/world.js)
against an independent Python reader and Python versions of its statistics.
Run: python3 pipeline/test_app_data.py   (needs node; WORLD_JS=<path> tests another copy of world.js)"""

import calendar
import gzip
import json
import os
import pathlib
import struct
import subprocess
import tempfile

import numpy as np
from scipy import sparse

from common import APP_DATA, MODEL, ROOT, cell_lat, cell_lon, month_index

BOXES = [
    [-124.5, 32.5, -114, 42],
    [22, -18, 34, -8],
    [20, 35, 28, 42],
    [140, -38, 150, -30],
    [100, 55, 120, 65],
    [10, 60, 20, 66],
    [27.1, -14.4, 27.6, -13.9],  # smaller than a degree
    [170, -20, 190, -10],  # across the date line
    [-40, 20, -30, 30],  # open sea
]
COUNTRIES = ["zambia", "greece", "sweden"]
EST, AQUA = "2012-02", "2002-07"

index = json.loads((APP_DATA / "index.json").read_text())
months = index["months"]
T = len(months)
have = {t["id"] for t in index["tiles"]}
countries = json.loads((APP_DATA / "countries.json").read_text())
R = index["world"]["ranges"]
YEAR = np.array([int(mo[:4]) for mo in months])
CAL = np.array([int(mo[5:]) for mo in months])
through = index["through"]
year, month, day = map(int, through.split("-"))
partial = through[:7] if day < calendar.monthrange(year, month)[1] else None  # the month in progress
complete = np.array(months) != partial


def read(path):
    """An independent reader of the BAC2 files (layout in stage3_export.write_bin)."""
    b = gzip.decompress(path.read_bytes())
    assert b[:4] == b"BAC2"
    n, nm, rows, size = struct.unpack("<4I", b[4:20])
    pos = 20

    def take(dtype, count):
        nonlocal pos
        a = np.frombuffer(b, dtype, count, pos)
        pos += a.nbytes
        return a

    ilat, ilon, ctry = take("<i2", n), take("<i2", n), take("<u2", n)
    if n % 2:
        pos += 2
    start, cell = take("<u4", nm + 1), take("<u2", rows)
    full = len(b) - pos >= rows * 6  # tiles have modis, h and blind; the overview only h
    modis = take("<u2", rows) if full else None
    h = take("<u2", rows)
    bl = take("<u2", rows) if full else None
    assert pos == len(b), (path.name, "bytes left over")
    return dict(
        lat=ilat * size / 100,
        lon=ilon * size / 100,
        size=size / 100,
        ctry=ctry,
        mon=np.repeat(np.arange(nm), np.diff(start)),
        cell=cell,
        modis=modis,
        h=np.expm1(h / 5000.0),
        blind=None if bl is None else np.expm1(bl / 5000.0),
    )


TILES = {t: read(APP_DATA / "tiles" / f"{t}.bin.gz") for t in sorted(have)}
OV = read(APP_DATA / "overview.bin.gz")


def split_at_dateline(b):
    if b[2] > 180:
        return [[b[0], b[1], 180, b[3]], [-180, b[1], b[2] - 360, b[3]]]
    return [b]


def overlaps(d, b):
    """Which cells of tile d overlap box b."""
    return np.any(
        [
            (d["lon"] + d["size"] > w) & (d["lon"] < e) & (d["lat"] + d["size"] > s) & (d["lat"] < n)
            for w, s, e, n in split_at_dateline(b)
        ],
        axis=0,
    )


def py_series(b=None, ci=0):
    """Monthly sums of the cells that overlap box b (or belong to country ci), straight from the tile files."""
    h, m, bl = np.zeros(T), np.zeros(T), np.zeros(T)
    for d in TILES.values():
        ok = d["ctry"] == ci if ci else overlaps(d, b)
        r = ok[d["cell"]]
        h += np.bincount(d["mon"][r], d["h"][r], T)
        m += np.bincount(d["mon"][r], d["modis"][r], T)
        bl += np.bincount(d["mon"][r], d["blind"][r], T)
    return h, m, bl


def quant(a, q):
    return float(np.quantile(np.asarray(a, float), q))


def py_ranges(h, bl):
    use = [t for t, mo in enumerate(months) if EST <= mo < "2026-01" and bl[t] > 0]
    lb = np.log1p(bl[use])
    lr = np.log1p(h[use]) - lb
    out = {}
    for t, mo in enumerate(months):
        if mo >= EST or len(use) < 12:
            continue
        le = np.log1p(h[t])
        d = abs(lb - le)
        o = np.argsort(d, kind="stable")[:48]
        near = o[d[o] <= np.log(5)]
        if len(near) < 12:
            near = o[:12]
        wide = R["terra_factor"] if mo < AQUA else 1.0
        widen = R["delta0"] + R["slope_per_year"] * (month_index(EST) - month_index(mo)) / 12
        out[t] = (
            max(0.0, np.expm1(le + wide * min(quant(lr[near], R["quantiles"][0]), 0) - widen)),
            np.expm1(le + wide * max(quant(lr[near], R["quantiles"][1]), 0) + widen),
        )
    return out


def theil(pts):
    """Theil-Sen slope per decade, relative to the median value."""
    slopes = np.sort([(b[1] - a[1]) / (b[0] - a[0]) for i, a in enumerate(pts) for b in pts[i + 1 :]])
    return float(np.median(slopes) * 10 / np.median([p[1] for p in pts]))


def yearly(v):
    return [(y, v[YEAR == y].sum()) for y in range(2003, 2020)]


def py_evidence(h, m, bl):
    ov = [t for t, mo in enumerate(months) if EST <= mo < "2026-01"]
    test = [t for t in ov if bl[t] > 0 and h[t] >= 20]
    if len(test) < 24:
        return None
    ov = np.array(ov)
    e1, e2 = [], []
    for t in test:
        o = ov[YEAR[ov] != YEAR[t]]
        k = h[o].sum() / max(m[o].sum(), 1)
        oc = o[CAL[o] == CAL[t]]
        e1.append(abs(k * m[t] - h[t]) / h[t])
        e2.append(abs((h[oc].sum() + 20 * k) / (m[oc].sum() + 20) * m[t] - h[t]) / h[t])
    weight = step = 0.0
    for c in range(1, 13):
        pre = [t for t, mo in enumerate(months) if AQUA <= mo < EST and CAL[t] == c]
        post = [t for t, mo in enumerate(months) if EST <= mo < "2020-01" and CAL[t] == c]
        hp, mp, ha, ma = h[pre].sum(), m[pre].sum(), h[post].sum(), m[post].sum()
        if min(hp, mp, ha, ma) > 0:
            step += (mp + ma) * np.log((ha / ma) / (hp / mp))
            weight += mp + ma
    return dict(
        months=len(test),
        model=quant([abs(bl[t] - h[t]) / h[t] for t in test], 0.5),
        one=quant(e1, 0.5),
        seasonal=quant(e2, 0.5),
        seam=float(np.expm1(step / weight)) if weight else None,
        trend=theil(yearly(h)),
        trendModis=theil(yearly(m)),
    )


JS = """
import fs from 'node:fs'
import zlib from 'node:zlib'
import { parse, tilesFor, seriesFor, rowsFor, evidenceFor, cellTotals, cellCsv } from '%s'

const W = '%s/'
const idx = JSON.parse(fs.readFileSync(W + 'index.json'))
const countries = JSON.parse(fs.readFileSync(W + 'countries.json'))
const have = new Set(idx.tiles.map(t => t.id))
const T = idx.months.length
const t0 = idx.months.indexOf('2019-11')
const t1 = idx.months.indexOf('2020-01')
const opt = { filled: idx.filled, gaps: idx.gaps, ranges: idx.world.ranges }
const job = JSON.parse(process.argv[2])

function load(id) {
  const b = zlib.gunzipSync(fs.readFileSync(W + 'tiles/' + id + '.bin.gz'))
  return parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.length))
}

function one(area, s, sets) {
  return {
    h: [...s.h],
    modis: [...s.modis],
    blind: [...s.blind],
    rows: rowsFor(idx.months, s, idx.through, opt),
    evidence: evidenceFor(idx.months, s),
    tiles: sets.length,
    cells: cellTotals(sets, t0, t1, area).filter(c => c.own).reduce((a, c) => a + c.v, 0),
    csv: cellCsv(sets, idx.months, area, t0, t1, idx.filled),
  }
}

const boxes = job.boxes.map(b => {
  const sets = tilesFor(b, have).map(load)
  const area = { bbox: b }
  return one(area, seriesFor(sets, area, T), sets)
})
const byCountry = job.countries.map(id => {
  const c = countries.find(x => x.id === id)
  const sets = tilesFor(c.bbox, have).map(load)
  const area = { bbox: c.bbox, ci: c.ci }
  return one(area, c, sets)
})
fs.writeFileSync(process.argv[3], JSON.stringify({ boxes, countries: byCountry }))
""" % (
    os.environ.get("WORLD_JS", ROOT / "frontend/src/lib/world.js"),
    APP_DATA,
)
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    (tmp / "run.mjs").write_text(JS)
    job = json.dumps({"boxes": BOXES, "countries": COUNTRIES})
    subprocess.run(["node", str(tmp / "run.mjs"), job, str(tmp / "out.json")], check=True)
    js = json.loads((tmp / "out.json").read_text())


def box_key(lat, lon):
    """One integer per 1 degree box, from whole-degree lat and lon."""
    return (lat.astype(np.int64) + 90) * 400 + lon.astype(np.int64) + 180


def name_index(cid):
    return next(i for i, n in enumerate(names) if n.lower().replace(" ", "-") == cid)


# ---- 1. the files against stage 2's arrays ----
keys = np.load(MODEL / "keys.npy")
H = np.load(MODEL / "H.npy")
BL = np.load(MODEL / "blind.npy")
S = sparse.load_npz(MODEL / "shares.npz")
names = json.loads((MODEL / "metrics.json").read_text())["country_names"]
C = len(keys)
V0 = months.index(EST)
ub, bi = np.unique(box_key(np.floor(cell_lat(keys)), np.floor(cell_lon(keys))), return_inverse=True)
nb = len(ub)
fh = np.zeros((nb, T))
fb = np.zeros((nb, T))
seen = 0
for d in TILES.values():
    k = box_key(np.floor(d["lat"]), np.floor(d["lon"]))
    j = np.searchsorted(ub, k)
    assert (ub[j] == k).all()
    seen += len(k)
    np.add.at(fh, (j[d["cell"]], d["mon"]), d["h"])
    np.add.at(fb, (j[d["cell"]], d["mon"]), d["blind"])
assert seen == C, "every cell of the grid is in exactly one tile"
ah = np.stack([np.bincount(bi, H[:, t], nb) for t in range(T)], axis=1)
ab = np.stack([np.bincount(bi, BL[:, t], nb) for t in range(T)], axis=1)
for what, f, a in (("harmonized", fh, ah), ("blind test", fb, ab)):
    worst = float((abs(f - a) / (1 + a)).max())
    assert worst < 2e-3, (what, "a 1 degree box-month in the tiles differs from the model's arrays", worst)
print(
    f"OK  all {nb:,} boxes x {T} months, harmonized and blind test: tiles = arrays (largest relative difference {worst:.1e})"
)

oh = np.zeros((nb, T))
j = np.searchsorted(ub, box_key(np.round(OV["lat"]), np.round(OV["lon"])))
np.add.at(oh, (j[OV["cell"]], OV["mon"]), OV["h"])
shown, hidden = ah >= 0.5, ah < 0.5
assert (abs(oh - ah)[shown] / (1 + ah[shown])).max() < 2e-3 and oh[
    hidden
].sum() == 0, "the overview differs from the model's arrays"
assert ah[hidden].sum() < 2e-3 * ah.sum(), "the overview leaves out more than 0.2 % of the record"

HT, BT = np.asarray(S @ H.astype(np.float64)), np.asarray(S @ BL.astype(np.float64))
for c in countries[1:]:
    i = name_index(c["id"])
    assert (
        abs(np.array(c["h"]) - HT[i]).max() <= 0.051 and abs(np.array(c["blind"]) - BT[i]).max() <= 0.051
    ), (c["id"], "country series differ from the model's arrays")
assert abs(np.array(countries[0]["h"]) - H.sum(axis=0, dtype=np.float64)).max() <= 0.06
world_modis = sum(np.bincount(d["mon"], d["modis"], T) for d in TILES.values())
assert (
    world_modis == np.array(countries[0]["modis"])
).all(), "MODIS counts in the tiles and in the world series differ"
print(
    f"OK  {len(countries) - 1} country series and the world = arrays; overview = arrays; MODIS in tiles = world series"
)

# ---- 2 and 3. world.js against the independent reader and the independent statistics ----
CELLS_T0, CELLS_T1 = months.index("2019-11"), months.index("2020-01")  # the months of the cells download


def rounds_to(shown, x):
    """shown is x rounded to a whole number (the two readers differ in the 7th digit, which matters at .5)."""
    return abs(shown - x) <= 0.5 + 2e-4 * max(x, 1)


def check_cells(tag, j, h):
    """The per-cell totals and the cells download against the monthly series h of the same cells."""
    want = h[CELLS_T0 : CELLS_T1 + 1].sum()
    lines = j["csv"].split("\n")[1:]
    per_month = {}
    assert abs(j["cells"] - want) <= 1e-4 * max(want, 1), (tag, "per-cell totals do not add up to the series")
    for ln in lines:
        f = ln.split(",")
        per_month[f[0]] = per_month.get(f[0], 0) + float(f[5])
        assert f[6] == "snpp" and float(f[3]) == 0.25, (tag, ln)
    assert set(per_month) <= set(months[CELLS_T0 : CELLS_T1 + 1]) and all(
        abs(per_month.get(months[t], 0) - h[t]) <= 0.02 + 0.005 * len(lines)
        for t in range(CELLS_T0, CELLS_T1 + 1)
    ), (tag, "the cells download does not match the series, month by month")
    return f"{len(lines)} cell rows"


def check(tag, j, h, m, bl):
    """The rows, ranges and evidence world.js made from the series (h, m, bl) against the Python rules."""
    rows = j["rows"]
    if h.sum() == 0 and m.sum() == 0:
        assert rows == [] and j["evidence"] is None
        return "no fire: no rows"
    assert len(rows) == T and [r["month"] for r in rows] == months
    rng = py_ranges(h, bl)
    bad = 0
    for t, r in enumerate(rows):
        mo = months[t]
        est = mo < EST
        assert (
            r["count"] == int(r["count"]) and rounds_to(r["count"], h[t]) and (r["source"] == "model") == est
        ), (tag, mo, "count or source", r["count"], h[t])
        md = np.median(h[(CAL == CAL[t]) & complete])
        assert abs(r["median"] - md) <= 0.0051 + 1e-6 * md, (tag, mo, "median")
        want = None if mo == partial or md <= 0 else r["count"] / md
        assert (r["anomaly"] is None) == (want is None) and (
            want is None or abs(r["anomaly"] - want) <= 0.0051
        ), (tag, mo, "times-median", r["anomaly"], want)
        assert bool(r.get("partial")) == (mo == partial) and r["modis"] == round(m[t]), (
            tag,
            mo,
            "month in progress or MODIS",
        )
        assert (r["blind"] is None) == (est or bl[t] <= 0) and (
            r["blind"] is None or rounds_to(r["blind"], bl[t])
        ), (tag, mo, "blind value", r["blind"], bl[t])
        if not est:
            assert r["lo"] is None, (tag, mo, "a range after 2012")
        elif t in rng:
            assert r["lo"] <= h[t] + 0.006 and r["hi"] >= h[t] - 0.006, (
                tag,
                mo,
                "an estimate outside its own range",
            )
            bad += (
                abs(r["lo"] - rng[t][0]) > 0.006 + 1e-6 * rng[t][0]
                or abs(r["hi"] - rng[t][1]) > 0.006 + 1e-6 * rng[t][1]
            )
        else:
            assert r["lo"] is None, (tag, mo)
    # exact ties among the nearest months may be broken differently
    assert bad <= 2, (tag, "ranges differ from the rule", bad)
    ev, pe = j["evidence"], py_evidence(h, m, bl)
    assert (ev is None) == (pe is None), (tag, "evidence present")
    if ev:
        for k in ("months", "model", "one", "seasonal", "seam"):
            assert ev[k] is not None and abs(ev[k] - pe[k]) <= 1e-6 * max(1, abs(pe[k])), (
                tag,
                k,
                ev[k],
                pe[k],
            )
        for k in ("trend", "trendModis"):
            assert (
                abs(ev[k]["v"] - pe[k]) <= 1e-6 * max(1, abs(pe[k]))
                and ev[k]["lo"] <= ev[k]["v"] <= ev[k]["hi"]
                and (ev[k]["from"], ev[k]["to"]) == (2003, 2019)
            ), (tag, k, ev[k], pe[k])
    return f"{len(rows)} months, {len(rng)} ranges, evidence {'yes' if ev else 'no'}"


for b, j in zip(BOXES, js["boxes"]):
    h, m, bl = py_series(b)
    for k, v in (("h", h), ("modis", m), ("blind", bl)):
        assert abs(np.array(j[k]) - v).max() <= 1e-4 * max(v.max(), 1), (
            b,
            k,
            "world.js and the Python reader disagree",
        )
    print(f"OK  box {str(b):<30}", check(b, j, h, m, bl) + (", " + check_cells(b, j, h) if h.sum() else ""))
country = np.load(MODEL / "country.npy")
for cid, j in zip(COUNTRIES, js["countries"]):
    c = next(x for x in countries if x["id"] == cid)
    h, m, bl = (np.array(c[k], float) for k in ("h", "modis", "blind"))
    th = py_series(ci=c["ci"])[0]
    own = country == name_index(cid)  # the cells where this country has the largest share
    assert abs(th[V0:] - H[own][:, V0:].sum(axis=0)).max() <= 1e-3 * max(th.max(), 1), (
        cid,
        "the country's own cells in the tiles are not the model's",
    )
    print(f"OK  country {cid:<26}", check(cid, j, h, m, bl) + ", " + check_cells(cid, j, th))
print("the browser code, the data files and the model arrays agree")
