"""Stage 2: the harmonization model, its blind tests and the harmonized record (method: docs/SUBMISSION.md).

data/global/cells/ (stage 1) -> data/global/model/: H.npy and the other arrays, shares.npz, metrics.json.
Run: python3 pipeline/stage2_model.py   (about half an hour on 8 cores)
"""

import json

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingRegressor

from common import CELLS, MODEL, T0, cell_key, cell_lat, cell_lon, log, month_index, month_name

AQUA = month_index("2002-07")  # Aqua joins Terra
VIIRS0 = month_index("2012-02")  # first month of S-NPP
MID = month_index("2016-01")
SPLIT = month_index("2019-01")
DRIFT = month_index("2020-01")  # the MODIS orbits drift from here on
REPHASE = month_index("2024-04")  # NOAA-20 was re-phased in March-April 2024
FRESH = month_index("2026-01")  # no blind test trains on these months

P0 = 0.08  # share of all-zero cell-months kept for training (weighted up by 1/P0)
W_LOCAL = 0.5  # weight of the best simple method in the record's 1 degree box totals (E3, E8, E10)
ALPHA = 0.5  # tiles weighted by (MODIS total)^-ALPHA, at most 20x, so Africa does not drown out the rest
GAP = 0.2  # a month in which a satellite lost more than this share of its detections is kept out of training
# persistent heat source: a cell-month with at least N detections, each spot seen R times on average
# (N, R next to a volcano, R elsewhere) (E10)
PERSIST = {"modis": (30, 4.0, 5.0), "viirs": (100, 6.0, 6.0)}
# chosen on validation years only (E8)
HGB = dict(
    loss="poisson",
    max_iter=600,
    learning_rate=0.06,
    max_leaf_nodes=255,
    min_samples_leaf=50,
    early_stopping=False,
    random_state=0,
)
STATS = (
    "nAd nAn nTd nTn frp_sum frp_max day_sum area_sum bright_sum conf_sum weak_sum ndays npix"
    " frp50 frp90 maxday t_frp_sum t_frp_max t_area_sum t_conf_sum t_weak_sum"
).split()
BLOCK = [dy * 4000 + dx for dy in (-1, 0, 1) for dx in (-1, 0, 1)]  # cell_key offsets of a cell's 3 x 3 block


def read(pattern, columns=None):
    files = sorted(CELLS.glob(pattern))
    return pd.concat([pd.read_parquet(f, columns=columns) for f in files], ignore_index=True)


def keys_of(d):
    return cell_key(d.ilat.values, d.ilon.values)


def box_index(lat, lon, size):
    """Index of each cell's size-degree box, the boxes numbered in order of (row, column)."""
    row = np.floor(lat / size).astype(np.int64)
    col = np.floor(lon / size).astype(np.int64)
    key = (row + int(90 / size)) * int(400 / size) + col + int(180 / size)
    return np.unique(key, return_inverse=True)[1]


def mean_or_zero(s, n):
    return np.where(n > 0, s / np.maximum(n, 1), 0)


def outages(T):
    """Which days did each satellite lose? From the world's detections per day and satellite.

    A day should bring what the partner saw that day times their usual ratio over the 61 days around it
    (Terra with Aqua; S-NPP with NOAA-20, or MODIS before NOAA-20 flew), or with no healthy partner the
    61-day median. A day under half of that is an outage.
    -> ({sat: share of each month lost}, [(sat, first day, last day, share lost)])
    """

    def world_per_day(prefix, sat=None):
        d = read(f"{prefix}_20[0-9][0-9]_daily.parquet")
        return (d[d.sat == sat] if sat else d).groupby("acq_date").n.sum()

    def around(x):
        return x.rolling(61, center=True, min_periods=15).median()

    last = T0 + T - 1
    end = pd.Timestamp(year=last // 12, month=last % 12 + 1, day=1) + pd.offsets.MonthEnd(0)
    days = pd.date_range("2000-11-01", end)
    count = {
        "terra": world_per_day("modis", "T"),
        "aqua": world_per_day("modis", "A"),
        "snpp": world_per_day("viirs-snpp"),
        "noaa20": world_per_day("viirs-jpss1"),
    }
    life = {k: (pd.Timestamp(v.index.min()), pd.Timestamp(v.index.max())) for k, v in count.items()}
    life["modis"] = life["terra"]
    count = {
        k: v.set_axis(pd.to_datetime(v.index)).reindex(days, fill_value=0).astype(float)
        for k, v in count.items()
    }
    count["modis"] = count["terra"] + count["aqua"]
    alive = {k: pd.Series((days >= a) & (days <= b), days) for k, (a, b) in life.items()}
    rel = {k: (v / around(v.where(alive[k])).replace(0, np.nan)).fillna(0) for k, v in count.items()}
    month = np.asarray(days.year * 12 + days.month - 1 - T0)
    lost, runs = {}, []
    for k, partners in (
        ("terra", ["aqua"]),
        ("aqua", ["terra"]),
        ("snpp", ["modis", "noaa20"]),
        ("noaa20", ["modis", "snpp"]),
    ):
        n = count[k]
        exp = around(n.where(alive[k]))
        for p in partners:  # the later partner wins where it is healthy that day
            ok = alive[p] & (rel[p] > 0.5)
            usual = around((n / count[p].replace(0, np.nan)).where(ok & alive[k] & (rel[k] > 0.5))).ffill()
            exp = (count[p] * usual).where(ok & usual.notna(), exp)
        frac = (n / exp.replace(0, np.nan)).fillna(1)
        loss = (1 - frac).where(frac < 0.5, 0.0).where(alive[k], 0.0)
        if k == "snpp":
            loss = loss.where(
                days <= life[k][1], 1.0
            )  # once S-NPP has ended every day is lost: NOAA-20 takes over
        w = exp.fillna(0).where((days >= life[k][0]) & ((days <= life[k][1]) | (k == "snpp")), 0.0)
        lost[k] = np.bincount(month, loss * w, T) / np.maximum(np.bincount(month, w, T), 1e-9)
        d = loss[(loss > 0) & alive[k]]
        run_id = (d.index.to_series().diff().dt.days != 1).cumsum()
        for _, r in d.groupby(run_id):
            runs.append((k, str(r.index[0].date()), str(r.index[-1].date()), round(float(r.mean()), 2)))
    return lost, runs


def persistent_sources(mo, vi, n2):
    """Cells of persistent heat sources (lava, gas flares, industry), and the cells next to a volcano.

    Lava and flares light the same spots day and night for weeks; a vegetation fire moves on (peat and the
    longest forest fires come close for a month or three, hence four such months within a year).
    """

    def typed_volcano(prefix, per):  # detections FIRMS typed as volcano, per grid cell
        st = read(f"{prefix}_20[0-9][0-9]_static.parquet")
        st = st[st.type == 1]
        spot = st.spot.values
        keys = cell_key((spot // 100000 - 40000) // per, (spot % 100000 - 40000) // per)
        return pd.Series(st.n.values, keys).groupby(level=0).sum()

    volcano = (
        typed_volcano("viirs-snpp", 50)
        .add(typed_volcano("viirs-jpss1", 50), fill_value=0)
        .add(typed_volcano("modis", 25), fill_value=0)
    )
    volcano = volcano.index.values[volcano.values >= 10]
    near = np.unique((volcano[:, None] + np.array(BLOCK)).ravel())
    gone = set()
    for d, (nmin, r_near, r_far) in ((mo, PERSIST["modis"]), (vi, PERSIST["viirs"]), (n2, PERSIST["viirs"])):
        k = keys_of(d)
        isnear = np.isin(k, near)
        hot = (d.n.values >= nmin) & (d.n.values >= np.where(isnear, r_near, r_far) * d.npix.values)
        gone |= set(k[hot & isnear])  # next to a volcano one such month is enough
        far = pd.DataFrame({"k": k[hot & ~isnear], "ym": d.ym.values[hot & ~isnear]}).sort_values(["k", "ym"])
        gone |= set(far.k[far.groupby("k").ym.diff(3) < 12])  # elsewhere: four such months within twelve
    return np.array(sorted(gone), np.int64), near


class Grid:
    """Every 0.25 degree cell where either sensor ever saw a vegetation fire x every month from Nov 2000."""

    def __init__(self):
        cols = ["ilat", "ilon", "ym", "n", "npix"]
        mo = read("modis_20[0-9][0-9].parquet")
        vi = read("viirs-snpp_20[0-9][0-9].parquet", cols)
        n2 = read("viirs-jpss1_20[0-9][0-9].parquet", cols)
        gone, near = persistent_sources(mo, vi, n2)
        self.persistent = {"cells": int(len(gone)), "next_to_volcano": int(np.isin(gone, near).sum())}
        for name, d in (("modis", mo), ("snpp", vi), ("noaa20", n2)):
            hot = np.isin(keys_of(d), gone)
            self.persistent[name] = int(d.n[hot].sum())
            d.drop(d.index[hot], inplace=True)
            d.reset_index(drop=True, inplace=True)

        keys = np.unique(np.concatenate([keys_of(mo), keys_of(vi), keys_of(n2)]))
        C = len(keys)
        T = int(max(mo.ym.max(), vi.ym.max(), n2.ym.max())) - T0 + 1
        self.keys, self.C, self.T = keys, C, T
        self.lat = cell_lat(keys).astype(np.float32)
        self.lon = cell_lon(keys).astype(np.float32)

        def locate(d):
            """Grid cell and month of the table's rows that fall inside the grid."""
            k = keys_of(d)
            ci = np.minimum(np.searchsorted(keys, k), C - 1)
            ok = (keys[ci] == k) & (d.ym.values >= T0)
            return ci[ok], d.ym.values[ok] - T0, ok

        def place(d, col):
            ci, ti, ok = locate(d)
            a = np.zeros((C, T), np.float32)
            a[ci, ti] = d[col].values[ok]
            return a

        self.Mraw = place(mo, "n")
        self.MTraw = place(mo, "nT")
        self.Vraw = place(vi, "n")
        self.N20 = place(n2, "n")
        ci, ti, ok = locate(mo)
        self.IDX = np.full((C, T), -1, np.int32)  # row of each cell-month in the MODIS table, -1 = none
        self.IDX[ci, ti] = np.arange(len(mo), dtype=np.int32)[ok]
        self.S = {c: mo[c].values.astype(np.float32) for c in STATS}

        self.NB = np.full((C, 8), C, np.int32)  # the 8 neighbours of each cell, C = none
        for j, offset in enumerate(o for o in BLOCK if o):
            k = keys + offset
            i = np.minimum(np.searchsorted(keys, k), C - 1)
            hit = keys[i] == k
            self.NB[hit, j] = i[hit]
        self.bx = box_index(self.lat, self.lon, 1)
        self.tl = box_index(self.lat, self.lon, 10)
        self.cal = (np.arange(T) + T0) % 12  # 0 = January
        self.repair()
        phase = 2 * np.pi * (self.cal + 1) / 12
        self.msin = np.sin(phase).astype(np.float32)
        self.mcos = np.cos(phase).astype(np.float32)

        # each cell's MODIS climatology over 2003-2019 (both satellites, stable orbits), as sums so that a
        # row can leave its own month out
        self.ref = np.zeros(T, bool)
        self.ref[month_index("2003-01") : DRIFT] = True
        self.csum = np.stack(
            [self.M[:, self.ref & (self.cal == c)].sum(axis=1) for c in range(12)], axis=1
        ).astype(np.float32)
        self.cn = np.array([(self.ref & (self.cal == c)).sum() for c in range(12)], np.float32)
        self.ctot = self.M[:, self.ref].sum(axis=1).astype(np.float32)
        log(
            f"grid: {C:,} cells x {T} months; MODIS {self.Mraw.sum():,.0f}, S-NPP {self.Vraw.sum():,.0f}, "
            f"NOAA-20 {self.N20.sum():,.0f} hotspots; persistent heat sources left out: {self.persistent}"
        )

    def repair(self):
        """Correct the counts for outages. Sets M and MT (MODIS and Terra, scaled up for lost days),
        V (S-NPP, its lost share filled from NOAA-20 or scaled up), fill (the share of each month's V
        that came from NOAA-20) and gappy (months kept out of training)."""
        T = self.T
        lost, self.runs = outages(T)
        month = np.arange(T)
        self.sT = (1 / np.maximum(1 - lost["terra"], 0.2)).astype(np.float32)
        self.sA = (1 / np.maximum(1 - lost["aqua"], 0.2)).astype(np.float32)
        self.MT = self.MTraw * self.sT
        self.M = self.MT + (self.Mraw - self.MTraw) * self.sA

        ntl = self.tl.max() + 1

        def per_tile(a):
            return np.stack([np.bincount(self.tl, a[:, t], ntl) for t in range(T)], axis=1)

        Vt = per_tile(self.Vraw)
        Nt = per_tile(self.N20)
        has_n = Nt.sum(axis=0) > 0
        healthy = has_n & (Vt.sum(axis=0) > 0) & (lost["snpp"] < 0.02) & (lost["noaa20"] < 0.02)
        self.V = self.Vraw.copy()
        self.fill = np.zeros(T, np.float32)
        kns = []
        for t in np.nonzero((lost["snpp"] > 0) & (month >= VIIRS0))[0]:
            if has_n[t] and lost["noaa20"][t] < 0.5:
                # S-NPP / NOAA-20 per tile over the 24 healthy months before (their ratio moves slowly)
                before = np.nonzero(healthy & (month < t))[0]
                h = before[-24:] if len(before) >= 6 else np.nonzero(healthy)[0][:24]
                v = Vt[:, h].sum(axis=1)
                n = Nt[:, h].sum(axis=1)
                kg = v.sum() / max(n.sum(), 1)
                kn = (v + 200 * kg) / (n + 200)
                kns.append(kn)
                self.V[:, t] += lost["snpp"][t] * kn[self.tl] * self.N20[:, t] / (1 - lost["noaa20"][t])
                self.fill[t] = lost["snpp"][t]
            else:
                self.V[:, t] /= max(1 - lost["snpp"][t], 0.2)
        self.gappy = (
            (lost["terra"] > GAP)
            | (lost["aqua"] > GAP)
            | ((lost["snpp"] > GAP) & (self.fill == 0) & (month >= VIIRS0))
        )
        self.twin_months = [int(t) for t in np.nonzero(healthy & (month >= VIIRS0))[0]]

        r = Vt.sum(axis=0)[healthy] / Nt.sum(axis=0)[healthy]
        if kns:
            tiles = np.concatenate(kns)
            tile_range = [float(np.percentile(tiles, 5)), float(np.percentile(tiles, 95))]
        else:
            tile_range = None
        self.noaa20 = {
            "healthy_months": int(healthy.sum()),
            "usual_monthly_ratio": float(np.median(r)),
            "ratio_first_year": float(np.median(r[:12])),
            "ratio_last_year": float(np.median(r[-12:])),
            "tile_ratio_range": tile_range,
            "filled": {
                month_name(t): round(float(self.fill[t]), 3) for t in np.nonzero(self.fill >= 0.03)[0]
            },
        }
        self.gaps = {}
        for t in range(T):
            share = {
                k: round(float(lost[k][t]), 3)
                for k in ("terra", "aqua", "snpp", "noaa20")
                if lost[k][t] >= 0.03 and (k != "snpp" or t >= VIIRS0)
            }
            if share:
                self.gaps[month_name(t)] = share
        log(
            f"outages: {len(self.runs)} runs of lost days; months with 3 % or more lost: {len(self.gaps)}; "
            f"months partly from NOAA-20: {self.noaa20['filled']}; "
            f"kept out of training: {[month_name(t) for t in np.nonzero(self.gappy)[0]]}"
        )

    def span(self, a, b):
        """Mask of months a to b - 1."""
        t = np.arange(self.T)
        return (t >= a) & (t < b)

    def small_fire(self, tm, terra=False):
        """VIIRS hotspots in the months tm when MODIS (or Terra alone) saw nothing in the cell: sums and
        counts per cell and calendar month."""
        empty = ((self.MT if terra else self.M) == 0) & tm[None, :]
        v = self.V * empty
        vs = np.stack([v[:, self.cal == c].sum(axis=1) for c in range(12)], axis=1)
        vn = np.stack([empty[:, self.cal == c].sum(axis=1) for c in range(12)], axis=1).astype(np.float32)
        return vs.astype(np.float32), vn, tm

    def context(self, cnt, ci, ti):
        """Log counts of the 8 neighbours, the month before and the month after."""
        nb = self.NB[ci]
        ok = nb < self.C
        nbr = (cnt[np.where(ok, nb, 0), ti[:, None]] * ok).sum(axis=1)
        prev = np.where(ti > 0, cnt[ci, np.maximum(ti - 1, 0)], 0)
        nxt = np.where(ti < self.T - 1, cnt[ci, np.minimum(ti + 1, self.T - 1)], 0)
        return np.log1p(nbr), np.log1p(prev), np.log1p(nxt)

    def feats(self, ci, ti, sf, terra=False):
        """Model inputs for cell-months (ci, ti). The climatologies leave the row's own month out, so that
        a row inside the years they are built from looks like the rows outside them."""
        r = self.IDX[ci, ti]
        has = r >= 0
        rr = np.where(has, r, 0)

        def stat(name):
            return np.where(has, self.S[name][rr], 0.0)

        cnt = self.MT if terra else self.M
        m = cnt[ci, ti]
        nbr, prev, nxt = self.context(cnt, ci, ti)
        # means use the counts as detected; counts are scaled up for lost days
        safe = np.maximum((self.MTraw if terra else self.Mraw)[ci, ti], 1)
        sT = self.sT[ti]
        sA = self.sA[ti]
        vs, vn, tm = sf
        cal = self.cal[ti]
        own = tm[ti] & (m == 0)
        v = self.V[ci, ti]
        vclim = np.log1p(mean_or_zero(vs[ci, cal] - own * v, vn[ci, cal] - own))
        vcell = np.log1p(mean_or_zero(vs[ci].sum(axis=1) - own * v, vn[ci].sum(axis=1) - own))
        inref = self.ref[ti]
        mm = self.M[ci, ti] * inref
        clim = np.log1p(np.maximum(self.csum[ci, cal] - mm, 0) / (self.cn[cal] - inref))
        cellmean = np.log1p(np.maximum(self.ctot[ci] - mm, 0) / (self.ref.sum() - inref))
        shared = [
            self.msin[ti],
            self.mcos[ti],
            nbr,
            prev,
            nxt,
            clim,
            cellmean,
            vclim,
            vcell,
            self.lat[ci],
            self.lon[ci],
        ]
        if terra:
            cols = [
                np.log1p(m),
                stat("t_frp_sum") / safe,
                stat("t_frp_max"),
                np.where(m > 0, stat("nTd") / safe, 0.5),
                stat("t_area_sum") / safe,
                stat("t_conf_sum") / safe,
                np.log1p(stat("nTd") * sT),
                np.log1p(stat("nTn") * sT),
                stat("t_weak_sum") / safe,
            ]
        else:
            cols = [
                np.log1p(m),
                stat("frp_sum") / safe,
                stat("frp_max"),
                np.where(m > 0, stat("day_sum") / safe, 0.5),
                stat("area_sum") / safe,
                stat("bright_sum") / safe,
                stat("conf_sum") / safe,
                np.log1p(stat("nAd") * sA),
                np.log1p(stat("nAn") * sA),
                np.log1p(stat("nTd") * sT),
                np.log1p(stat("nTn") * sT),
                np.log1p(stat("ndays")),
                np.log1p(stat("maxday")),
                np.log1p(stat("npix")),
                stat("frp50"),
                stat("frp90"),
                stat("weak_sum") / safe,
            ]
        return np.column_stack(cols + shared).astype(np.float32)

    def fit(self, tm, terra=False):
        """Train on months tm (less the gappy ones): every cell-month where a sensor saw fire, plus a P0
        sample of the all-zero ones. -> (model, small-fire climatology of tm)"""
        tm = tm & ~self.gappy
        rng = np.random.default_rng(0)
        cnt = self.MT if terra else self.M
        fire = (cnt > 0) | (self.V > 0)
        act = fire & tm[None, :]
        zero = ~fire & tm[None, :] & (rng.random((self.C, self.T), dtype=np.float32) < P0)
        ci, ti = np.nonzero(act | zero)
        w0 = np.where(act[ci, ti], 1.0, 1.0 / P0)
        e = cnt[ci, ti] + 1
        tile_total = np.bincount(self.tl[ci], weights=e * w0)
        # capped: a tile with almost no fire must not get an enormous weight
        balance = np.clip((np.maximum(tile_total, 1e-9) / tile_total.max()) ** -ALPHA, 1, 20)
        sf = self.small_fire(tm, terra)
        X = self.feats(ci, ti, sf, terra)
        # capped: a few cell-months have hundreds of VIIRS hotspots and no MODIS one
        y = np.minimum(self.V[ci, ti] / e, 200.0)
        model = HistGradientBoostingRegressor(**HGB)
        model.fit(X, y, sample_weight=(e * w0 * balance[self.tl[ci]]).astype(np.float64))
        log(
            f"  fit on {len(ci):,} rows ({int(act.sum()):,} with fire), {int(tm.sum())} months, "
            f"{'Terra-only' if terra else 'full'} inputs"
        )
        return model, sf

    def predict(self, model, sf, ts, terra=False):
        ci = np.arange(self.C)
        cnt = self.MT if terra else self.M
        out = {}
        for t in ts:
            ratio = model.predict(self.feats(ci, np.full(self.C, t), sf, terra))
            out[t] = (ratio * (cnt[:, t] + 1)).astype(np.float32)
        return out

    def local_ratio(self, tm, terra=False, fire_only=False):
        """VIIRS / MODIS per 1 degree box and calendar month over months tm, shrunk toward the 10 degree
        tile's ratio and that toward the world's. fire_only: VIIRS counted only where MODIS saw fire
        (small_fire covers the rest)."""
        tm = tm & ~self.gappy
        cnt = self.MT if terra else self.M
        V = self.V * (cnt > 0) if fire_only else self.V
        nb = self.bx.max() + 1
        nt = self.tl.max() + 1
        tile_of_box = np.zeros(nb, np.int64)
        tile_of_box[self.bx] = self.tl
        kb = np.zeros((nb, 12), np.float32)
        for c in range(12):
            cols = tm & (self.cal == c)
            v = V[:, cols].sum(axis=1)
            m = cnt[:, cols].sum(axis=1)
            kg = v.sum() / max(m.sum(), 1)
            kt = (np.bincount(self.tl, v, nt) + 50 * kg) / (np.bincount(self.tl, m, nt) + 50)
            kb[:, c] = (np.bincount(self.bx, v, nb) + 50 * kt[tile_of_box]) / (
                np.bincount(self.bx, m, nb) + 50
            )
        return kb

    def simple(self, t, kb, sf=None, terra=False):
        """Month t without a model: the local seasonal ratio times MODIS and, given sf (then kb must be
        fire-only), the cell's usual VIIRS count where MODIS saw nothing."""
        cnt = (self.MT if terra else self.M)[:, t]
        c = self.cal[t]
        out = kb[self.bx, c] * cnt
        if sf is not None:
            vs, vn, _ = sf
            out = out + (cnt == 0) * mean_or_zero(vs[:, c], vn[:, c])
        return out.astype(np.float32)

    def reconcile(self, p, best):
        """Keep the model's detail between cells, but make each 1 degree box total a blend of the model's
        and the best simple method's (weight W_LOCAL)."""
        nb = self.bx.max() + 1
        model_box = np.bincount(self.bx, p, nb)
        best_box = np.bincount(self.bx, best, nb)
        blend = (1 - W_LOCAL) * model_box + W_LOCAL * best_box
        scale = np.where(model_box > 0, blend / np.maximum(model_box, 1e-9), 1.0)
        return (p * scale[self.bx]).astype(np.float32)


def bridge(g, F, G, months, prior=500):
    """F / G per 10 degree tile and calendar month over months, shrunk toward the tile's ratio and that
    toward the world's. F: the full-input estimates, G: the Terra-only ones.
    -> (ratio[tile, calendar month], world ratio)"""
    nt = g.tl.max() + 1
    months = [t for t in months if not g.gappy[t]]

    def tile_sums(P, ms):
        return sum(np.bincount(g.tl, P[t], nt) for t in ms)

    f = tile_sums(F, months)
    q = tile_sums(G, months)
    kw = f.sum() / q.sum()
    kt = (f + prior * kw) / (q + prior)
    k = np.ones((nt, 12))
    for c in range(12):
        ms = [t for t in months if g.cal[t] == c]
        if ms:
            k[:, c] = (tile_sums(F, ms) + prior * kt) / (tile_sums(G, ms) + prior)
    return k, float(kw)


def totals(group, x):
    """Sum x over groups: group is an index per cell (-1 = none) or a groups x cells matrix of shares."""
    if sparse.issparse(group):
        return np.asarray(group @ x.astype(np.float64)).ravel()
    ok = group >= 0
    return np.bincount(group[ok], x[ok], group.max() + 1)


def scores(g, pred, ts, group, min_months=12):
    """Errors of estimates {t: per cell} against VIIRS over months ts.

    by: each area's median error of its monthly totals (months with 20+ real hotspots; areas with
        min_months such months); country: median of by;
    box: median error of 1 degree box-months with 50+ real hotspots;
    cell: log-RMSE over cell-months where either sensor saw fire (cell_all: over all);
    wcountry, wbox: sum of absolute errors of area and box totals over the sum of real hotspots;
    world, world_p90: median and 90th percentile error of the world's monthly totals;
    bias: all estimated / all real - 1.
    """
    err = {}
    box = []
    world = []
    se = n = se_all = ae = bae = sp = sa = 0.0
    for t in ts:
        p, a = pred[t], g.V[:, t]
        pg, ag = totals(group, p), totals(group, a)
        for i in np.nonzero(ag >= 20)[0]:
            err.setdefault(int(i), []).append(abs(pg[i] - ag[i]) / ag[i])
        pb, ab = np.bincount(g.bx, p), np.bincount(g.bx, a)
        big = ab >= 50
        box.append(abs(pb[big] - ab[big]) / ab[big])
        d2 = (np.log1p(p) - np.log1p(a)) ** 2
        act = (g.M[:, t] > 0) | (a > 0)
        se += d2[act].sum()
        n += act.sum()
        se_all += d2.sum()
        ae += abs(pg - ag).sum()
        bae += abs(pb - ab).sum()
        sp += p.sum()
        sa += a.sum()
        world.append(abs(p.sum() - a.sum()) / a.sum())
    by = np.full(len(totals(group, g.V[:, ts[0]])), np.nan)
    for i, e in err.items():
        if len(e) >= min_months:
            by[i] = np.median(e)
    return {
        "by": by,
        "country": float(np.nanmedian(by)),
        "box": float(np.median(np.concatenate(box))),
        "cell": float(np.sqrt(se / max(n, 1))),
        "cell_all": float(np.sqrt(se_all / (len(ts) * g.C))),
        "wcountry": float(ae / sa),
        "wbox": float(bae / sa),
        "world": float(np.median(world)),
        "world_p90": float(np.quantile(world, 0.9)),
        "bias": float(sp / sa - 1),
    }


def slim(s):
    """The scores without the per-area errors, for metrics.json."""
    return {k: v for k, v in s.items() if k != "by"}


def show(results):
    for n, s in results.items():
        log(
            f"  {n:<15} country {s['country']:.1%}  box {s['box']:.1%}  cell {s['cell']:.3f}"
            f"  world {s['world']:.1%} | weighted: country {s['wcountry']:.1%} box {s['wbox']:.1%}"
            f" | bias {s['bias']:+.1%}"
        )


def range_table(g, blind, group, q=(0.03, 0.97), k=48, f=5.0):
    """The app's range rule tested across periods: learn the range of an estimate from the blind-test
    errors of one half of the VIIRS years (the k months of most similar size in the same area) and apply
    it to the other half. -> (rows: estimate, real value, low and high quantile of the log error, is one
    of the area's biggest 10 % of months; number of areas tested)"""
    ts = np.arange(VIIRS0, FRESH)
    P = np.stack([totals(group, blind[:, t]) for t in ts], axis=1)
    R = np.stack([totals(group, g.V[:, t]) for t in ts], axis=1)
    half = SPLIT - VIIRS0
    rows = []
    areas = 0
    for i in np.nonzero(R.sum(axis=1) >= 200)[0]:
        areas += 1
        for ref, tst in ((slice(0, half), slice(half, None)), (slice(half, None), slice(0, half))):
            p, r = P[i, ref], R[i, ref]
            use = p > 0
            if use.sum() < 12:
                continue
            lb = np.log1p(p[use])
            lr = np.log1p(r[use]) - lb
            pt, rt = P[i, tst], R[i, tst]
            big = pt >= np.quantile(pt, 0.9)
            for e, real, b in zip(pt, rt, big):
                d = abs(lb - np.log1p(e))
                o = np.argsort(d)[:k]
                near = o[d[o] <= np.log(f)]
                if len(near) < 12:
                    near = o[:12]
                rows.append((e, real, *np.quantile(lr[near], q), b))
    return np.array(rows, np.float64), areas


def covered(tab, delta):
    """Share of real values inside the range widened by delta (log) each side: (plain, weighted by
    hotspots, in the biggest months)."""
    e, real, lo, hi, big = tab.T
    le = np.log1p(e)
    inside = (np.expm1(le + np.minimum(lo, 0) - delta) - 0.5 <= real) & (
        real <= np.expm1(le + np.maximum(hi, 0) + delta) + 0.5
    )
    return float(inside.mean()), float((inside * real).sum() / real.sum()), float(inside[big > 0].mean())


def assign_countries(g):
    """Each cell's share in each country, in proportion to the hotspots the archive files of that country
    have there (2000-2025). A cell that first burned in 2026 (no country in the API data) takes the shares
    of the nearest cell that has them, up to 1 degree away. -> (shares: countries x cells, the country with
    the largest share or -1, names, number of cells without a country before that fill)"""
    cc = read("*_countries.parquet").groupby(["country", "ilat", "ilon"]).n.sum().reset_index()
    names, cid = np.unique(cc.country.values, return_inverse=True)
    k = cell_key(cc.ilat.values, cc.ilon.values)
    i = np.minimum(np.searchsorted(g.keys, k), g.C - 1)
    ok = g.keys[i] == k
    S = sparse.csc_matrix((cc.n.values[ok].astype(np.float64), (cid[ok], i[ok])), shape=(len(names), g.C))
    tot = np.asarray(S.sum(axis=0)).ravel()
    has = tot > 0
    src = np.arange(g.C)
    if (~has).any() and has.any():
        d, j = cKDTree(np.c_[g.lat[has], g.lon[has]]).query(np.c_[g.lat[~has], g.lon[~has]])
        close = d <= 1.0
        src[np.nonzero(~has)[0][close]] = np.nonzero(has)[0][j[close]]
    tot = tot[src]
    S = (
        S[:, src] @ sparse.diags(1 / np.maximum(tot, 1e-12) * (tot > 0))
    ).tocsr()  # columns sum to 1, 0 at sea
    country = np.where(tot > 0, np.asarray(S.argmax(axis=0)).ravel(), -1)
    return S, country, names, int((~has).sum())


def methods(g, country, nc, tr, te, terra=False):
    """Fit on months tr and estimate months te by each method: {method: {t: estimate per cell}}.
    "model averaged" (the record): the model, its box totals averaged with the best simple method's."""
    model, sf = g.fit(tr, terra)
    kb = g.local_ratio(tr, terra)
    kbf = g.local_ratio(tr, terra, fire_only=True)
    p = g.predict(model, sf, te, terra)
    cnt = g.MT if terra else g.M
    trn = tr & ~g.gappy
    okc = country >= 0
    cx = np.maximum(country, 0)

    def per_country(x):
        return np.bincount(country[okc], x[okc], nc)

    ka = per_country(g.V[:, trn].sum(axis=1)) / np.maximum(per_country(cnt[:, trn].sum(axis=1)), 1)
    kc = np.zeros((nc, 12))
    for c in range(12):
        cols = trn & (g.cal == c)
        kc[:, c] = (per_country(g.V[:, cols].sum(axis=1)) + 20 * ka) / (
            per_country(cnt[:, cols].sum(axis=1)) + 20
        )
    best = {t: g.simple(t, kbf, sf, terra) for t in te}
    avg = {t: g.reconcile(p[t], best[t]) for t in te}
    return {
        "one ratio": {t: (okc * ka[cx] * cnt[:, t]).astype(np.float32) for t in te},
        "seasonal ratio": {t: (okc * kc[cx, g.cal[t]] * cnt[:, t]).astype(np.float32) for t in te},
        "local ratio": {t: g.simple(t, kb, None, terra) for t in te},
        "best simple": best,
        "model": p,
        "model averaged": avg,
        "record": avg,
    }


def monthly_totals(A):
    """World total of each month of a cells x months array."""
    return np.array([A[:, t].sum(dtype=np.float64) for t in range(A.shape[1])])


def step(g, h, m, a0, a1, b0, b1):
    """Change of h / m from months a0..a1 to months b0..b1, calendar month by calendar month, weighted by m
    (None if no calendar month can be compared)."""
    w = st = 0.0
    for c in range(12):
        pre = [t for t in range(a0, a1) if g.cal[t] == c and not g.gappy[t]]
        post = [t for t in range(b0, b1) if g.cal[t] == c and not g.gappy[t]]
        hp, mp, ha, ma = h[pre].sum(), m[pre].sum(), h[post].sum(), m[post].sum()
        if min(hp, mp, ha, ma) > 0:
            wt = mp + ma
            st += wt * np.log((ha / ma) / (hp / mp))
            w += wt
    return float(np.expm1(st / w)) if w else None


def main():
    MODEL.mkdir(parents=True, exist_ok=True)
    g = Grid()
    T, C = g.T, g.C
    shares, country, names, unassigned = assign_countries(g)
    nc = len(names)
    M = {
        "cells": int(C),
        "months": int(T),
        "first": "2000-11",
        "hotspots": {"modis": float(g.Mraw.sum()), "snpp": float(g.Vraw.sum()), "noaa20": float(g.N20.sum())},
        "persistent_sources": g.persistent,
        "cells_without_country_before_fill": unassigned,
        "cells_without_country": int((country < 0).sum()),
        "outages": {
            "runs": [{"satellite": a, "from": b, "to": c, "lost": d} for a, b, c, d in g.runs],
            "months": g.gaps,
        },
        "noaa20": g.noaa20,
    }
    for f in sorted(CELLS.glob("mask_check_*.json")):
        M.setdefault("mask_check", {}).update(json.loads(f.read_text()))

    # ---- blind tests: closest analogue of the real task (stable orbits, back in time), both directions ----
    blind = np.zeros((C, T), np.float32)
    res = {}
    yearly = {}
    # the whole months of 2026
    fresh = [t for t in range(FRESH, T - 1) if g.M[:, t].sum() > 0 and g.V[:, t].sum() > 0]
    for name, tr, te in (
        ("analogue", g.span(MID, DRIFT), list(range(VIIRS0, MID))),
        ("forward", g.span(VIIRS0, SPLIT), list(range(SPLIT, FRESH))),
        ("backward", g.span(SPLIT, FRESH), list(range(VIIRS0, SPLIT))),
    ):
        log(name)
        P = methods(g, country, nc, tr, te + (fresh if name == "backward" else []))
        res[name] = {n: scores(g, x, te, shares) for n, x in P.items()}
        show(res[name])
        yearly[name] = {}
        for y in sorted({(T0 + t) // 12 for t in te}):
            ts = [t for t in te if (T0 + t) // 12 == y]
            estimated = sum(P["record"][t].sum() for t in ts)
            real = sum(g.V[:, t].sum() for t in ts)
            yearly[name][str(y)] = float(estimated / real - 1)
        if name != "analogue":
            for t in te:
                blind[:, t] = P["record"][t]
        if name == "backward" and len(fresh) >= 6:
            # 2026: the model trained on the latest years (2019-2025) meets months no model was trained on
            f = {n: scores(g, x, fresh, shares, 6) for n, x in P.items()}
            hv = ~np.isnan(f["record"]["by"])
            M["fresh2026"] = {
                **{n: slim(s) for n, s in f.items()},
                "months": len(fresh),
                "months_all_snpp": int(sum(g.fill[t] < 0.03 for t in fresh)),
                "countries": int(hv.sum()),
                "countries_better": {
                    n: int((f["record"]["by"][hv] < f[n]["by"][hv]).sum())
                    for n in ("one ratio", "seasonal ratio", "best simple")
                },
            }
            for t in fresh:
                blind[:, t] = P["record"][t]
            rec = f["record"]
            log(
                f"  2026 ({len(fresh)} months): record country {rec['country']:.1%} box {rec['box']:.1%}"
                f" cell {rec['cell']:.3f} bias {rec['bias']:+.1%}"
                f" | best simple {f['best simple']['country']:.1%}"
                f" | seasonal ratio {f['seasonal ratio']['country']:.1%}"
                f" | one ratio {f['one ratio']['country']:.1%};"
                f" better in {M['fresh2026']['countries_better']} of {hv.sum()}"
            )
    log("analogue, Terra-only inputs")
    te = list(range(VIIRS0, MID))
    P = methods(g, country, nc, g.span(MID, DRIFT), te, terra=True)
    res["analogue_terra"] = {n: scores(g, x, te, shares) for n, x in P.items()}
    show(res["analogue_terra"])
    M["record_is"] = "model averaged"
    M["tests"] = {d: {n: slim(s) for n, s in r.items()} for d, r in res.items()}
    M["bias_by_year"] = yearly

    def both(n):  # a country counts only if it could be scored in both directions
        return np.mean([res["forward"][n]["by"], res["backward"][n]["by"]], axis=0)

    record_err = both("record")
    have = ~np.isnan(record_err) & ~np.isnan(both("seasonal ratio"))
    M["countries_tested"] = int(have.sum())
    M["countries_better"] = {
        n: int((record_err[have] < both(n)[have]).sum())
        for n in ("one ratio", "seasonal ratio", "local ratio", "best simple")
    }
    log(f"countries scored in both directions: {have.sum()}; the record beats {M['countries_better']}")

    # ---- are the app's ranges honest? ----
    tabs = {
        "country": range_table(g, blind, shares),
        "2 degree box": range_table(g, blind, box_index(g.lat, g.lon, 2)),
        "0.5 degree box": range_table(g, blind, box_index(g.lat, g.lon, 0.5)),
    }
    # the smallest widening that puts the real value inside 9 times in 10, plain and weighted by fire
    delta0 = next(
        (d for d in np.arange(0, 0.61, 0.01) if min(covered(tabs["country"][0], d)[:2]) >= 0.90), 0.6
    )
    yb = np.array([yearly["analogue"][y] for y in sorted(yearly["analogue"])])
    dist = np.arange(len(yb), 0, -1)  # years between the test year and the training period
    # how fast the bias moves per year of distance, where the orbits were stable
    slope = float(np.clip(abs(np.polyfit(dist, np.log1p(yb), 1)[0]), 0.005, 0.03))
    terra_factor = float(
        np.clip(res["analogue_terra"]["record"]["country"] / res["analogue"]["record"]["country"], 1.0, 3.0)
    )
    coverage_keys = ("inside", "inside_weighted", "inside_biggest")
    M["ranges"] = {
        "quantiles": [0.03, 0.97],
        "delta0": float(delta0),
        "slope_per_year": slope,
        "terra_factor": terra_factor,
        "coverage": {
            n: dict(zip(coverage_keys, covered(t[0], delta0)), areas=int(t[1])) for n, t in tabs.items()
        },
        "coverage_unwidened": {n: dict(zip(coverage_keys, covered(t[0], 0.0))) for n, t in tabs.items()},
    }
    log(
        f"ranges: widened by {delta0:.2f} (log) -> {M['ranges']['coverage']};"
        f" before: {M['ranges']['coverage_unwidened']}; +{slope:.3f} per year before 2012;"
        f" Terra-only months x{terra_factor:.2f}"
    )

    # ---- twin-sensor benchmark: NOAA-20 predicting S-NPP in the healthy months of the forward test ----
    def bench(months):
        kt = sum(g.Vraw[:, t].sum() for t in months) / sum(g.N20[:, t].sum() for t in months)
        return {
            "months": len(months),
            "twin": slim(scores(g, {t: g.N20[:, t] * kt for t in months}, months, shares)),
            "record": slim(scores(g, {t: blind[:, t] for t in months}, months, shares)),
        }

    twin = [t for t in g.twin_months if SPLIT <= t < FRESH]
    if len(twin) >= 12:
        M["benchmark"] = {
            **bench(twin),
            "before_rephasing": bench([t for t in twin if t < REPHASE - 1]),
            "after_rephasing": bench([t for t in twin if t > REPHASE]),
        }
        b = M["benchmark"]
        log(
            f"twin-sensor benchmark ({b['months']} months): country {b['twin']['country']:.1%}"
            f" box {b['twin']['box']:.1%} cell {b['twin']['cell']:.3f} | record, same months:"
            f" {b['record']['country']:.1%} {b['record']['box']:.1%} {b['record']['cell']:.3f}"
            f" | twin before/after re-phasing: {b['before_rephasing']['twin']['country']:.1%}"
            f" / {b['after_rephasing']['twin']['country']:.1%}"
        )

    # ---- the record: models trained on 2012-2019 (stable orbits) ----
    log("final")
    stable = g.span(VIIRS0, DRIFT)
    late = [t for t in range(DRIFT, T) if g.M[:, t].sum() > 0 and g.V[:, t].sum() > 0]
    P = methods(g, country, nc, stable, list(range(AQUA, VIIRS0)) + late)
    H = np.zeros((C, T), np.float32)
    H_model = np.zeros((C, T), np.float32)
    H_ratio = np.zeros((C, T), np.float32)
    for t in range(AQUA, VIIRS0):
        H[:, t] = P["record"][t]
        H_model[:, t] = P["model"][t]
        H_ratio[:, t] = P["best simple"][t]
    # a stress test: the final model has never seen 2020 on, while the MODIS orbits drift further each year
    M["final_forward"] = {"2020-2025": {n: slim(scores(g, P[n], range(DRIFT, FRESH), shares)) for n in P}}
    if len(fresh) >= 6:
        M["final_forward"]["2026"] = {n: slim(scores(g, P[n], fresh, shares, 6)) for n in P}
    for n, s in M["final_forward"].items():
        log(
            f"  final model on {n}: record country {s['record']['country']:.1%}"
            f" bias {s['record']['bias']:+.1%} | best simple {s['best simple']['country']:.1%}"
            f" bias {s['best simple']['bias']:+.1%}"
        )
    log("Terra-only model for the months before Aqua")
    PT = methods(g, country, nc, stable, list(range(0, VIIRS0)), terra=True)
    # tie them to the rest of the record through the years both models can run (E11)
    kbr, kw = bridge(g, {t: H[:, t] for t in range(AQUA, VIIRS0)}, PT["record"], range(AQUA, VIIRS0))
    H_plain = np.zeros((C, AQUA), np.float32)
    for t in range(0, AQUA):
        H[:, t] = PT["record"][t] * kbr[g.tl, g.cal[t]]
        H_plain[:, t] = PT["record"][t]
        H_model[:, t] = PT["model"][t]
        H_ratio[:, t] = PT["best simple"][t]
    M["bridge"] = {"world": kw, "tiles_5_95": [float(v) for v in np.percentile(kbr, [5, 95])]}
    log(f"bridge to the Terra-only months: {M['bridge']}")
    # S-NPP, with the share it lost filled from NOAA-20 (Grid.repair); NOAA-20 alone once S-NPP had ended
    H[:, VIIRS0:] = g.V[:, VIIRS0:]
    M["n20_months"] = [month_name(t) for t in np.nonzero(g.fill >= 0.03)[0]]

    # ---- steps: at Feb 2012 against MODIS, at July 2002 against Terra (which flew through) ----
    H_model[:, VIIRS0:] = H[:, VIIRS0:]
    H_ratio[:, VIIRS0:] = H[:, VIIRS0:]
    modis_w = monthly_totals(g.M)
    terra_w = monthly_totals(g.MT)
    viirs_w = monthly_totals(g.V)
    record_w = monthly_totals(H)
    model_w = monthly_totals(H_model)
    ratio_w = monthly_totals(H_ratio)

    def seam(h, m):
        return step(g, h, m, AQUA, VIIRS0, VIIRS0, DRIFT)

    def step_2002(h):
        return step(g, h, terra_w, 0, AQUA, AQUA, VIIRS0)

    unbridged_w = np.r_[H_plain.sum(axis=0, dtype=np.float64), record_w[AQUA:]]
    raw = np.where(np.arange(T) < VIIRS0, modis_w, viirs_w)
    # the same test inside real VIIRS data (first 20 months against the rest): what no step looks like
    real_vt = step(g, viirs_w, terra_w, VIIRS0, VIIRS0 + AQUA, VIIRS0 + AQUA, DRIFT)
    M["steps"] = {
        "2012": {
            "record": seam(record_w, modis_w),
            "model alone": seam(model_w, modis_w),
            "best simple alone": seam(ratio_w, modis_w),
            "raw join": seam(raw, modis_w),
        },
        "2002": {
            "record": step_2002(record_w),
            "without the bridge": step_2002(unbridged_w),
            "model alone": step_2002(model_w),
            "best simple alone": step_2002(ratio_w),
            "real VIIRS, same test": real_vt,
        },
    }
    M["seam_world"] = M["steps"]["2012"]["record"]
    log(f"steps: {M['steps']}")

    # ---- per country table ----
    def by_country(A):
        return np.stack([totals(shares, A[:, t]) for t in range(T)], axis=1)

    def number(v):
        return None if np.isnan(v) else float(v)

    record_c = by_country(H)
    modis_c = by_country(g.M)
    viirs_c = by_country(g.V)
    model_c = by_country(H_model)
    rows = []
    alone = []
    for i, name in enumerate(names):
        viirs = float(viirs_c[i, VIIRS0:FRESH].sum())
        if viirs < 2000:
            continue
        alone.append(seam(model_c[i], modis_c[i]))
        rows.append(
            {
                "country": name,
                "viirs_hotspots": viirs,
                "ratio": viirs / max(float(modis_c[i, VIIRS0:FRESH].sum()), 1),
                "record": number(record_err[i]),
                "seasonal_ratio": number(both("seasonal ratio")[i]),
                "one_ratio": number(both("one ratio")[i]),
                "best_simple": number(both("best simple")[i]),
                "seam": seam(record_c[i], modis_c[i]),
            }
        )
    M["countries"] = rows
    s = np.array([abs(r["seam"]) for r in rows if r["seam"] is not None])
    M["seam_countries_median_abs"] = float(np.median(s))
    # what the averaging of box totals buys
    M["seam_countries_median_abs_model_alone"] = float(np.median([abs(v) for v in alone if v is not None]))
    log(
        f"{len(rows)} countries; median |step at 2012| {np.median(s):.1%}"
        f" (model alone: {M['seam_countries_median_abs_model_alone']:.1%});"
        f" within 5%: {(s < 0.05).mean():.0%}"
    )

    for name, a in (("H", H), ("blind", blind), ("M", g.M), ("V", g.V), ("N20", g.N20), ("MT", g.MT)):
        np.save(MODEL / f"{name}.npy", a)
    np.save(MODEL / "keys.npy", g.keys)
    np.save(MODEL / "country.npy", country)
    sparse.save_npz(MODEL / "shares.npz", shares)
    (MODEL / "metrics.json").write_text(json.dumps({**M, "country_names": names.tolist()}, indent=1))
    log("saved", MODEL)


if __name__ == "__main__":
    main()
