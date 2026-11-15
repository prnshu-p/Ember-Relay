"""E14: Landsat 8 and 9 (30 m fire pixels) check where the record puts fire, in the US and Canada south of 50°N
from July 2022. See docs/EXPERIMENTS.md, E14. Run: python3 pipeline/experiments/e14_landsat.py
(needs the Landsat files of `download_api.py extra` and stage 2's outputs)"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import CELL, DATA, MODEL, T0, cell_key, cell_lat, cell_lon, month_index  # noqa: E402

A, B = month_index("2022-07"), month_index("2026-10")  # whole months with Landsat in FIRMS, and of the record
T = B - A + 1
keys = np.load(MODEL / "keys.npy")
C = len(keys)
names = json.loads((MODEL / "metrics.json").read_text())["country_names"]
country = np.load(MODEL / "country.npy")
us, ca = names.index("United States"), names.index("Canada")
lat, lon = cell_lat(keys), cell_lon(keys)
area = np.isin(country, [us, ca]) & (lat < 50)
H = np.asarray(np.load(MODEL / "H.npy", mmap_mode="r")[:, A : B + 1])

files = sorted(DATA.glob("api_cache/LANDSAT_NRT_*.csv"))
columns = ["latitude", "longitude", "acq_date", "confidence", "daynight"]
d = pd.concat(pd.read_csv(f, usecols=columns) for f in files).drop_duplicates()
confidence = d.confidence.value_counts().to_dict()
d = d[d.confidence.isin(["M", "H", "medium", "high", "nominal", "n", "h"])]  # nominal and high, as for VIIRS
ilat = np.floor(d.latitude.values / CELL).astype(np.int64)
ilon = np.floor(d.longitude.values / CELL).astype(np.int64)
k = cell_key(ilat, ilon)
date = pd.to_datetime(d.acq_date)
t = (date.dt.year * 12 + date.dt.month - 1).values - T0 - A
i = np.minimum(np.searchsorted(keys, k), C - 1)
in_time = (t >= 0) & (t < T)
on = (keys[i] == k) & in_time
landsat = np.zeros((C, T), np.float32)
np.add.at(landsat, (i[on], t[on]), 1)
# off the record's cells: persistent heat sources and places VIIRS never saw fire
outside = float(1 - on.sum() / max(in_time.sum(), 1))
res = {
    "files": len(files),
    "detections_kept": int(on.sum()),
    "confidence_values": {str(a): int(b) for a, b in confidence.items()},
    "share_outside_record_grid": outside,
}
print(
    f"{len(files)} files; {on.sum():,} Landsat detections of nominal or high confidence on the record's grid; {outside:.1%} fall in cells the record does not have"
)

# 1. where
Lc, Hc = landsat[area], H[area]
land = Lc >= 2
res["landsat_fire_cell_months"] = int(land.sum())
res["record_has_fire_there"] = float((Hc[land] >= 1).mean())
rec = Hc >= 10
res["record_fire_cell_months"] = int(rec.sum())
res["landsat_saw_fire_there"] = float((Lc[rec] >= 1).mean())
big = Hc >= 100
res["landsat_saw_fire_where_record_100"] = float((Lc[big] >= 1).mean())
print(
    f"\n1. cell-months (US and Canada south of 50N, Jul 2022 - Oct 2026): where Landsat saw 2+ fire pixels ({land.sum():,}) the record has fire in {res['record_has_fire_there']:.0%}; "
    f"where the record has 10+ hotspots ({rec.sum():,}) Landsat saw fire in {res['landsat_saw_fire_there']:.0%} (100+: {res['landsat_saw_fire_where_record_100']:.0%})"
)

# 2. how much, as a pattern
bx = np.unique(
    (np.floor(lat).astype(np.int64) + 90) * 400 + np.floor(lon).astype(np.int64) + 180, return_inverse=True
)[1]
nb = bx.max() + 1
Lb = np.stack([np.bincount(bx[area], Lc[:, j], nb) for j in range(T)], axis=1)
Hb = np.stack([np.bincount(bx[area], Hc[:, j], nb) for j in range(T)], axis=1)
both = (Lb > 0) | (Hb > 0)
rho = stats.spearmanr(Lb[both], Hb[both])[0]
monthly = {
    n: (landsat[area & (country == c)].sum(axis=0), H[area & (country == c)].sum(axis=0))
    for n, c in (("United States", us), ("Canada south of 50N", ca))
}
res["box_month_spearman"] = float(rho)
res["country_month_spearman"] = {n: float(stats.spearmanr(a, b)[0]) for n, (a, b) in monthly.items()}
print(
    f"\n2. rank correlation of monthly totals: 1 degree box-months {rho:.2f} ({both.sum():,} with fire in either); "
    + ", ".join(f"{n} months {v:.2f}" for n, v in res["country_month_spearman"].items())
)


# 3. the near-real-time months against the same months of earlier years
def record_per_landsat(year):
    ts = [month_index(f"{year}-{m:02d}") - A for m in (8, 9, 10)]
    return Hc[:, ts].sum() / max(Lc[:, ts].sum(), 1)


res["record_per_landsat"] = {y: record_per_landsat(y) for y in (2023, 2024, 2025, 2026)}
print(
    "\n3. record hotspots per Landsat fire pixel, August to October (2026: near-real-time, cleaned by place): "
    + ", ".join(f"{y} {v:.2f}" for y, v in res["record_per_landsat"].items())
)
(HERE / "e14_results.json").write_text(json.dumps(res, indent=1, default=float))
