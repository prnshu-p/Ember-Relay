"""The write-up's figure: hotspots per year for the world and seven countries, from the app's data.
-> demo/record.png. Run: python3 pipeline/figure.py"""

import json

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import APP_DATA, ROOT, month_index  # noqa: E402

index = json.loads((APP_DATA / "index.json").read_text())
months = index["months"]
countries = {c["name"]: c for c in json.loads((APP_DATA / "countries.json").read_text())}
RANGES = index["world"]["ranges"]
year = np.array([int(m[:4]) for m in months])
estimated = np.array([m < "2012-02" for m in months])
overlap = np.array(["2012-02" <= m < "2026-01" for m in months])
YEARS = np.arange(2001, 2026)
SHOW = [
    "World",
    "Brazil",
    "Democratic Republic of the Congo",
    "Australia",
    "Canada",
    "Russian Federation",
    "United States",
    "Indonesia",
]


def ranges(h, blind):
    """The app's range rule (rangesFor in world.js), for the estimated months."""
    use = overlap & (blind > 0)
    lb = np.log1p(blind[use])
    lr = np.log1p(h[use]) - lb
    lo, hi = h.copy(), h.copy()
    for t in np.nonzero(estimated)[0]:
        le = np.log1p(h[t])
        dist = abs(lb - le)
        o = np.argsort(dist)[:48]
        near = o[dist[o] <= np.log(5)]
        if len(near) < 12:
            near = o[:12]
        a, b = np.quantile(lr[near], RANGES["quantiles"])
        w = RANGES["terra_factor"] if months[t] < "2002-07" else 1.0
        widen = (
            RANGES["delta0"]
            + RANGES["slope_per_year"] * (month_index("2012-02") - month_index(months[t])) / 12
        )
        lo[t] = np.expm1(le + w * min(a, 0) - widen)
        hi[t] = np.expm1(le + w * max(b, 0) + widen)
    return lo, hi


def per_year(a):
    """Monthly values -> millions per year."""
    return np.array([a[year == y].sum() for y in YEARS]) / 1e6


fig, axs = plt.subplots(2, 4, figsize=(15, 7.2))
for ax, name in zip(axs.flat, SHOW):
    c = countries[name]
    h, m, bl = (np.array(c[k], float) for k in ("h", "modis", "blind"))
    lo, hi = ranges(h, bl)
    raw = np.where(estimated, m, h)
    early = YEARS <= 2011
    ax.fill_between(
        YEARS[early],
        per_year(lo)[early],
        per_year(hi)[early],
        color="#d9480f",
        alpha=0.15,
        lw=0,
        label="Range of the estimates (monthly ranges added up)",
    )
    ax.plot(
        YEARS, per_year(raw), "--", color="#9a978c", lw=1.6, label="Raw sensors joined (MODIS, then VIIRS)"
    )
    tested = YEARS >= 2013
    ax.plot(
        YEARS[tested],
        per_year(bl)[tested],
        color="#1f6fb2",
        lw=1.8,
        label="Model with VIIRS hidden (blind test)",
    )
    ax.plot(YEARS, per_year(h), color="#d9480f", lw=2.2, label="Harmonized record")
    ax.axvline(2011.6, color="#bbb", lw=0.8)
    ax.set_title(
        name.replace("Democratic Republic of the Congo", "DR Congo").replace("Russian Federation", "Russia"),
        fontsize=12,
        loc="left",
        fontweight="bold",
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("million hotspots / year", fontsize=8, color="#555")
handles, labels = axs.flat[0].get_legend_handles_labels()
fig.legend(
    handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.035)
)
fig.suptitle(
    "One consistent fire record for the whole planet: the 2012 jump is the change of sensor, not more fire",
    fontsize=14,
    x=0.01,
    ha="left",
)
fig.text(
    0.01,
    0.008,
    "Data: NASA FIRMS (MODIS Collection 6.1; VIIRS 375 m on Suomi NPP and NOAA-20). Harmonized planetary time series record.",
    fontsize=8,
    color="#777",
)
fig.tight_layout(rect=(0, 0.07, 1, 1))
out = ROOT / "demo" / "record.png"
fig.savefig(out, dpi=110)
print("saved", out)
