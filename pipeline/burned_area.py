#!/usr/bin/env python3
"""Check the harmonized record against burned area: hotspots per km² burned must not step at 2012.
Downloads FireCCI51, GFED5 and the GFED regions to data/external/ (1.3 GB, kept between runs) and writes
data/global/model/burned_area_check.json. Run: python3 pipeline/burned_area.py (needs scipy, h5py and curl).
"""

import io
import json
import os
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# at most 3 BLAS threads; must be set before numpy is imported
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_var, "3")

import h5py
import numpy as np
from scipy.io import netcdf_file
from scipy.stats import rankdata

from common import MODEL, ROOT, month_index

EXT = ROOT / "data/external"
YEARS = range(2003, 2021)  # Aqua flies all year from 2003; both products end in 2020
MONTHS = [(y, m) for y in YEARS for m in range(1, 13)]
JOIN = 2012  # VIIRS starts in February 2012
NBOOT = 2000  # year-resampling draws
TOL = 10.0  # a step beyond TOL percent whose interval excludes zero is a failure
NEAR = 4  # years each side of 2012 in the "near" test

CCI = "https://dap.ceda.ac.uk/neodc/esacci/fire/data/burned_area/MODIS/grid/v5.1/{y}/{sub}{y}{m:02d}01-ESACCI-L4_FIRE-BA-MODIS-fv5.1.nc"
CCI_HEAD = (
    4_300_000  # burned_area is the head of each 95 MB file and ends near byte 4,181,200 (checked on load)
)
GFED5 = "https://zenodo.org/api/records/7668424/files/BA.zip/content"
GFED4 = "https://www.geo.vu.nl/~gwerf/GFED/GFED4/GFED4.1s_2016.hdf5"  # only its 14 basis regions are used


def fetch(url, dest, head=None):
    """curl url to dest unless it is there; head = only the first that many bytes."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    how = ["-r", f"0-{head - 1}"] if head else ["-C", "-"]
    cmd = [
        "curl",
        "-fsSL",
        *how,
        "--retry",
        "3",
        "--speed-limit",
        "2000",
        "--speed-time",
        "45",
        "-o",
        str(part),
        url,
    ]
    for _ in range(8):  # servers drop long transfers; -C - picks up where the last try stopped
        if subprocess.run(cmd).returncode == 0:
            break
    else:
        raise SystemExit(f"download failed: {url}")
    part.rename(dest)
    return dest


def fetch_firecci(month):
    y, m = month
    sub = "new-corrected/" if y == 2019 and m >= 10 else ""  # the first release of Oct-Dec 2019 was faulty
    name = f"{y}{m:02d}01-ESACCI-L4_FIRE-BA-MODIS-fv5.1.nc.head"
    return fetch(CCI.format(y=y, m=m, sub=sub), EXT / "firecci51" / name, CCI_HEAD)


def firecci(row, col):
    """km² burned per cell and month (cells x months), and the product's world total."""
    with ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(fetch_firecci, MONTHS))
    out, tot = np.empty((len(row), len(MONTHS)), np.float32), 0.0
    for i, p in enumerate(paths):
        # the missing tail is padded with 0xff = NaN, so a head that was cut too short cannot pass as data
        nc = netcdf_file(io.BytesIO(p.read_bytes().ljust(96_000_000, b"\xff")), mmap=False)
        area, lat = nc.variables["burned_area"], nc.variables["lat"][:]
        assert area.units == b"m2" and np.isfinite(area[0]).all() and area[0].min() >= 0, p
        km2 = (area[0][::-1] if lat[0] > lat[-1] else area[0]) / 1e6
        out[:, i] = km2[row, col]
        tot += km2.sum(dtype=np.float64)
    return out, tot


def gfed5(row, col):
    z = zipfile.ZipFile(fetch(GFED5, EXT / "gfed5" / "BA.zip"))
    names = {Path(n).name: n for n in z.namelist()}
    out, tot = np.empty((len(row), len(MONTHS)), np.float32), 0.0
    for i, (y, m) in enumerate(MONTHS):
        with h5py.File(io.BytesIO(z.read(names[f"BA{y}{m:02d}.nc"]))) as f:
            assert f["lat"][0] < f["lat"][-1]
            km2 = np.nan_to_num(f["Total"][0])
        out[:, i] = km2[row, col]
        tot += km2.sum()
    return out, tot


def gfed_regions(row, col):
    with h5py.File(fetch(GFED4, EXT / "gfed4.1s" / "GFED4.1s_2016.hdf5")) as f:
        d = f["ancill/basis_regions"]
        assert f["lat"][0, 0] > f["lat"][-1, 0]  # the file runs north to south
        return d[:][::-1][row, col], [d.attrs[f"class_{i}"].split()[0] for i in range(1, 15)]


def rcorr(x, y):
    """Row-wise Pearson r."""
    x, y = x - x.mean(-1, keepdims=True), y - y.mean(-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (x * y).sum(-1) / np.sqrt((x * x).sum(-1) * (y * y).sum(-1))


def analyse(B, H, R, M, W, names, kinds):
    """All statistics for one burned-area array B (cells x months); W = units x cells membership."""
    yrs = np.array(YEARS)
    # 2012 is in neither period: January is modelled and VIIRS's first weeks are incomplete
    periods = {"pre": np.flatnonzero(yrs < JOIN), "post": np.flatnonzero(yrs > JOIN)}
    pre, post = periods["pre"], periods["post"]

    # three fire-size classes holding a third of the MODIS hotspots each, by km² burned per MODIS hotspot of the cell
    ms, bs = M.sum(1, dtype=np.float64), B.sum(1, dtype=np.float64)
    order = np.argsort(bs / (ms + 1))
    size_class = np.empty(len(order), int)
    size_class[order] = np.searchsorted([1 / 3, 2 / 3], np.cumsum(ms[order]) / ms.sum())
    W = np.vstack([W, [size_class == k for k in range(3)]])
    kinds = kinds + ["class"] * 3
    names = names + ["small fires (least km2/hotspot)", "middle third", "large fires (most km2/hotspot)"]

    series = {"ba": B, "H": H, "raw": R, "modis": M, "H_seen": H * (M > 0), "H_noba": H * (bs == 0)[:, None]}
    weights = W.astype(np.float64)
    U = {k: (weights @ np.asarray(x, np.float64)).reshape(len(W), len(yrs), 12) for k, x in series.items()}
    A = {k: u.sum(2) for k, u in U.items()}  # units x years

    def level(k, a=pre, b=post, den="ba"):
        """Series k per unit of den in years a and b, the step in percent, and its interval from resampling the years."""

        def ratio(i):
            return A[k][:, i].sum(-1) / A[den][:, i].sum(-1)

        rng = np.random.default_rng(0)  # the same draws for every series
        ia = a[rng.integers(0, len(a), (NBOOT, len(a)))]
        ib = b[rng.integers(0, len(b), (NBOOT, len(b)))]
        with np.errstate(invalid="ignore", divide="ignore"):
            ra, rb = ratio(a), ratio(b)
            ci = 100 * np.percentile(ratio(ia) / ratio(ib) - 1, [2.5, 97.5], axis=1).T
            return ra, rb, 100 * (ra / rb - 1), ci

    def season(k, i):
        """r of the mean monthly cycles, and the shift of the burned-area cycle with the best r (months, + = later)."""
        h, b = U[k][:, i].mean(1), U["ba"][:, i].mean(1)
        rs = np.array([rcorr(h, np.roll(b, -s, 1)) for s in range(-3, 4)])
        return rs[3], np.nanargmax(np.nan_to_num(rs, nan=-9), 0) - 3

    lev = {k: level(k) for k in ("H", "raw", "modis")}
    # only the years next to the join: a slow drift shrinks, a splice error stays
    lev |= {k + "_near": level(k, pre[-NEAR:], post[:NEAR]) for k in ("H", "modis")}
    # H per MODIS hotspot: the H step with the control divided out; burned area cancels, so not independent evidence
    lev["H_vs_modis"] = level("H", den="modis")
    var = {
        k: {
            p: (
                rcorr(A[k][:, i], A["ba"][:, i]),
                rcorr(rankdata(A[k][:, i], axis=1), rankdata(A["ba"][:, i], axis=1)),
            )
            for p, i in periods.items()
        }
        for k in ("H", "modis")
    }
    sea = {k: {p: season(k, i) for p, i in periods.items()} for k in ("H", "modis")}

    units = {}
    for u, n in enumerate(names):
        units[n] = {
            "kind": kinds[u],
            "ba_km2_per_year": A["ba"][u].mean(),
            "km2_per_modis_hotspot": A["ba"][u].sum() / A["modis"][u].sum(),
            "share_H_in_cells_without_burned_area": A["H_noba"][u].sum() / A["H"][u].sum(),
            "share_H_in_months_modis_saw_nothing": {
                p: 1 - A["H_seen"][u, i].sum() / A["H"][u, i].sum() for p, i in periods.items()
            },
            "annual": {k: A[k][u] for k in ("ba", "H", "raw", "modis")},
            "level": {
                k: {"pre": v[0][u], "post": v[1][u], "step_pct": v[2][u], "ci95": v[3][u]}
                for k, v in lev.items()
            },
            "variability": {k: {p: {"r": v[p][0][u], "rho": v[p][1][u]} for p in v} for k, v in var.items()},
            "seasonality": {
                k: {p: {"r": v[p][0][u], "lag_months": int(v[p][1][u])} for p in v} for k, v in sea.items()
            },
        }

    # the 14 regions pooled: anomalies standardised inside each region and period, then stacked
    regions = [u for u, k in enumerate(kinds) if k == "region"]

    def anomalies(a, i):
        x = a[regions][:, i]
        return ((x - x.mean(1, keepdims=True)) / x.std(1, keepdims=True)).ravel()

    pooled = {
        k: {p: float(rcorr(anomalies(A[k], i), anomalies(A["ba"], i))) for p, i in periods.items()}
        for k in ("H", "modis")
    }
    return units, pooled, [int(yrs[pre[0]]), int(yrs[pre[-1]]), int(yrs[post[0]]), int(yrs[post[-1]])]


def excludes_zero(d):
    return d["ci95"][0] * d["ci95"][1] > 0


def fails(d):
    return excludes_zero(d) and abs(d["step_pct"]) > TOL


def mark(d):
    return "FAIL" if fails(d) else "step" if excludes_zero(d) else "ok"


def fmt(d):
    return f"{d['step_pct']:+.0f}% [{d['ci95'][0]:+.0f},{d['ci95'][1]:+.0f}]"


def table(units, pooled, full):
    print(
        f"\n LEVEL: hotspots per km2 burned, estimated years against VIIRS years, step in % [95 % interval]\n {'unit':<32}{'km2/yr':>9} {'H est':>6} {'H VIIRS':>7}   {'step H':<17}{'step raw join':<17}{'step MODIS control':<19}{f'H, {NEAR} yrs each side':<20}{'H / control':<17}{'no-BA cells':>11}"
    )
    for n, d in units.items():
        if full or d["kind"] != "country":
            v = d["level"]
            print(
                f" {n[:31]:<32}{d['ba_km2_per_year']:>9.0f} {v['H']['pre']:>6.2f} {v['H']['post']:>7.2f}   {fmt(v['H']):<17}{fmt(v['raw']):<17}{fmt(v['modis']):<19}{fmt(v['H_near']):<20}{fmt(v['H_vs_modis']):<17}{100 * d['share_H_in_cells_without_burned_area']:>10.0f}%"
            )
    if not full:
        return
    cols = (("H", "pre", 12), ("H", "post", 13), ("modis", "pre", 12), ("modis", "post", 13))
    print(
        f"\n VARIABILITY (annual hotspots against annual burned area: r / rho) and SEASONALITY (r of the mean monthly cycles, and the lag in months with the best r)\n {'unit':<32}{'H est yrs':>12}{'H VIIRS yrs':>13}{'MODIS est':>12}{'MODIS VIIRS':>13}   |{'H est yrs':>12}{'H VIIRS yrs':>13}{'MODIS est':>12}{'MODIS VIIRS':>13}"
    )
    for n, d in units.items():
        v, s = d["variability"], d["seasonality"]
        print(
            f" {n[:31]:<32}"
            + "".join(f"{v[k][p]['r']:>{w - 6}.2f} /{v[k][p]['rho']:>5.2f}" for k, p, w in cols)
            + "   |"
            + "".join(f"{s[k][p]['r']:>{w - 5}.2f} ({s[k][p]['lag_months']:+d})" for k, p, w in cols)
        )
    print(
        f" {'14 regions pooled (r only)':<32}"
        + "".join(f"{pooled[k][p]:>{w - 6}.2f}      " for k, p, w in cols)
    )


def verdict(units, pooled):
    """Plain sentences that follow from the numbers."""

    def lv(n, k):
        return units[n]["level"][k]

    def named(n, k):
        return f"{n} {fmt(lv(n, k))}"

    def word(d):
        if fails(d):
            return "FAILS"
        if excludes_zero(d):
            return "a real but small step (interval excludes zero, inside the tolerance)"
        return "no detectable step"

    power = (
        "steps as it must, so the test has power. "
        if fails(lv("World", "raw"))
        else "DOES NOT STEP, so the test has no power. "
    )
    out = [
        f"World level. H: {fmt(lv('World', 'H'))}, {word(lv('World', 'H'))}. Raw join: {fmt(lv('World', 'raw'))}, "
        + power
        + f"MODIS control: {fmt(lv('World', 'modis'))}, {word(lv('World', 'modis'))}. H with the control divided out: {fmt(lv('World', 'H_vs_modis'))} (burned area cancels in this figure; it is not independent evidence)."
    ]
    for kind in ("region", "country", "class"):
        us = [n for n, d in units.items() if d["kind"] == kind]
        fh = [n for n in us if fails(lv(n, "H"))]
        fm = [n for n in us if fails(lv(n, "modis"))]
        fx = [n for n in us if fails(lv(n, "H_vs_modis"))]
        small = [n for n in us if excludes_zero(lv(n, "H")) and n not in fh]
        out.append(
            f"Level by {kind} ({len(us)}). H FAILS in {len(fh)}: {'; '.join(named(n, 'H') for n in fh) or 'none'}. Real but small step in {len(small)}: {', '.join(small) or 'none'}. The MODIS control FAILS in {len(fm)}: {'; '.join(named(n, 'modis') for n in fm) or 'none'}. "
            f"H fails while the control holds (points at the record): {', '.join(n for n in fh if n not in fm) or 'none'}. Control fails while H does not (H's pass is no evidence there): {', '.join(n for n in fm if n not in fh) or 'none'}. "
            f"H departs from the control by more than the tolerance: {'; '.join(named(n, 'H_vs_modis') for n in fx) or 'none'}."
        )
    p = pooled
    follows = (
        "FAILS: the estimates follow burned area clearly worse than real VIIRS does. "
        if p["H"]["pre"] < p["H"]["post"] - 0.1
        else "The estimated years do not follow burned area worse than the VIIRS years. "
    )
    out.append(
        f"Variability pooled over the 14 regions: r = {p['H']['pre']:.2f} for H in the estimated years and {p['H']['post']:.2f} in the VIIRS years (MODIS: {p['modis']['pre']:.2f} and {p['modis']['post']:.2f}). "
        + follows
        + "Before 2012 H is a function of MODIS and both products are seeded with MODIS hotspots, so a high r there is partly built in."
    )
    us = [n for n, d in units.items() if d["kind"] in ("region", "country")]
    for key, what, gap in (("variability", "annual totals", 0.2), ("seasonality", "mean monthly cycle", 0.1)):

        def r(n, k, q):
            return units[n][key][k][q]["r"]

        drop = [
            f"{n} (H {r(n, 'H', 'pre'):.2f} vs {r(n, 'H', 'post'):.2f}; MODIS {r(n, 'modis', 'pre'):.2f} vs {r(n, 'modis', 'post'):.2f})"
            for n in us
            if r(n, "H", "pre") < r(n, "H", "post") - gap
        ]
        worse = [
            f"{n} (H {r(n, 'H', 'pre'):.2f} vs MODIS {r(n, 'modis', 'pre'):.2f}; after 2012 VIIRS {r(n, 'H', 'post'):.2f} vs MODIS {r(n, 'modis', 'post'):.2f})"
            for n in us
            if r(n, "H", "pre") < r(n, "modis", "pre") - 0.1
        ]
        out.append(
            f"{key.capitalize()} by region and country ({what} against burned area, r). Lower before 2012 than after by more than {gap}: {'; '.join(drop) or 'none'}. H worse than its own MODIS input before 2012 by more than 0.1 (real VIIRS doing the same after 2012 makes this expected): {'; '.join(worse) or 'none'}."
        )
    return out


def tidy(o):
    if isinstance(o, dict):
        return {k: tidy(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)):
        return [tidy(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(f"{o:.4g}") if np.isfinite(o) else None
    return o


def main():
    H, M, V = (np.load(MODEL / f"{n}.npy", mmap_mode="r") for n in "HMV")
    keys, country = np.load(MODEL / "keys.npy"), np.load(MODEL / "country.npy")
    cnames = json.loads((MODEL / "metrics.json").read_text())["country_names"]
    t0, t_viirs = month_index(f"{YEARS[0]}-01"), month_index(f"{JOIN}-02")
    t1 = t0 + 12 * len(YEARS)
    assert H.shape[1] >= t1 and np.array_equal(
        H[:, t_viirs:], V[:, t_viirs:]
    ), "H is expected to be VIIRS itself from Feb 2012 and to reach the end of the burned-area record"
    H, M, V = (np.array(a[:, t0:t1]) for a in (H, M, V))
    R = np.where(np.arange(t0, t1) < t_viirs, M, V)  # the raw join
    row, col = (
        keys // 4000 - 400 + 360,
        keys % 4000 - 800 + 720,
    )  # indices into a south-to-north 720 x 1440 grid
    region, rnames = gfed_regions(row, col)
    top = np.argsort(-np.bincount(country[country >= 0], H.sum(1)[country >= 0], len(cnames)))[:25]
    W = np.array(
        [np.ones(len(keys), bool)] + [region == i + 1 for i in range(14)] + [country == c for c in top]
    )
    names = ["World"] + rnames + [cnames[c] for c in top]
    kinds = ["world"] + ["region"] * 14 + ["country"] * 25
    res = {
        "years": list(YEARS),
        "tolerance_pct": TOL,
        "bootstrap_draws": NBOOT,
        "share_H_outside_gfed_regions": float(H[region == 0].sum() / H.sum()),
        "products": {},
    }
    for label, load, note in (
        ("FireCCI51", firecci, "primary: reflectance-based area, MODIS hotspots only as seeds"),
        ("GFED5", gfed5, "robustness only: up to half of its area is derived from MODIS hotspots"),
    ):
        B, tot = load(row, col)
        # burned area and hotspots must fall in the same cells, or the grids are misaligned
        check = float(rcorr(rankdata(B.sum(1)), rankdata(M.sum(1))))
        assert (
            check > 0.3
        ), f"{label}: burned area does not line up with the hotspot cells (rank r = {check:.2f})"
        units, pooled, per = analyse(B, H, R, M, W, names, kinds)
        v = verdict(units, pooled)
        print(
            f"\n{'=' * 160}\n {label} ({note}); estimated years {per[0]}-{per[1]}, VIIRS years {per[2]}-{per[3]}; {100 * B.sum(dtype=np.float64) / tot:.2f} % of its burned area lies in the model's cells; rank r over cells with MODIS hotspots {check:.2f}"
        )
        table(units, pooled, label == "FireCCI51")
        print("\n VERDICT")
        for s in v:
            print("  - " + s)
        res["products"][label] = {
            "note": note,
            "periods": per,
            "share_of_burned_area_in_model_cells": B.sum(dtype=np.float64) / tot,
            "cell_rank_r_with_modis": check,
            "regions_pooled_variability_r": pooled,
            "verdict": v,
            "units": units,
        }

    # A unit's yardstick is trusted when FireCCI51 maps at least half of GFED5's area there
    # and under 10 % of its hotspots lie in cells with no mapped burned area.
    a, b = (res["products"][k]["units"] for k in ("FireCCI51", "GFED5"))
    cross = {}
    print(
        f"\n{'=' * 160}\n CROSS-CHECK: step of H in both products (FAIL = beyond {TOL:.0f} % and interval excludes zero; step = interval excludes zero; ok = no detectable step)\n {'unit':<32}{'FireCCI51':<24}{'GFED5':<24}{'area ratio':>10}{'no-BA cells':>12}  yardstick"
    )
    for n in names:
        x, y = a[n]["level"]["H"], b[n]["level"]["H"]
        ratio = a[n]["ba_km2_per_year"] / b[n]["ba_km2_per_year"]
        no_ba = a[n]["share_H_in_cells_without_burned_area"]
        cross[n] = {
            "FireCCI51": mark(x),
            "GFED5": mark(y),
            "area_ratio": ratio,
            "trusted": bool(ratio >= 0.5 and no_ba <= 0.1),
        }
        print(
            f" {n[:31]:<32}{fmt(x) + ' ' + mark(x):<24}{fmt(y) + ' ' + mark(y):<24}{ratio:>10.2f}{100 * no_ba:>11.0f}%  {'trusted' if cross[n]['trusted'] else 'weak'}"
        )
    trusted = [n for n in names if cross[n]["trusted"]]

    def failing(in_cci, in_gfed):
        """Trusted units whose H fails (or not) in each product."""
        hits = [
            n
            for n in trusted
            if (cross[n]["FireCCI51"] == "FAIL") == in_cci and (cross[n]["GFED5"] == "FAIL") == in_gfed
        ]
        return ", ".join(hits) or "none"

    both = (
        "; ".join(
            f"{n} (H {fmt(a[n]['level']['H'])} and {fmt(b[n]['level']['H'])}; MODIS control {fmt(a[n]['level']['modis'])} and {fmt(b[n]['level']['modis'])}; H over control {fmt(a[n]['level']['H_vs_modis'])})"
            for n in trusted
            if cross[n]["FireCCI51"] == cross[n]["GFED5"] == "FAIL"
        )
        or "none"
    )
    blind = b["World"]["share_H_in_months_modis_saw_nothing"]
    final = [
        f"Trusted yardstick in {len(trusted)} of {len(names)} units; weak (small, cropland, deforestation fires or gas flares; ignore their verdicts) in: {', '.join(n for n in names if n not in trusted) or 'none'}.",
        f"Among trusted units H FAILS the level check in both products in: {both}. In FireCCI51 only: {failing(True, False)}. In GFED5 only: {failing(False, True)}. In neither: {failing(False, False)}.",
        f"In the world total, {100 * blind['pre']:.1f} % of H lies in cell-months where MODIS saw nothing in the estimated years, against {100 * blind['post']:.1f} % of real VIIRS afterwards (not a burned-area test).",
    ]
    print("\n FINAL VERDICT")
    for s in final:
        print("  - " + s)
    res |= {"cross_check": cross, "final_verdict": final}
    (MODEL / "burned_area_check.json").write_text(json.dumps(tidy(res), separators=(",", ":")))
    print(f"\nwrote {MODEL / 'burned_area_check.json'}")


if __name__ == "__main__":
    main()
