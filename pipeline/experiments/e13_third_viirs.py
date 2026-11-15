"""E13: a third VIIRS, NOAA-21 (from March 2023), tests the twin-sensor benchmark, the outage repairs and the
hand-over to NOAA-20. See docs/EXPERIMENTS.md, E13. Run: python3 pipeline/experiments/e13_third_viirs.py
(needs stage 1's tables, including NOAA-21 from `download_api.py extra`, and stage 2's outputs)"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy import sparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import CELLS, MODEL, T0, cell_key, cell_lat, cell_lon, month_index, month_name  # noqa: E402
from stage2_model import scores  # noqa: E402

SENSORS = {"S-NPP": "viirs-snpp", "NOAA-20": "viirs-jpss1", "NOAA-21": "viirs-noaa21"}
SCORES = ("country", "box", "cell", "wcountry", "world")
# months with all three; November 2026 (S-NPP ended on the 2nd) is used only for the hand-over
A, B = month_index("2023-03"), month_index("2026-11")
T = B - A + 1

keys = np.load(MODEL / "keys.npy")
C = len(keys)
met = json.loads((MODEL / "metrics.json").read_text())
shares = sparse.load_npz(MODEL / "shares.npz")
lat, lon = cell_lat(keys), cell_lon(keys)
box = np.unique(
    (np.floor(lat).astype(np.int64) + 90) * 400 + np.floor(lon).astype(np.int64) + 180, return_inverse=True
)[1]
tile = np.unique(
    (np.floor(lat / 10).astype(np.int64) + 9) * 40 + np.floor(lon / 10).astype(np.int64) + 18,
    return_inverse=True,
)[1]
n_tiles = tile.max() + 1
grid = SimpleNamespace(C=C, bx=box)  # what scores() reads, with M and V set below


def tables(prefix, suffix=""):
    paths = (CELLS / f"{prefix}_{y}{suffix}.parquet" for y in range(2023, 2027))
    return [p for p in paths if p.exists()]


def monthly(prefix):
    """Cell x month counts on the record's grid (cells it left out, the persistent heat sources, stay out)."""
    d = pd.concat([pd.read_parquet(f, columns=["ilat", "ilon", "ym", "n"]) for f in tables(prefix)])
    k = cell_key(d.ilat.values, d.ilon.values)
    i = np.minimum(np.searchsorted(keys, k), C - 1)
    t = d.ym.values - T0 - A
    ok = (keys[i] == k) & (t >= 0) & (t < T)
    a = np.zeros((C, T), np.float32)
    np.add.at(a, (i[ok], t[ok]), d.n.values[ok])
    return a


def daily(prefix):
    d = pd.concat([pd.read_parquet(f) for f in tables(prefix, "_daily")])
    return d.groupby("acq_date").n.sum()


def score(target, pred):
    """Scores of pred {month: per cell} against one sensor, as stage 2 scores the record."""
    grid.V = np.zeros((C, A + T), np.float32)
    grid.V[:, A:] = X[target]
    s = scores(grid, pred, list(pred), shares, 6)
    return {x: s[x] for x in SCORES}


def bench(target, pred, ts):
    """pred, brought to the target's scale with one factor, scored on months ts."""
    k = sum(X[target][:, t].sum() for t in ts) / sum(pred[:, t].sum() for t in ts)
    return score(target, {A + t: pred[:, t] * k for t in ts})


def difference(alt, rec):
    """World difference of alt from rec, median difference of the 10° tiles with 500+ hotspots, and those tiles."""
    alt_t, rec_t = np.bincount(tile, alt, n_tiles), np.bincount(tile, rec, n_tiles)
    big = rec_t >= 500
    return (
        float(alt.sum() / rec.sum() - 1),
        float(np.median(abs(alt_t[big] / rec_t[big] - 1))),
        int(big.sum()),
    )


X = {s: monthly(p) for s, p in SENSORS.items()}
D = pd.DataFrame({s: daily(p) for s, p in SENSORS.items()}).loc["2023-03-01":"2026-11-30"].fillna(0)
# a sensor lost a day when it brought under half of what the other two lead to expect (scaled by its usual ratio)
lost = pd.DataFrame(index=D.index)
for s in SENSORS:
    ref = D[[o for o in SENSORS if o != s]].mean(axis=1)
    k = (D[s] / ref).where((D > 0).all(axis=1)).median()
    lost[s] = (D[s] < 0.5 * k * ref) | (D[s] == 0)
lost.loc[lost.index > "2026-11-02", "S-NPP"] = True


def any_lost(month):
    return lost[[day[:7] == month for day in lost.index]].any().any()


healthy = [t for t in range(T - 1) if not any_lost(month_name(A + t))]
print(f"{len(healthy)} of {T - 1} months (Mar 2023 - Oct 2026) in which none of the three lost a day")

# 1. pairwise agreement, scored like the record on the cell-months where any of the four sensors saw fire
modis = np.load(MODEL / "M.npy", mmap_mode="r")
grid.M = np.zeros((C, A + T), np.float32)
grid.M[:, A:] = X["S-NPP"] + X["NOAA-20"] + X["NOAA-21"] + np.asarray(modis[:, A : B + 1])
blind = np.load(MODEL / "blind.npy", mmap_mode="r")[:, A : B + 1]
H = np.load(MODEL / "H.npy", mmap_mode="r")
res = {"healthy_months": [month_name(A + t) for t in healthy]}
average = (X["NOAA-20"] / X["NOAA-20"][:, healthy].sum() + X["NOAA-21"] / X["NOAA-21"][:, healthy].sum()) / 2
pairs = {
    "NOAA-20 -> S-NPP": ("S-NPP", X["NOAA-20"]),
    "NOAA-21 -> S-NPP": ("S-NPP", X["NOAA-21"]),
    "NOAA-21 -> NOAA-20": ("NOAA-20", X["NOAA-21"]),
    "average of NOAA-20 and NOAA-21 -> S-NPP": ("S-NPP", average),
}
res["pairs"] = {n: bench(target, pred, healthy) for n, (target, pred) in pairs.items()}
res["record_blind"] = score("S-NPP", {A + t: np.asarray(blind[:, t]) for t in healthy})
print("\n1. on those months (median error of monthly totals; cells: log-RMSE)")
for n, r in list(res["pairs"].items()) + [("the record's blind test (MODIS -> S-NPP)", res["record_blind"])]:
    print(
        f"   {n:<42} country {r['country']:.1%}  box {r['box']:.1%}  cell {r['cell']:.3f}  country weighted {r['wcountry']:.1%}  world {r['world']:.1%}"
    )

# 2. three-cornered hat on 1° box-months
nb = box.max() + 1
box_counts = {s: np.stack([np.bincount(box, X[s][:, t], nb) for t in healthy], axis=1) for s in SENSORS}
ok = np.all([box_counts[s] >= 50 for s in SENSORS], axis=0)
L = {s: np.log(box_counts[s][ok]) for s in SENSORS}
var = {}
for s1, s2 in (("S-NPP", "NOAA-20"), ("S-NPP", "NOAA-21"), ("NOAA-20", "NOAA-21")):
    d = L[s1] - L[s2]
    var[(s1, s2)] = float(np.var(d - np.median(d)))  # scale differences removed
own = {
    "S-NPP": (var[("S-NPP", "NOAA-20")] + var[("S-NPP", "NOAA-21")] - var[("NOAA-20", "NOAA-21")]) / 2,
    "NOAA-20": (var[("S-NPP", "NOAA-20")] + var[("NOAA-20", "NOAA-21")] - var[("S-NPP", "NOAA-21")]) / 2,
    "NOAA-21": (var[("S-NPP", "NOAA-21")] + var[("NOAA-20", "NOAA-21")] - var[("S-NPP", "NOAA-20")]) / 2,
}
rec = np.stack([np.bincount(box, np.asarray(blind[:, t]), nb) for t in healthy], axis=1)[ok]
d = np.log(np.maximum(rec, 1)) - L["S-NPP"]
hat = res["three_cornered_hat"] = {
    "box_months": int(ok.sum()),
    "pair_sd": {f"{s1} / {s2}": float(np.sqrt(x)) for (s1, s2), x in var.items()},
    "own_sd": {s: float(np.sqrt(max(x, 0))) for s, x in own.items()},
    "record_vs_snpp_sd": float(np.std(d - np.median(d))),
    "record_own_sd": float(np.sqrt(max(np.var(d - np.median(d)) - own["S-NPP"], 0))),
}
print(
    f"\n2. three-cornered hat, {ok.sum():,} box-months with 50+ hotspots in all three (log standard deviations)"
)
print("   pairs: " + ", ".join(f"{k} {x:.3f}" for k, x in hat["pair_sd"].items()))
print("   each sensor's own random error: " + ", ".join(f"{k} {x:.3f}" for k, x in hat["own_sd"].items()))
print(
    f"   the record against S-NPP: {hat['record_vs_snpp_sd']:.3f}; once S-NPP's own error is taken out: {hat['record_own_sd']:.3f}"
)

# 3. before and after NOAA-20 was re-phased
before = [t for t in healthy if A + t < month_index("2024-03")]
after = [t for t in healthy if A + t > month_index("2024-04")]
res["rephasing"] = {}
for period, ts in (("before (Mar 2023 - Feb 2024)", before), ("after (May 2024 on)", after)):
    if len(ts) >= 6:
        single = list(pairs.items())[:3]
        res["rephasing"][period] = {
            "months": len(ts),
            **{n: bench(tg, p, ts)["box"] for n, (tg, p) in single},
        }
print("\n3. box error by period: " + json.dumps(res["rephasing"], default=lambda x: round(x, 3)))

# 4. outage days: was NOAA-21 normal?
runs = [
    r
    for r in met["outages"]["runs"]
    if r["satellite"] in ("snpp", "noaa20") and r["to"] >= "2023-03-01" and r["from"] <= "2026-11-02"
]
rows = []
for r in runs:
    days = [d for d in D.index if r["from"] <= d <= r["to"]]
    sat = {"snpp": "S-NPP", "noaa20": "NOAA-20"}[r["satellite"]]
    rows.append(
        {
            "satellite": sat,
            "from": r["from"],
            "to": r["to"],
            "lost_by_record": r["lost"],
            "noaa21_lost_any_day": bool(lost.loc[days, "NOAA-21"].any()),
            "detected_here_too": bool(lost.loc[days, sat].any()),
        }
    )
res["outage_days"] = rows
print(
    f"\n4. {len(rows)} outage runs of S-NPP or NOAA-20 since March 2023: NOAA-21 normal on all their days in {sum(not r['noaa21_lost_any_day'] for r in rows)}; "
    f"the three-sensor test here confirms the loss in {sum(r['detected_here_too'] for r in rows)}"
)
n21_lost = lost["NOAA-21"]
n21_days = n21_lost[n21_lost].index.tolist()
res["noaa21_lost_days"] = n21_days
print(f"   NOAA-21's own lost days: {len(n21_days)} {n21_days[:12]}")

# 5. the months filled from NOAA-20: the same fill from NOAA-21
filled = {m: f for m, f in met["noaa20"]["filled"].items() if "2023-03" <= m <= "2026-10"}
V = np.load(MODEL / "V.npy", mmap_mode="r")
snpp_t = np.bincount(tile, X["S-NPP"][:, healthy].sum(axis=1), n_tiles)
n21_t = np.bincount(tile, X["NOAA-21"][:, healthy].sum(axis=1), n_tiles)
k_world = snpp_t.sum() / n21_t.sum()
# S-NPP / NOAA-21 per 10° tile, shrunk toward the world's: the record's rule, with NOAA-21 in NOAA-20's place
k_tile = (snpp_t + 200 * k_world) / (n21_t + 200)


def refill(month):
    t = month_index(month) - A
    return X["S-NPP"][:, t] + met["outages"]["months"][month]["snpp"] * k_tile[tile] * X["NOAA-21"][:, t]


rows = []
for m, f in filled.items():
    world, tiles, _ = difference(refill(m), np.asarray(V[:, month_index(m)]))
    rows.append(
        {"month": m, "filled_share": f, "world_difference": world, "tile_median_abs_difference": tiles}
    )
res["fills"] = rows
print("\n5. months filled from NOAA-20, refilled from NOAA-21 (difference: world, median 10 degree tile):")
for r in rows:
    print(
        f"   {r['month']}  filled {r['filled_share']:.0%}: world {r['world_difference']:+.1%}, tiles {r['tile_median_abs_difference']:.1%}"
    )

# 6. the hand-over: November 2026
world, tiles, n_big = difference(refill("2026-11"), np.asarray(H[:, month_index("2026-11")]))
res["handover"] = {"world_difference": world, "tile_median_abs_difference": tiles, "tiles": n_big}
print(
    f"\n6. November 2026 (to the 13th): NOAA-21, scaled to S-NPP, against the record (NOAA-20): world {world:+.1%}, median tile {tiles:.1%} over {n_big} tiles"
)
(HERE / "e13_results.json").write_text(json.dumps(res, indent=1, default=float))
