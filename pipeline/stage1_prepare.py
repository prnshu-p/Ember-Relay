"""Stage 1: FIRMS detections (yearly archives in data/global/zips, 2026 from data/global/api_cache) -> monthly
statistics per 0.25 degree cell, one set of parquet files per sensor and year in data/global/cells/.
Run: python3 pipeline/stage1_prepare.py [name filter ...]   (skips what is already done)"""

import io
import json
import re
import sys
import zipfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from common import CELL, CELLS, DATA

USE = {
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "confidence",
    "frp",
    "daynight",
    "type",
    "scan",
    "track",
    "satellite",
    "brightness",
    "bright_ti4",
}
# Output name -> [(API product, first day, last day)]. NOAA-21 is read only to test the record (E13).
API_2026 = {
    "viirs-noaa21_2023": [("VIIRS_NOAA21_SP", "2023-03-01", "2023-12-31")],
    "viirs-noaa21_2024": [("VIIRS_NOAA21_SP", "2024-01-01", "2024-12-31")],
    "viirs-noaa21_2025": [("VIIRS_NOAA21_SP", "2025-01-01", "2025-12-31")],
    "viirs-noaa21_2026": [
        ("VIIRS_NOAA21_SP", "2026-01-01", "2026-07-31"),
        ("VIIRS_NOAA21_NRT", "2026-08-01", "2026-12-31"),
    ],
    "modis_2026": [("MODIS_SP", "2026-01-01", "2026-08-31"), ("MODIS_NRT", "2026-09-01", "2026-12-31")],
    "viirs-snpp_2026": [
        ("VIIRS_SNPP_SP", "2026-01-01", "2026-07-31"),
        ("VIIRS_SNPP_NRT", "2026-08-01", "2026-11-02"),
    ],
    "viirs-jpss1_2026": [
        ("VIIRS_NOAA20_SP", "2026-01-01", "2026-07-31"),
        ("VIIRS_NOAA20_NRT", "2026-08-01", "2026-12-31"),
    ],
}
# download_api.py's 5-day windows start on the product's first day, or on this day.
ORIGIN = {"VIIRS_NOAA21_SP": "2023-03-01"}
SPOT = {"modis": 0.01, "viirs": 0.005}  # place mask grid, degrees (about 1 km and 500 m)
MASK_FROM = 2023  # other heat sources flagged since this year make the mask
CELL_MONTH = ["ilat", "ilon", "ym"]


class NotReady(Exception):
    pass


def spot(df, size):
    """The place mask square each detection falls in."""
    return (
        (np.floor(df.latitude.values / size).astype(np.int64) + 40000) * 100000
        + np.floor(df.longitude.values / size).astype(np.int64)
        + 40000
    )


def grow(spots):
    """These squares and the eight around each."""
    around = np.array([dy * 100000 + dx for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return np.unique((np.asarray(spots, np.int64)[:, None] + around).ravel())


def mask_for(kind):
    """The place mask, from the record's own sensors only, so that NOAA-21 can never change the record."""
    prefixes = ("modis",) if kind == "modis" else ("viirs-snpp", "viirs-jpss1")
    files = [
        f
        for prefix in prefixes
        for f in CELLS.glob(f"{prefix}_20[0-9][0-9]_static.parquet")
        if MASK_FROM <= int(f.stem.split("_")[1]) < 2026
    ]
    if not files:
        return np.zeros(0, np.int64)
    return grow(np.unique(np.concatenate([pd.read_parquet(f, columns=["spot"]).spot.values for f in files])))


def confident(df):
    conf = pd.to_numeric(df["confidence"], errors="coerce")
    return ((conf >= 30) | df["confidence"].isin(["n", "h"])).values


def mask_check(df, size, mask):
    """How well the place mask stands in for the type flag, on typed rows it was not built from."""
    df = df[confident(df)]
    ty = pd.to_numeric(df["type"]).values
    hit = np.isin(spot(df, size), mask)
    fire, other = ty == 0, ty > 0
    return {
        "other_sources_removed": float(hit[other].mean()),
        "fires_removed": float(hit[fire].mean()),
        "excess_without_mask": float(other.sum() / fire.sum()),
        "net_error_with_mask": float(((other & ~hit).sum() - (fire & hit).sum()) / fire.sum()),
        "rows": int(len(df)),
    }


def clean(df, size, mask):
    """-> (the vegetation fires, with cell and month; the detections typed as another heat source, per spot and type)"""
    df = df.rename(columns={"bright_ti4": "brightness"})
    df = df.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time"])
    # Near-real-time rows have no type. A type that is not a number means a damaged file: fail.
    ty = pd.to_numeric(df["type"]).values if "type" in df else np.full(len(df), np.nan)
    key = spot(df, size)
    other = ty > 0
    static = pd.DataFrame({"spot": key[other], "type": ty[other].astype("int8")})
    static = static.value_counts().rename("n").reset_index()
    df = df[~other & ~(np.isnan(ty) & np.isin(key, mask))]  # untyped rows: other sources removed by place
    df = df[confident(df)].copy()
    df["ilat"] = np.floor(df.latitude / CELL).astype("int32")
    df["ilon"] = np.floor(df.longitude / CELL).astype("int32")
    df["ym"] = (df.acq_date.str[:4].astype(int) * 12 + df.acq_date.str[5:7].astype(int) - 1).astype("int32")
    return df, static


def modis_stats(df):
    """One row per cell-month with everything the model reads from MODIS."""
    aqua = (df.satellite == "Aqua") | (df.satellite == "A")
    day = df.daynight == "D"
    df = df.assign(
        nT=(~aqua).astype("int32"),
        nAd=(aqua & day).astype("int32"),
        nAn=(aqua & ~day).astype("int32"),
        nTd=(~aqua & day).astype("int32"),
        nTn=(~aqua & ~day).astype("int32"),
        day=day.astype("int32"),
        area=df.scan * df.track,
        conf=pd.to_numeric(df.confidence, errors="coerce").fillna(0.0),
        weak=(df.frp < 10).astype("int32"),
        pix=(df.latitude * 100).round().astype("int64") * 100000
        + (df.longitude * 100).round().astype("int64"),
    )
    # Terra-only versions, for the months before Aqua (July 2002) and the Terra-only model
    terra = (~aqua).astype(float)
    df = df.assign(
        t_frp=df.frp * terra, t_area=df.area * terra, t_conf=df.conf * terra, t_weak=df.weak * terra
    )
    g = df.groupby(CELL_MONTH)
    out = g.agg(
        n=("frp", "size"),
        nT=("nT", "sum"),
        nAd=("nAd", "sum"),
        nAn=("nAn", "sum"),
        nTd=("nTd", "sum"),
        nTn=("nTn", "sum"),
        frp_sum=("frp", "sum"),
        frp_max=("frp", "max"),
        day_sum=("day", "sum"),
        area_sum=("area", "sum"),
        bright_sum=("brightness", "sum"),
        conf_sum=("conf", "sum"),
        weak_sum=("weak", "sum"),
        ndays=("acq_date", "nunique"),
        npix=("pix", "nunique"),
        frp50=("frp", "median"),
        t_frp_sum=("t_frp", "sum"),
        t_frp_max=("t_frp", "max"),
        t_area_sum=("t_area", "sum"),
        t_conf_sum=("t_conf", "sum"),
        t_weak_sum=("t_weak", "sum"),
    )
    out["frp90"] = g.frp.quantile(0.9)
    out["maxday"] = df.groupby(CELL_MONTH + ["acq_date"]).size().groupby(CELL_MONTH).max()
    return out.reset_index()


def read_csv(f):
    return pd.read_csv(
        f, usecols=lambda c: c in USE, dtype={"confidence": str, "acq_time": str}, low_memory=False
    )


def read_zip(path):
    """Yield (country, detections) for each country's CSV in a yearly archive."""
    z = zipfile.ZipFile(path)
    for info in z.infolist():
        if not info.filename.endswith(".csv"):
            continue
        df = read_csv(z.open(info))
        if len(df):
            country = re.sub(r"^.*?_\d{4}_", "", Path(info.filename).stem).replace("_", " ")
            yield country, df


def rows_intact(text):
    """Every line has the header's number of fields (no row cut or glued)."""
    k = text.split("\n", 1)[0].count(",")
    return all(line.count(",") == k for line in text.rstrip("\n").split("\n"))


def api_frames(name, size, mask):
    """2026 from the API cache, product by product -> ([(None, fires, other sources)], the mask test on the typed months)."""
    out, check = [], {}
    for prod, a, b in API_2026[name]:
        files = sorted((DATA / "api_cache").glob(f"{prod}_*.csv"))
        # every 5-day file from a to the product's end (or today) must be there
        last = min(pd.Timestamp(b), pd.Timestamp.now(tz="UTC").tz_localize(None).normalize())
        want = {
            f"{prod}_{d.date()}.csv"
            for d in pd.date_range(ORIGIN.get(prod, a), last, freq="5D")
            if d + pd.Timedelta(days=4) >= pd.Timestamp(a)
        }
        missing = want - {f.name for f in files}
        if missing:
            raise NotReady(f"{len(missing)} {prod} files still to download")
        parts = []
        for f in files:
            if f.name not in want:
                continue
            text = f.read_text()
            assert rows_intact(text), f"{f.name}: a row is cut or glued; run download_api.py world again"
            parts.append(read_csv(io.StringIO(text)))
        df = pd.concat(parts, ignore_index=True)
        df = df[(df.acq_date >= a) & (df.acq_date <= b)]
        if "type" in df:  # typed months: test the mask on them, then add their own flagged spots to it
            check[prod] = mask_check(df, size, mask)
            fires, static = clean(df, size, mask)
            mask = np.union1d(mask, grow(static.spot.values))
        else:
            day = df.acq_date.max()
            if int(df.acq_time[df.acq_date == day].astype(int).max()) < 2100:
                df = df[df.acq_date < day]  # the last day is still arriving: whole UTC days only
            fires, static = clean(df, size, mask)
        out.append((None, fires, static))
    return out, check


def build(job):
    """Write the tables of one sensor and year; returns a log line."""
    name, src, mask = job
    out = CELLS / f"{name}.parquet"
    modis = name.startswith("modis")
    size = SPOT["modis" if modis else "viirs"]
    if out.exists():
        return f"skip {name}"
    CELLS.mkdir(parents=True, exist_ok=True)
    check = {}
    try:
        if src is None:
            frames, check = api_frames(name, size, mask)
        else:
            frames = ((country, *clean(df, size, mask)) for country, df in read_zip(src))
        modis_rows, viirs_cells, by_country, daily, statics = [], [], [], [], []
        for country, fires, other_sources in frames:
            sat = np.where(fires.satellite.isin(["Aqua", "A"]), "A", "T") if modis else "V"
            per_day = fires.assign(sat=sat).groupby(["acq_date", "sat", "daynight"]).size()
            daily.append(per_day.rename("n").reset_index())
            statics.append(other_sources)
            if modis:
                modis_rows.append(fires.assign(country=country))
            else:
                # npix: distinct spots, to tell lava from fire
                by_spot = fires.assign(spot=spot(fires, size)).groupby(CELL_MONTH)
                per_cell = by_spot.agg(n=("spot", "size"), npix=("spot", "nunique")).reset_index()
                viirs_cells.append(per_cell)
                if country:
                    per_country = per_cell.groupby(["ilat", "ilon"]).n.sum().reset_index()
                    by_country.append(per_country.assign(country=country))
    except zipfile.BadZipFile:
        return f"NOT READY {name}"
    except NotReady as e:
        return f"NOT READY {name} ({e})"
    if modis:
        df = pd.concat(modis_rows, ignore_index=True)
        cells = modis_stats(df)
        countries = None
        if src:
            countries = df.groupby(["country", "ilat", "ilon"], dropna=True).size().rename("n").reset_index()
    else:
        # border cells come from two countries
        cells = (
            pd.concat(viirs_cells, ignore_index=True).groupby(CELL_MONTH)[["n", "npix"]].sum().reset_index()
        )
        countries = pd.concat(by_country, ignore_index=True) if by_country else None
    if countries is not None:
        countries.to_parquet(CELLS / f"{name}_countries.parquet")
    daily = pd.concat(daily, ignore_index=True).groupby(["acq_date", "sat", "daynight"]).n.sum()
    daily.reset_index().to_parquet(CELLS / f"{name}_daily.parquet")
    static = pd.concat(statics, ignore_index=True).groupby(["spot", "type"]).n.sum().reset_index()
    static.to_parquet(CELLS / f"{name}_static.parquet")
    if check:
        (CELLS / f"mask_check_{name}.json").write_text(json.dumps(check, indent=1))
    cells.to_parquet(out)
    return (
        f"{name}: {int(cells.n.sum()):,} hotspots, {len(cells):,} cell-months; other heat sources set aside: {int(static.n.sum()):,}"
        + (f"; mask test {check}" if check else "")
    )


def picked(jobs):
    """The jobs whose name contains one of the command-line filters (all of them without filters)."""
    return [j for j in jobs if len(sys.argv) < 2 or any(a in j[0] for a in sys.argv[1:])]


if __name__ == "__main__":
    archives = [
        (z.stem.replace("_all_countries", ""), str(z), np.zeros(0, np.int64))
        for z in sorted((DATA / "zips").glob("*.zip"))
    ]
    with Pool(6) as pool:
        for msg in pool.imap_unordered(build, picked(archives)):
            print(msg, flush=True)
        # 2026 last: its near-real-time months need the place mask the archive years have just written
        api = [(n, None, mask_for("modis" if n.startswith("modis") else "viirs")) for n in API_2026]
        for msg in pool.imap_unordered(build, picked(api)):
            print(msg, flush=True)
