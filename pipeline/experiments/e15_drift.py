"""E15: does the drift of the MODIS orbits, read against GOES's daily cycle of fire, explain why every conversion
reads low after 2020? See docs/EXPERIMENTS.md, E15. Run: python3 pipeline/experiments/e15_drift.py (needs
data/global/zips, the 2026 API cache, the GOES sample of `download_api.py extra`, and stage 1's and 2's outputs)
"""

import json
import sys
import zipfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import CELL, CELLS, DATA, MODEL, T0, cell_lat, cell_lon  # noqa: E402

BOX = dict(s=-20.0, n=5.0, w=-75.0, e=-35.0)  # tropical South America, seen well by GOES-East
COUNTRIES = ("Brazil", "Bolivia", "Paraguay", "Peru", "Colombia", "Venezuela")
COLUMNS = ["latitude", "longitude", "acq_date", "acq_time", "satellite", "daynight"]
SATELLITES = {
    "T": "Terra",
    "A": "Aqua",
    "N": "S-NPP",
    "N20": "NOAA-20",
    "1": "NOAA-20",
    "Terra": "Terra",
    "Aqua": "Aqua",
}
PASSES = (("Terra", "D", "nTd"), ("Aqua", "D", "nAd"), ("Terra", "N", "nTn"), ("Aqua", "N", "nAn"))
MODIS_COUNTS = ("nTd", "nTn", "nAd", "nAn")  # stage 1's MODIS counts: Terra day and night, Aqua day and night
BASE = list(range(2013, 2020))  # the years before the drift that everything is relative to


def inside(lat, lon):
    return (lat >= BOX["s"]) & (lat < BOX["n"]) & (lon >= BOX["w"]) & (lon < BOX["e"])


def in_box(df):
    return df[inside(df.latitude, df.longitude)]


def solar_hour(df):
    """Local solar time in hours: UTC + longitude / 15 + the equation of time."""
    t = pd.to_numeric(df.acq_time, errors="coerce").astype(int)
    utc = t // 100 + (t % 100) / 60
    day = pd.to_datetime(df.acq_date).dt.dayofyear.values
    b = np.deg2rad(360 / 365 * (day - 81))
    eot = (9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)) / 60
    return np.mod(utc.values + df.longitude.values / 15 + eot, 24)


def sat_name(s):
    return SATELLITES.get(str(s), str(s))


def summarize(df, year):
    """Median local solar time of the day and of the night detections, per satellite."""
    df = df.assign(h=solar_hour(df), sat=df.satellite.map(sat_name))
    out = []
    for (sat, dn), g in df.groupby(["sat", "daynight"]):
        h = g.h.values if dn == "D" else np.mod(g.h.values + 12, 24) - 12  # nights straddle midnight
        out.append(
            {
                "year": year,
                "satellite": sat,
                "daynight": dn,
                "hour": float(np.median(h)) % 24,
                "n": int(len(g)),
            }
        )
    return out


def year_times(job):
    """summarize() for one yearly archive of FIRMS country files."""
    path, year = job
    z = zipfile.ZipFile(path)
    parts = [
        in_box(pd.read_csv(z.open(info), usecols=COLUMNS, dtype={"acq_time": str}))
        for info in z.infolist()
        if any(f"_{c}.csv" in info.filename for c in COUNTRIES)
    ]
    return summarize(pd.concat(parts), year)


def overpass():
    """(A) the observing times per year: MODIS from every yearly archive, VIIRS from a few, 2026 from the API."""
    zips = DATA / "zips"
    jobs = [(str(zips / f"modis_{y}_all_countries.zip"), y) for y in range(2001, 2026)]
    jobs += [(str(zips / f"viirs-snpp_{y}_all_countries.zip"), y) for y in (2013, 2019, 2023, 2025)]
    jobs += [(str(zips / f"viirs-jpss1_{y}_all_countries.zip"), y) for y in (2019, 2025)]
    with Pool(4) as p:
        rows = [r for part in p.map(year_times, jobs) for r in part]
    for prod in ("MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"):  # 2026, January to July/August
        files = sorted((DATA / "api_cache").glob(f"{prod}_2026-*.csv"))
        dtype = {"acq_time": str, "satellite": str}
        df = pd.concat(in_box(pd.read_csv(f, usecols=COLUMNS, dtype=dtype)) for f in files)
        rows += summarize(df, 2026)
    return pd.DataFrame(rows)


def diurnal(files):
    """(B) the daily cycle of fire in the box from the GOES sample: detections per local half hour, mean 1."""
    dtype = {"acq_time": str, "satellite": str}
    df = pd.concat(
        in_box(
            pd.read_csv(
                f, usecols=["latitude", "longitude", "acq_date", "acq_time", "satellite"], dtype=dtype
            )
        )
        for f in files
    )
    df = df[df.satellite.isin(["G16", "G19"])]  # GOES-East only: one satellite, one look at every hour
    counts = np.bincount((solar_hour(df) * 2).astype(int) % 48, minlength=48).astype(float)
    wrapped = np.r_[counts[-2:], counts, counts[:2]]
    smooth = np.convolve(wrapped, np.ones(5) / 5, mode="valid")  # 2.5-hour running mean
    return smooth / smooth.mean(), len(files), int(len(df)), sorted(df.satellite.unique().tolist())


def activity(curve, hour):
    """The cycle at a time of day, interpolated between half hours."""
    x = np.arange(48) / 2 + 0.25
    return float(np.interp(hour % 24, x, curve, period=24))


def observed():
    """(C) per year in the box: Terra and Aqua, day and night, as detected (stage 1), and Suomi NPP with its lost
    days filled from NOAA-20 (stage 2's V). Months in which Terra or Aqua lost 3% or more are left out."""
    gaps = json.loads((MODEL / "metrics.json").read_text())["outages"]["months"]
    keys = np.load(MODEL / "keys.npy")
    cells = inside(cell_lat(keys), cell_lon(keys))
    V = np.load(MODEL / "V.npy", mmap_mode="r")
    rows = []
    for y in range(2012, 2027):
        mo = pd.read_parquet(CELLS / f"modis_{y}.parquet", columns=["ilat", "ilon", "ym", *MODIS_COUNTS])
        mo = mo[inside(mo.ilat * CELL, mo.ilon * CELL)]
        months = [
            k
            for k in range(12)
            if (2012, 1) <= (y, k) <= (2026, 6)  # February 2012 to July 2026
            and max(gaps.get(f"{y}-{k + 1:02d}", {}).get(s, 0) for s in ("terra", "aqua")) < 0.03
        ]
        keep = np.isin(mo.ym.values - y * 12, months)
        rows.append(
            {
                "year": y,
                "months": len(months),
                **{c: float(mo[c].values[keep].sum()) for c in MODIS_COUNTS},
                "snpp": float(sum(np.asarray(V[cells, y * 12 + k - T0]).sum() for k in months)),
            }
        )
    return pd.DataFrame(rows)


def drift(curve, piv):
    """(C) each pass's count per S-NPP hotspot by year, observed and predicted from the cycle at its observing hour."""

    def hour(sat, dn, y):
        return float(piv.loc[y, (sat, dn)]) if (sat, dn) in piv.columns and y in piv.index else np.nan

    obs = observed()
    rows = []
    for _, r in obs.iterrows():
        y = int(r.year)
        row = {"year": y}
        for sat, dn, col in PASSES:
            row[f"{sat} {dn} observed"] = r[col] / r.snpp
            row[f"{sat} {dn} hour"] = hour(sat, dn, y)
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("year")
    late = tab.index.values >= 2020

    comparison = []
    for sat, dn, _ in PASSES:
        o = tab[f"{sat} {dn} observed"]
        h = tab[f"{sat} {dn} hour"]
        obs_rel = (o / o.loc[BASE].mean()).values
        pred = np.array([activity(curve, x) for x in h]) / np.mean([activity(curve, x) for x in h.loc[BASE]])
        c = {
            "satellite": sat,
            "daynight": dn,
            "years": tab.index.tolist(),
            "hour": h.round(2).tolist(),
            "observed": np.round(obs_rel, 3).tolist(),
            "predicted": np.round(pred, 3).tolist(),
            "r_all_years": float(np.corrcoef(obs_rel, pred)[0, 1]),
            "base_sd": float(np.std(obs_rel[~late])),
            "shift_2026": [float(obs_rel[-1] - 1), float(pred[-1] - 1)],
        }
        comparison.append(c)
        print(
            f"\n{sat} {'day' if dn == 'D' else 'night'}: count per S-NPP hotspot, relative to 2013-2019, observed / predicted from the GOES cycle at the observing hour"
            f" (r over 2012-2026 {c['r_all_years']:.2f}; year-to-year spread before 2020 {c['base_sd']:.2f})"
        )
        print(
            "  "
            + "  ".join(
                f"{y}: {a:.2f}/{b:.2f} ({hh:.1f}h)" for y, a, b, hh in zip(tab.index, obs_rel, pred, h)
            )
        )

    # the whole of MODIS: day and night of both satellites, as counted
    tot = obs.assign(m=obs.nTd + obs.nTn + obs.nAd + obs.nAn)
    tot["obs"] = tot.m / tot.snpp
    tot["obs"] /= tot.set_index("year").loc[BASE, "obs"].mean()
    weight = {col: obs.set_index("year").loc[BASE, col].sum() for _, _, col in PASSES}

    def modis_predicted(y):
        """Each pass scaled by the cycle at its hour, weighted by its share of 2013-2019."""
        parts = (
            weight[col]
            * activity(curve, hour(sat, dn, y))
            / np.mean([activity(curve, hour(sat, dn, b)) for b in BASE])
            for sat, dn, col in PASSES
        )
        return sum(parts) / sum(weight.values())

    tot["pred"] = [modis_predicted(int(y)) for y in tot.year]
    total = tot[["year", "obs", "pred"]].round(3).to_dict("records")
    print(
        "\nall of MODIS per S-NPP hotspot, relative to 2013-2019, observed / predicted:\n  "
        + "  ".join(f"{int(r.year)}: {r.obs:.2f}/{r.pred:.2f}" for r in tot.itertuples())
    )
    return comparison, total


def main():
    out = {}
    ov = overpass()
    out["overpass"] = ov.to_dict("records")
    piv = ov.pivot_table(index="year", columns=["satellite", "daynight"], values="hour")
    print(
        "local solar time of fire detections (median), tropical South America:\n" + piv.round(2).to_string()
    )
    goes = sorted((DATA / "api_cache").glob("GOES_NRT_2024-*.csv"))
    if len(goes) >= 30:
        curve, nf, nd, sats = diurnal(goes)
        out["diurnal"] = {
            "curve_half_hours": curve.round(4).tolist(),
            "files": nf,
            "detections": nd,
            "satellites": sats,
        }
        print(
            f"\nGOES daily cycle from {nf} days, {nd:,} detections ({sats}); peak at {np.argmax(curve) / 2 + 0.25:.2f} h local solar time"
        )
        print(
            "  relative activity at 09:00, 10:30, 13:30, 15:00, 15:30:",
            [round(activity(curve, h), 2) for h in (9, 10.5, 13.5, 15, 15.5)],
        )
        out["comparison"], out["modis_total"] = drift(curve, piv)
    else:
        print(f"\nGOES sample not complete yet ({len(goes)} of 36 days): parts B and C wait for it")
    (HERE / "e15_results.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
