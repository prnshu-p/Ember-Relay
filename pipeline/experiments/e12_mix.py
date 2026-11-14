"""E12: is the record's step against MODIS at 2012 a conversion error, or did the mix of fires change? See
docs/EXPERIMENTS.md, E12. Run: python3 pipeline/experiments/e12_mix.py (seconds; needs stage 2's outputs)"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import MODEL, cell_lat, cell_lon, month_index, month_name  # noqa: E402

H, M, V = (np.load(MODEL / f"{n}.npy", mmap_mode="r") for n in ("H", "M", "V"))
keys = np.load(MODEL / "keys.npy")
country = np.load(MODEL / "country.npy")
metrics = json.loads((MODEL / "metrics.json").read_text())
names = metrics["country_names"]
gaps = metrics["outages"]["months"]
lat, lon = cell_lat(keys), cell_lon(keys)
T = H.shape[1]
t = np.arange(T)
cal = (t + 10) % 12  # calendar month, 0 = January
modis_ok = np.array(
    [max(gaps.get(month_name(i), {}).get(k, 0) for k in ("terra", "aqua")) <= 0.2 for i in range(T)]
)
pre = (t >= month_index("2002-07")) & (t < month_index("2012-02")) & modis_ok
post = (t >= month_index("2012-02")) & (t < month_index("2020-01")) & modis_ok
box = (np.floor(lat).astype(np.int64) + 90) * 400 + np.floor(lon).astype(np.int64) + 180


def split(cells):
    """(step at 2012, the part a fixed ratio per box and calendar month would show, the rest, VIIRS hotspots after)."""
    if not cells.any():
        return None
    b = np.unique(box[cells], return_inverse=True)[1]
    nb = b.max() + 1
    Hc, Mc, Vc = (np.asarray(A[cells], np.float64) for A in (H, M, V))

    def strata(A, months):
        """Box x calendar month totals."""
        return np.stack(
            [np.bincount(b, A[:, months & (cal == c)].sum(axis=1), nb) for c in range(12)], axis=1
        )

    hp, mp, vq, mq = strata(Hc, pre), strata(Mc, pre), strata(Vc, post), strata(Mc, post)
    if min(mp.sum(), mq.sum(), hp.sum(), vq.sum()) <= 0:
        return None
    r_all = vq.sum() / mq.sum()
    r_post = (vq + 50 * r_all) / (mq + 50)  # each stratum's ratio after 2012, shrunk toward the area's
    fixed = (mp * r_post).sum() / mp.sum()
    total = r_all / (hp.sum() / mp.sum()) - 1
    mix = r_all / fixed - 1
    return total, mix, (1 + total) / (1 + mix) - 1, vq.sum()


rows = [("World", split(np.ones(len(keys), bool)))] + [(n, split(country == i)) for i, n in enumerate(names)]
rows = [(n, r) for n, r in rows if r and (n == "World" or r[3] >= 2e6)]
rows.sort(key=lambda x: -x[1][3])
print(f"{'':<34}{'step at 2012':>13}{'from the mix':>14}{'within strata':>15}")
for n, (step, mix, within, _) in rows:
    print(f"{n:<34}{step:>+13.1%}{mix:>+14.1%}{within:>+15.1%}")
steps = np.array([r[0] for _, r in rows[1:]])
withins = np.array([r[2] for _, r in rows[1:]])
print(
    f"\n{len(withins)} countries with 2 million or more VIIRS hotspots: median |step| {np.median(abs(steps)):.1%}; median |within strata| {np.median(abs(withins)):.1%}; within 5 %: {np.mean(abs(withins) < .05):.0%}"
)

russia = country == names.index("Russian Federation")
russia_pre, russia_post = np.asarray(M[russia][:, pre]).sum(), np.asarray(M[russia][:, post]).sum()
south = lat < 55
for part, cells in (("Russia south of 55N", russia & south), ("Russia north of 55N", russia & ~south)):
    for season, months in (("Mar-May", (2, 3, 4)), ("Jun-Sep", (5, 6, 7, 8))):
        sel = np.isin(cal, months)
        mp, mq = np.asarray(M[cells][:, pre & sel]).sum(), np.asarray(M[cells][:, post & sel]).sum()
        vq, hp = np.asarray(V[cells][:, post & sel]).sum(), np.asarray(H[cells][:, pre & sel]).sum()
        print(
            f"  {part}, {season}: share of Russia's MODIS hotspots {mp / russia_pre:.0%} before, {mq / russia_post:.0%} after 2012; VIIRS/MODIS after 2012 {vq / mq:.2f}; record/MODIS before {hp / mp:.2f}"
        )
(HERE / "e12_results.json").write_text(
    json.dumps({n: dict(zip(("step", "mix", "within"), r[:3])) for n, r in rows}, indent=1)
)
