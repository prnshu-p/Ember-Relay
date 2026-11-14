"""Download from the FIRMS API into data/global/api_cache/: `world` fetches 2026 for the whole planet (the yearly
archives end in 2025), `extra` the products used only to test the record (E13-E15).
Run: FIRMS_MAP_KEY=... python3 pipeline/download_api.py world [reverse] | extra"""

import datetime as dt
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import DATA

KEY = os.environ["FIRMS_MAP_KEY"]  # never written to disk
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
CACHE = DATA / "api_cache"
TODAY = dt.datetime.now(dt.timezone.utc).date()  # the API's dates are UTC
# (product, first day, last day): science data where it exists, near-real-time after. VIIRS first, MODIS last.
WORLD = [
    ("VIIRS_NOAA20_SP", "2026-01-01", "2026-07-31"),
    ("VIIRS_NOAA20_NRT", "2026-08-01", str(TODAY)),
    ("VIIRS_SNPP_SP", "2026-01-01", "2026-07-31"),
    ("VIIRS_SNPP_NRT", "2026-08-01", "2026-11-02"),
    ("MODIS_SP", "2026-01-01", "2026-08-31"),
    ("MODIS_NRT", "2026-09-01", str(TODAY)),
]


def whole(text):
    """A complete answer: starts with the header and every line has the header's number of fields (a cut or glued row has not)."""
    k = text.split("\n", 1)[0].count(",")
    return text.startswith("latitude") and all(line.count(",") == k for line in text.rstrip("\n").split("\n"))


def chunk(bbox, prod, day, span=5):
    cache = CACHE / f"{prod}_{day}.csv"
    # Reuse a file only if it is intact and was written after its window closed (plus 6 hours for late data).
    closed = dt.datetime.combine(
        dt.date.fromisoformat(day) + dt.timedelta(span), dt.time(6), dt.timezone.utc
    ).timestamp()
    if cache.exists() and cache.stat().st_mtime >= closed and whole(cache.read_text()):
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)

    def get(n, d):
        for i in range(40):
            r = subprocess.run(
                ["curl", "-sS", "--max-time", "600", f"{API}/{KEY}/{prod}/{bbox}/{n}/{d}"],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and whole(r.stdout):
                return r.stdout
            # Over 5,000 transactions per 10 minutes the API answers "Invalid MAP_KEY": wait for the window to move on.
            limited = "transaction" in r.stdout.lower() or "invalid map_key" in r.stdout.lower()
            if n == 5 and i == 1 and not limited:
                return None  # a big area in fire season: the 5-day call times out, use 1-day calls
            time.sleep(90 if limited else 30 * min(i + 1, 4))
        raise RuntimeError(f"failed {bbox} {prod} {d}: {r.stdout[:120]} {r.stderr[:120]}")

    text = get(span, day) if span == 1 else get(5, day)
    if text is None:
        parts = [get(1, str(dt.date.fromisoformat(day) + dt.timedelta(i))) for i in range(5)]
        # Answers end without a newline, so the days are joined with one; a day with no fires is a bare header.
        bodies = [b for p in parts[1:] if (b := p.partition("\n")[2].rstrip("\n"))]
        text = "\n".join([parts[0].rstrip("\n")] + bodies) + "\n"
        assert whole(text), (prod, day)
    tmp = cache.with_suffix(f".{os.getpid()}.part")
    tmp.write_text(text)
    tmp.replace(cache)  # atomic: two downloaders can share a cache
    return cache


def days(a, b):
    """The first day of each 5-day window from a to b."""
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [str(a + dt.timedelta(i)) for i in range(0, (b - a).days + 1, 5)]


def fetch_all(label, jobs):
    """jobs: chunk() arguments, three at a time."""
    with ThreadPoolExecutor(3) as ex:
        for i, _ in enumerate(ex.map(lambda job: chunk(*job), jobs)):
            if i % 20 == 0:
                print(f"{label}: {i}/{len(jobs)} chunks", flush=True)
    print(f"{label} done", flush=True)


def run_world():
    jobs = [("world", prod, d) for prod, a, b in WORLD for d in days(a, b)]
    if "reverse" in sys.argv:  # a second downloader working from the other end: S-NPP, then MODIS, backwards
        jobs = [j for j in jobs if "SNPP" in j[1]][::-1] + [j for j in jobs if "MODIS" in j[1]][::-1]
    fetch_all("world 2026", jobs)


def run_extra():
    """Smallest first: GOES (36 days of 2024, the Americas), Landsat (US and Canada), then NOAA-21 (the world)."""
    goes = [str(dt.date(2024, m, d)) for m in range(1, 13) for d in (1, 11, 21)]
    jobs = [("-170,-60,-30,72", "GOES_NRT", d, 1) for d in goes]
    jobs += [("-170,14,-50,84", "LANDSAT_NRT", d, 5) for d in days("2022-06-20", str(TODAY))]
    jobs += [("world", "VIIRS_NOAA21_NRT", d, 5) for d in days("2026-08-01", str(TODAY))]
    jobs += [("world", "VIIRS_NOAA21_SP", d, 5) for d in days("2023-03-01", "2026-07-31")]
    fetch_all("extra", jobs)


if __name__ == "__main__":
    if "extra" in sys.argv:
        run_extra()
    elif "world" in sys.argv:
        run_world()
    else:
        sys.exit(__doc__)
