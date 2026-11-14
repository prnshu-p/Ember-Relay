"""Stage 3: stage 2's arrays -> the web app's data in frontend/public/world/ (index.json, countries.json,
overview.bin.gz and one tiles/<id>.bin.gz per 10 degree tile).
Run: python3 pipeline/stage3_export.py"""

import gzip
import json
import shutil
import struct

import numpy as np
import pandas as pd
from scipy import ndimage, sparse

from common import APP_DATA, CELL, CELLS, MODEL, T0, cell_key, month_index, month_name

THR = 0.25  # smallest estimate a tile keeps
Q = 5000.0
VIIRS0 = month_index("2012-02")
TEST_KEYS = ("record", "seasonal_ratio", "one_ratio", "best_simple", "seam", "ratio")
WORLD_KEYS = (
    "cells",
    "hotspots",
    "tests",
    "record_is",
    "countries_tested",
    "countries_better",
    "benchmark",
    "steps",
    "seam_countries_median_abs",
    "noaa20",
    "fresh2026",
    "final_forward",
    "ranges",
    "persistent_sources",
    "mask_check",
    "bias_by_year",
)


def quantize(a):
    return np.minimum(np.round(np.log1p(np.maximum(a, 0)) * Q), 65535).astype("<u2")


def write_bin(path, ilat, ilon, cidx, size100, months, cols):
    """Write a gzipped BAC2 file and return its number of rows. Layout, little-endian:
    "BAC2", uint32 nCells, nMonths, nRows, cell size in 1/100 degree;
    int16 lat index[nCells], int16 lon index[nCells], uint16 country[nCells] (+2 padding bytes if nCells is odd);
    uint32 first row of each month[nMonths + 1]; uint16 cell[nRows], modis[nRows], h[nRows], blind[nRows].
    h and blind are round(log1p(x) * 5000). cols: per month (cell idx, modis, h, blind); the overview has no
    modis or blind (None), and no such arrays in the file."""
    start = np.zeros(months + 1, "<u4")
    start[1:] = np.cumsum([len(c[0]) for c in cols])

    def column(i, convert):
        if cols[0][i] is None:
            return np.zeros(0, "<u2").tobytes()
        return np.concatenate([convert(c[i]) for c in cols]).tobytes()

    body = [
        np.asarray(ilat, "<i2").tobytes(),
        np.asarray(ilon, "<i2").tobytes(),
        np.asarray(cidx, "<u2").tobytes(),
    ]
    if len(ilat) % 2:
        body.append(b"\0\0")
    body += [
        start.tobytes(),
        column(0, lambda a: a.astype("<u2")),
        column(1, lambda a: np.minimum(a, 65535).astype("<u2")),
        column(2, quantize),
        column(3, quantize),
    ]
    header = b"BAC2" + struct.pack("<4I", len(ilat), months, int(start[-1]), size100)
    path.write_bytes(gzip.compress(header + b"".join(body), 6))
    return int(start[-1])


def tile_name(s, w):
    return f"{'n' if s >= 0 else 's'}{abs(s):02d}{'e' if w >= 0 else 'w'}{abs(w):03d}"


def main_groups(y, x, w):
    """The cells that frame a country on the map: cells within 2 degrees of each other form a group, and the
    groups with most fire are taken until they hold 95 % of it (the mainland, not far islands)."""
    gy, gx = y - y.min(), x - x.min()
    grid = np.zeros((gy.max() + 1, gx.max() + 1), bool)
    grid[gy, gx] = True
    labels, n = ndimage.label(ndimage.binary_dilation(grid, np.ones((17, 17), bool)))
    group = labels[gy, gx]
    fire = np.bincount(group, w, n + 1)
    order = np.argsort(-fire)
    return np.isin(group, order[: np.searchsorted(np.cumsum(fire[order]) / fire.sum(), 0.95) + 1])


def round1(a):
    return [round(float(x), 1) for x in a]


def series(h, m, b):
    return {"h": round1(h), "modis": [int(x) for x in m], "blind": round1(b)}


def main():
    H, BL, V = (np.load(MODEL / f"{n}.npy") for n in ("H", "blind", "V"))
    keys = np.load(MODEL / "keys.npy")
    country = np.load(MODEL / "country.npy")
    met = json.loads((MODEL / "metrics.json").read_text())
    S = sparse.load_npz(MODEL / "shares.npz")
    C, T = H.shape
    ilat = (keys // 4000 - 400).astype(np.int32)  # the inverse of cell_key
    ilon = (keys % 4000 - 800).astype(np.int32)
    lat, lon = ilat * CELL, ilon * CELL

    # The app shows MODIS as detected; stage 2's M is scaled up for outage days, so read stage 1's counts.
    mo = pd.concat(
        [
            pd.read_parquet(f, columns=["ilat", "ilon", "ym", "n"])
            for f in sorted(CELLS.glob("modis_20[0-9][0-9].parquet"))
        ]
    )
    k = cell_key(mo.ilat.values, mo.ilon.values)
    ci = np.minimum(np.searchsorted(keys, k), C - 1)
    ok = (keys[ci] == k) & (mo.ym.values >= T0)
    M = np.zeros((C, T), np.float32)
    M[ci[ok], mo.ym.values[ok] - T0] = mo.n.values[ok]
    months = [month_name(t) for t in range(T)]

    if APP_DATA.exists():
        shutil.rmtree(APP_DATA)
    (APP_DATA / "tiles").mkdir(parents=True)
    bx_key = (np.floor(lat).astype(np.int64) + 90) * 400 + np.floor(lon).astype(np.int64) + 180
    boxes, bx = np.unique(bx_key, return_inverse=True)
    tile_key = (np.floor(lat / 10).astype(np.int64) + 9) * 40 + np.floor(lon / 10).astype(np.int64) + 18

    def box_sum(a):
        return np.bincount(bx, a, len(boxes))

    def keep_largest(a, kept):
        """In boxes where no cell is kept, keep the largest one: it will carry the box's sum."""
        empty = (box_sum(a) > 0) & (box_sum(a * kept) == 0)
        cells = np.nonzero(empty[bx] & (a > 0))[0]
        if len(cells):
            by_box = cells[np.lexsort((a[cells], bx[cells]))]
            kept[by_box[np.r_[bx[by_box][1:] != bx[by_box][:-1], True]]] = True

    def fold(a, kept):
        """Give the dropped cells' sum to the kept cells of the same 1 degree box."""
        before, after = box_sum(a), box_sum(a * kept)
        return a * kept * np.where(after > 0, before / np.maximum(after, 1e-30), 0.0)[bx]

    # Tiles keep the cells where a sensor saw fire or the estimate is at least THR; smaller estimates fold into
    # their box, so every 1 degree box total stays stage 2's.
    Hk = np.zeros((C, T), np.float32)
    Bk = np.zeros((C, T), np.float32)
    keep = np.zeros((C, T), bool)
    worst = 0.0
    for t in range(T):
        h, b = H[:, t], BL[:, t]
        kept = (M[:, t] > 0) | (V[:, t] > 0) | (h >= THR)
        if t < VIIRS0:
            keep_largest(h, kept)
        keep_largest(b, kept)
        Hk[:, t] = fold(h, kept) if t < VIIRS0 else h * kept
        Bk[:, t] = fold(b, kept)
        keep[:, t] = kept
        for x, y in ((Hk[:, t], h), (Bk[:, t], b)):
            worst = max(worst, float((np.abs(box_sum(x) - box_sum(y)) / (1 + box_sum(y))).max()))
    assert worst < 1e-4, ("a 1 degree box total changed", worst)
    print(
        f"cell-months kept: {int(keep.sum()):,} of {C * T:,}; largest relative change of a 1 degree box total: {worst:.1e}"
    )

    tiles = []
    for tk in np.unique(tile_key):
        cells = np.nonzero(tile_key == tk)[0]
        s, w = (tk // 40 - 9) * 10, (tk % 40 - 18) * 10
        cols = []
        for t in range(T):
            j = np.nonzero(keep[cells, t])[0]
            c = cells[j]
            cols.append((j, M[c, t], Hk[c, t], Bk[c, t]))
        name = tile_name(s, w)
        rows = write_bin(
            APP_DATA / "tiles" / f"{name}.bin.gz", ilat[cells], ilon[cells], country[cells] + 1, 25, T, cols
        )
        tiles.append({"id": name, "s": int(s), "w": int(w), "cells": int(len(cells)), "rows": rows})

    # Overview: harmonized hotspots per 1 degree box, boxes under half a hotspot a month left out.
    box_lat = (boxes // 400 - 90).astype(np.int32)
    box_lon = (boxes % 400 - 180).astype(np.int32)
    cols = []
    for t in range(T):
        v = box_sum(Hk[:, t])
        j = np.nonzero(v >= 0.5)[0]
        cols.append((j, None, v[j], None))
    # Each box is shown as part of the country with most of its hotspots (only to highlight a country).
    wt = np.asarray(H, np.float64).sum(axis=1)
    has = country >= 0
    pairs, pair_of = np.unique(np.stack([bx[has], country[has]]), axis=1, return_inverse=True)
    pair_box, pair_country = pairs[0], pairs[1]
    pair_fire = np.bincount(pair_of.ravel(), wt[has])
    o = np.lexsort((pair_fire, pair_box))
    top = np.r_[pair_box[o][1:] != pair_box[o][:-1], True]
    box_country = np.zeros(len(boxes), np.int64)
    box_country[pair_box[o][top]] = pair_country[o][top] + 1
    orows = write_bin(APP_DATA / "overview.bin.gz", box_lat, box_lon, box_country, 100, T, cols)

    # Country series come from stage 2's arrays, untouched by the folding: a border cell counts for each country
    # by its share of the hotspots there.
    names = met["country_names"]
    byname = {r["country"]: r for r in met["countries"]}
    HT, MT, BT = (np.asarray(S @ A.astype(np.float64)) for A in (H, M, BL))
    out = [
        {
            "id": "world",
            "name": "World",
            "bbox": [-180, -60, 180, 80],
            **series(*(A.sum(axis=0, dtype=np.float64) for A in (H, M, BL))),
            "tests": None,
        }
    ]
    for i, name in enumerate(names):
        mask = country == i
        y, x = ilat[mask], ilon[mask]
        if not mask.any() or wt[mask].sum() <= 0:
            continue
        main = main_groups(y, x, wt[mask])
        y, x, wk = y[main], x[main], wt[mask][main]
        if x.max() - x.min() > 1200:  # across the date line
            east = x >= 0
            small = east if wk[east].sum() < wk[~east].sum() else ~east
            if wk[small].sum() < 0.02 * wk.sum():
                y, x = y[~small], x[~small]  # a sliver beyond the line: leave it out of the frame
            else:
                x = np.where(x < 0, x + 1440, x)  # the box runs past 180; the app splits it there
        w, s, e, n = x.min() * CELL, y.min() * CELL, x.max() * CELL, y.max() * CELL
        r = byname.get(name)
        out.append(
            {
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "ci": i + 1,
                "bbox": [
                    round(float(w), 2),
                    round(float(s), 2),
                    round(float(e) + CELL, 2),
                    round(float(n) + CELL, 2),
                ],
                **series(HT[i], MT[i], BT[i]),
                "tests": None if r is None else {k: r[k] for k in TEST_KEYS},
            }
        )
    out[1:] = sorted(out[1:], key=lambda r: r["name"])
    (APP_DATA / "countries.json").write_text(json.dumps(out, separators=(",", ":")))

    # The last whole day of data: NOAA-20 carries the record now.
    through = max(
        pd.read_parquet(f, columns=["acq_date"]).acq_date.max()
        for f in CELLS.glob("viirs-jpss1_20[0-9][0-9]_daily.parquet")
    )
    index = {
        "months": months,
        "through": through,
        "tiles": tiles,
        "overview_rows": orows,
        "world": {k: met[k] for k in WORLD_KEYS if k in met},
        "gaps": met["outages"]["months"],  # month -> {satellite: share of its detections lost to outages}
        "filled": met["noaa20"]["filled"],  # month -> share of the VIIRS count taken from NOAA-20
    }
    (APP_DATA / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    size = sum(f.stat().st_size for f in APP_DATA.rglob("*") if f.is_file())
    print(
        f"{len(tiles)} tiles, {sum(t['rows'] for t in tiles):,} rows; overview {orows:,} rows; {len(out)} country series; {size / 1e6:.0f} MB in {APP_DATA}"
    )
    print("largest tiles:", sorted(((t["rows"], t["id"]) for t in tiles), reverse=True)[:5])


if __name__ == "__main__":
    main()
