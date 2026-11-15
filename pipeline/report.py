"""Write docs/RESULTS.md, docs/SUBMISSION.md, docs/SUBMISSION_FORM.md and demo/tokens.json from the run's numbers:
data/global/model/metrics.json, the app's data and, when present, the burned-area check and experiments E13-E15.
Run after stage3_export.py: python3 pipeline/report.py"""

import json

import numpy as np

from common import APP_DATA, MODEL, ROOT

EXPERIMENTS = ROOT / "pipeline" / "experiments"

METHODS = (
    ("one ratio", "One ratio per country"),
    ("seasonal ratio", "Ratio per country and calendar month"),
    ("local ratio", "Ratio per 1° box and calendar month"),
    ("best simple", "Best simple method (local ratio + the cell's usual small fires)"),
    ("model", "Model"),
    ("model averaged", "Model, box totals averaged with the best simple method"),
)
TOKEN_METHODS = (
    ("m", "record"),
    ("s", "seasonal ratio"),
    ("o", "one ratio"),
    ("l", "local ratio"),
    ("b", "best simple"),
)
ACCURACY_TABLES = (
    (
        "forward",
        "Forward: trained on 2012–2018, tested on 2019–2025",
        "MODIS's orbits drift in the test years (Terra from 2020, Aqua from 2022), and every method reads low.",
    ),
    (
        "backward",
        "Backward: trained on 2019–2025, tested on 2012–2018",
        "Trained on the drift years; every method reads high.",
    ),
    (
        "analogue",
        "Analogue of the real task: trained on 2016–2019, tested on 2012–2015",
        "Stable orbits on both sides and backward in time, as when 2000–2011 is estimated from 2012–2019: the closest test to the real task.",
    ),
    (
        "analogue_terra",
        "The same analogue with Terra-only inputs (the model used before July 2002)",
        "The month's inputs come from Terra alone; the simple methods use Terra counts too.",
    ),
)
SATELLITES = (("terra", "Terra"), ("aqua", "Aqua"), ("snpp", "Suomi NPP"), ("noaa20", "NOAA-20"))
GFED_REGIONS = {
    "BONA": "boreal North America",
    "TENA": "temperate North America",
    "CEAM": "Central America",
    "NHSA": "northern South America",
    "SHSA": "southern South America",
    "EURO": "Europe",
    "MIDE": "Middle East",
    "NHAF": "Africa north of the equator",
    "SHAF": "Africa south of the equator",
    "BOAS": "boreal Asia",
    "CEAS": "central Asia",
    "SEAS": "South-East Asia",
    "EQAS": "equatorial Asia",
    "AUST": "Australia and New Zealand",
}


def pc(v, d=1):
    return "–" if v is None else f"{v * 100:.{d}f}%"


def sg(v, d=1):
    """Signed percentage; zero is written without a sign."""
    if v is None:
        return "–"
    if round(v * 100, d) == 0:
        return f"{0:.{d}f}%"
    return f"{v * 100:+.{d}f}%"


def signed_int(v):
    """'+8', '-3' or '0', never '-0'."""
    return "0" if round(v) == 0 else f"{v:+.0f}"


def both_ways(tests, method, score):
    """Mean of the forward and the backward test."""
    return (tests["forward"][method][score] + tests["backward"][method][score]) / 2


def method_row(metrics, method, cells):
    """A table row, in bold when the method is the record."""
    if method == metrics["record_is"]:
        cells = [f"**{c}**" for c in cells]
    return "| " + " | ".join(cells) + " |"


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def header(metrics, idx):
    hotspots = metrics["hotspots"]
    lines = [
        "# Results of the world run",
        "",
        "Written by `pipeline/report.py` from the metrics of `pipeline/stage2_model.py`. Method and discussion: [SUBMISSION.md](SUBMISSION.md); how we got here, including the review that rebuilt the pipeline: [EXPERIMENTS.md](EXPERIMENTS.md).",
        "",
        f"- Grid: **{metrics['cells']:,} cells** of 0.25° (every cell where either sensor ever saw a vegetation fire) × **{metrics['months']} months** from November 2000.",
        f"- Hotspots used: MODIS {hotspots['modis'] / 1e6:.1f} million, VIIRS S-NPP {hotspots['snpp'] / 1e6:.1f} million, VIIRS NOAA-20 {hotspots['noaa20'] / 1e6:.1f} million.",
        "- The record is the row in bold: the model with each 1° box total averaged with the best simple method. Against the model alone that costs a few tenths of a point on world totals "
        f"in these tests and buys continuity where the sources change: the median country step at 2012 is {pc(metrics['seam_countries_median_abs'])} against {pc(metrics['seam_countries_median_abs_model_alone'])} for the model alone (E10).",
        "",
    ]
    tokens = {
        "cells": f"{metrics['cells']:,}",
        "hot_m": f"{sum(hotspots.values()) / 1e6:.0f}",
        "months": str(metrics["months"]),
        "through": idx["through"],
    }
    return lines, tokens


def hidden_years(metrics):
    tests = metrics["tests"]
    lines = [
        "## Accuracy on years hidden from the model",
        "",
        "- **Countries**: for each country, the median error of its monthly totals (months with 20 or more real hotspots; countries with 12 or more such months); then the median over countries.",
        "- **1° boxes**: median error of box-months with 50 or more real hotspots. **Cells**: log-RMSE over 0.25° cell-months where either sensor saw fire. **World**: median error of the world's monthly total.",
        "- Border cells count for each country by its share of the hotspots there. (The two ratios per country are fitted with each cell given to the country that has most of its hotspots, and scored the same way as everything else.) Lower is better.",
        "",
    ]
    for test, title, note in ACCURACY_TABLES:
        lines += [
            f"### {title}",
            "",
            note,
            "",
            "| Method | Countries | 1° boxes | Cells | World total | All hotspots (bias) |",
            "|---|---|---|---|---|---|",
        ]
        for k, label in METHODS:
            r = tests[test][k]
            cells = [label, pc(r["country"]), pc(r["box"]), f"{r['cell']:.3f}", pc(r["world"]), sg(r["bias"])]
            lines.append(method_row(metrics, k, cells))
        lines.append("")

    tokens = {}
    analogue, terra = tests["analogue"], tests["analogue_terra"]
    for p, k in TOKEN_METHODS:
        tokens |= {
            f"{p}_country": pc(both_ways(tests, k, "country")),
            f"{p}_box": pc(both_ways(tests, k, "box")),
            f"{p}_cell": f"{both_ways(tests, k, 'cell'):.2f}",
            f"{p}_wcountry": pc(both_ways(tests, k, "wcountry")),
            f"{p}_wbox": pc(both_ways(tests, k, "wbox")),
            f"an_{p}_country": pc(analogue[k]["country"]),
            f"an_{p}_box": pc(analogue[k]["box"]),
            f"an_{p}_cell": f"{analogue[k]['cell']:.2f}",
            f"an_{p}_bias": sg(analogue[k]["bias"]),
            f"te_{p}_country": pc(terra[k]["country"]),
            f"te_{p}_box": pc(terra[k]["box"]),
            f"te_{p}_cell": f"{terra[k]['cell']:.2f}",
        }
    return lines, tokens


def harder_measures(metrics):
    tests = metrics["tests"]
    lines = [
        "### Harder measures (forward / backward)",
        "",
        "Weighted by fire (sum of absolute errors over sum of real hotspots, every month and area counted, so big fire months dominate), over all cell-months (zeros included), and the worst tenth of months for the world total.",
        "",
        "| Method | Countries, weighted | 1° boxes, weighted | All cells (log-RMSE) | World total, 90th percentile |",
        "|---|---|---|---|---|",
    ]
    for k, label in METHODS:
        f, b = tests["forward"][k], tests["backward"][k]
        cells = [
            label,
            f"{pc(f['wcountry'])} / {pc(b['wcountry'])}",
            f"{pc(f['wbox'])} / {pc(b['wbox'])}",
            f"{f['cell_all']:.3f} / {b['cell_all']:.3f}",
            f"{pc(f['world_p90'])} / {pc(b['world_p90'])}",
        ]
        lines.append(method_row(metrics, k, cells))

    better = metrics["countries_better"]
    bias = {
        test: ", ".join(f"{y} {sg(v)}" for y, v in by_year.items())
        for test, by_year in metrics["bias_by_year"].items()
    }
    lines += [
        "",
        f"- Countries scored in both directions: **{metrics['countries_tested']}**. The record beats one ratio in **{better['one ratio']}**, the ratio per calendar month in **{better['seasonal ratio']}**, "
        f"the ratio per 1° box in **{better['local ratio']}** and the best simple method in **{better['best simple']}**.",
        f"- Bias of the record by test year (all predicted over all real hotspots, less one): analogue {bias['analogue']}; backward {bias['backward']}; forward {bias['forward']}.",
    ]
    tokens = {
        "countries": str(metrics["countries_tested"]),
        "better_o": str(better["one ratio"]),
        "better_s": str(better["seasonal ratio"]),
        "better_l": str(better["local ratio"]),
        "better_b": str(better["best simple"]),
    }
    return lines, tokens


def benchmark(metrics):
    bench = metrics.get("benchmark")
    if not bench:
        return [], {}
    tests = metrics["tests"]
    twin, record = bench["twin"], bench["record"]
    before, after = bench["before_rephasing"], bench["after_rephasing"]

    def simple(score):
        return both_ways(tests, "best simple", score)

    def gap_closed(score):
        return 1 - (record[score] - twin[score]) / (simple(score) - twin[score])

    lines = [
        "",
        "## The twin-sensor benchmark",
        "",
        f"NOAA-20 predicting S-NPP (a VIIRS of the same design in the same orbital plane) with one scale factor, over the {bench['months']} months of 2019–2025 in which neither lost 2% or more of its detections. "
        "It is a measured reference, not a theoretical limit: the two view each cell from different angles and at different times.",
        "",
        "| | Countries | 1° boxes | Cells |",
        "|---|---|---|---|",
        f"| Twin VIIRS sensor | {pc(twin['country'])} | {pc(twin['box'])} | {twin['cell']:.3f} |",
        f"| The record, the same months | {pc(record['country'])} | {pc(record['box'])} | {record['cell']:.3f} |",
        f"| Best simple method (both directions) | {pc(simple('country'))} | {pc(simple('box'))} | {simple('cell'):.3f} |",
        "",
        f"Share of the gap between the best simple method and the twin sensor that the record closes: countries {pc(gap_closed('country'), 0)}, boxes {pc(gap_closed('box'), 0)}, cells {pc(gap_closed('cell'), 0)}.",
        f"Until NOAA-20 was re-phased in March–April 2024 the two were half an orbit (about 50 minutes) apart, afterwards about a quarter orbit: twin error per country {pc(before['twin']['country'])} "
        f"({before['months']} months) before and {pc(after['twin']['country'])} ({after['months']} months) after. The second figure rests on few months, "
        "so only countries with fire in nearly every month are scored: the two are not directly comparable.",
    ]
    tokens = {
        "f_country": pc(twin["country"]),
        "f_box": pc(twin["box"]),
        "f_cell": f"{twin['cell']:.2f}",
        "f_months": str(bench["months"]),
        "fm_country": pc(record["country"]),
        "fm_box": pc(record["box"]),
        "fm_cell": f"{record['cell']:.2f}",
        "gap_country": pc(gap_closed("country"), 0),
        "gap_box": pc(gap_closed("box"), 0),
        "gap_cell": pc(gap_closed("cell"), 0),
        "f_before": pc(before["twin"]["country"]),
        "f_after": pc(after["twin"]["country"]),
    }
    return lines, tokens


def steps(metrics):
    s12, s02 = metrics["steps"]["2012"], metrics["steps"]["2002"]
    seams = abs(np.array([r["seam"] for r in metrics["countries"] if r["seam"] is not None]))
    median = pc(float(np.median(seams)))
    within5 = pc(float((seams < 0.05).mean()), 0)
    within10 = pc(float((seams < 0.10).mean()), 0)
    lines = [
        "",
        "## Steps where the sources change",
        "",
        "Step in (record / yardstick) between the months before a change and the months after, weighted by fire, calendar month by calendar month. Zero means no step. "
        "A fixed ratio passes the 2012 test by construction, so it shows that no fire is lost or invented at the change, not that the conversion is accurate.",
        "",
        "| | At February 2012 (yardstick: MODIS; Jul 2002–Jan 2012 against Feb 2012–2019) | At July 2002 (yardstick: Terra; before Aqua against Jul 2002–Jan 2012) |",
        "|---|---|---|",
        f"| **The record** | **{sg(s12['record'])}** | **{sg(s02['record'])}** |",
        f"| The record before its Terra-only months were bridged to the rest (E11) | | {sg(s02['without the bridge'])} |",
        f"| Model alone (not bridged) | {sg(s12['model alone'])} | {sg(s02['model alone'])} |",
        f"| Best simple method alone (not bridged) | {sg(s12['best simple alone'])} | {sg(s02['best simple alone'])} |",
        f"| Raw sensors joined (MODIS, then VIIRS) | {sg(s12['raw join'], 0)} | |",
        f"| Real VIIRS, first 20 months against the rest (what no step looks like) | | {sg(s02['real VIIRS, same test'])} |",
        "",
        f"- Countries at 2012: median absolute step **{median}**; within ±5%: {within5}; within ±10%: {within10} of {len(seams)}.",
    ]
    tokens = {
        "seam_world": sg(s12["record"]),
        "seam_model": sg(s12["model alone"]),
        "seam_simple": sg(s12["best simple alone"]),
        "raw_join": sg(s12["raw join"], 0),
        "aqua_step": sg(s02["record"]),
        "aqua_real": sg(s02["real VIIRS, same test"]),
        "aqua_simple": sg(s02["best simple alone"]),
        "aqua_nobridge": sg(s02["without the bridge"]),
        "seam_med": median,
        "seam_med_model": pc(metrics["seam_countries_median_abs_model_alone"]),
        "seam5": within5,
        "seam10": within10,
    }
    return lines, tokens


def ranges(metrics):
    r = metrics["ranges"]
    widened, unwidened = r["coverage"], r["coverage_unwidened"]
    widen = f"{(np.exp(r['delta0']) - 1) * 100:.0f}%"
    lines = [
        "",
        "## Are the ranges honest?",
        "",
        f"The app's range of an estimate is the 3rd to 97th percentile of the blind-test errors of similar months in the same area. Learned on one half of 2012–2025 and tested on the other, "
        f"that alone held the real value in {pc(unwidened['country']['inside'], 0)} of country-months ({pc(unwidened['country']['inside_weighted'], 0)} when weighted by fire): too narrow, because the relation between the sensors drifts. "
        f"So every range is widened by ±{widen}, the smallest amount that brings both figures to 90%, plus {r['slope_per_year'] * 100:.1f}% for each year before 2012 "
        f"(the drift of the bias per year in the analogue test, at least 0.5%), and the error part is multiplied by {r['terra_factor']:.2f} before July 2002 (Terra-only against full inputs in the analogue test).",
        "",
        "| Area | Areas tested | Real value inside the range | Weighted by fire | In each area's biggest 10% of months | Before widening |",
        "|---|---|---|---|---|---|",
    ]
    for k, v in widened.items():
        lines.append(
            f"| {k.capitalize()} | {v['areas']:,} | {pc(v['inside'], 0)} | {pc(v['inside_weighted'], 0)} | {pc(v['inside_biggest'], 0)} | {pc(unwidened[k]['inside'], 0)} |"
        )
    tokens = {
        "rng_widen": widen,
        "rng_slope": f"{r['slope_per_year'] * 100:.1f}%",
        "rng_terra": f"{r['terra_factor']:.2f}",
        "rng_country": pc(widened["country"]["inside"], 0),
        "rng_country_w": pc(widened["country"]["inside_weighted"], 0),
        "rng_box2": pc(widened["2 degree box"]["inside"], 0),
        "rng_box05": pc(widened["0.5 degree box"]["inside"], 0),
        "rng_before": pc(unwidened["country"]["inside"], 0),
        "rng_before_w": pc(unwidened["country"]["inside_weighted"], 0),
    }
    return lines, tokens


def fresh_months(metrics):
    fresh = metrics.get("fresh2026")
    if not fresh:
        return [], {}
    other_model = "model averaged" if metrics["record_is"] == "model" else "model"
    better = fresh["countries_better"]
    lines = [
        "",
        "## 2026: months no model was trained on",
        "",
        f"{fresh['months']} whole months of 2026, predicted by the model trained on the latest years (2019–2025). (The outage rule and the place mask were built with 2026 data in hand; no model saw it.) In {fresh['months_all_snpp']} of them the real count is S-NPP alone; in the rest part of it was filled from NOAA-20.",
        "",
        "| | Countries | 1° boxes | Cells | All hotspots (bias) |",
        "|---|---|---|---|---|",
    ]
    for k, label in METHODS:
        if k != other_model:
            r = fresh[k]
            lines.append(
                f"| {label} | {pc(r['country'])} | {pc(r['box'])} | {r['cell']:.3f} | {sg(r['bias'])} |"
            )
    lines += [
        "",
        f"Of {fresh['countries']} countries with enough fire in those months the record beats one ratio in {better['one ratio']}, the ratio per calendar month in {better['seasonal ratio']} "
        f"and the best simple method in {better['best simple']}. Every method reads low, consistent with MODIS seeing a smaller share of the fires than in any training year: by 2026 Terra crossed the equator near 09:00 and Aqua near 15:30.",
    ]
    tokens = {
        "fresh_months": str(fresh["months"]),
        "fresh_m": pc(fresh["record"]["country"]),
        "fresh_o": pc(fresh["one ratio"]["country"]),
        "fresh_s": pc(fresh["seasonal ratio"]["country"]),
        "fresh_b": pc(fresh["best simple"]["country"]),
        "fresh_bias": sg(fresh["record"]["bias"], 0),
        "fresh_countries": str(fresh["countries"]),
        "fresh_better_o": str(better["one ratio"]),
        "fresh_better_s": str(better["seasonal ratio"]),
    }
    return lines, tokens


def final_forward(metrics):
    lines = [
        "",
        "## The final model, forward in time",
        "",
        "The record before 2012 is made by models trained on 2012–2019 only (stable orbits). Run forward over the drift years, which they never saw, they show how fast the conversion ages:",
        "",
        "| Period | Record: countries | Record: bias | Best simple method: countries | Best simple method: bias |",
        "|---|---|---|---|---|",
    ]
    for period, v in metrics["final_forward"].items():
        rec, simple = v["record"], v["best simple"]
        lines.append(
            f"| {period.replace('-', '–')} | {pc(rec['country'])} | {sg(rec['bias'])} | {pc(simple['country'])} | {sg(simple['bias'])} |"
        )
    return lines, {}


def day_span(run):
    """'2019-03-02', '2019-03-02 to 03-05' or '2019-12-30 to 2020-01-02'."""
    start, end = run["from"], run["to"]
    if start == end:
        return start
    return f"{start} to {end[5:] if end[:4] == start[:4] else end}"


def outages(metrics):
    gap_months = metrics["outages"]["months"]
    runs = metrics["outages"]["runs"]
    noaa20 = metrics["noaa20"]
    lines = [
        "",
        "## Outages found and put right",
        "",
        f"From the world's detections per day and satellite ({len(runs)} runs of lost days). A day is lost when it brings under half of what the partner sensor and the days around it lead to expect. "
        "Whole days and days at least four fifths lost:",
        "",
    ]
    for sat, name in SATELLITES:
        big = [r for r in runs if r["satellite"] == sat and (r["from"] != r["to"] or r["lost"] >= 0.8)]
        lines.append(f"- **{name}**: " + "; ".join(day_span(r) for r in big) + ".")

    modis = ("terra", "aqua")
    modis_months = []
    for month, lost in gap_months.items():
        if any(lost.get(s, 0) >= 0.05 for s in modis):
            shares = " and ".join(f"{s.capitalize()} {pc(lost[s], 0)}" for s in modis if s in lost)
            modis_months.append(f"{month} ({shares})")
    filled = ", ".join(f"{k} ({pc(v, 0)})" for k, v in noaa20["filled"].items())
    lines += [
        "",
        f"- MODIS months that lost 5% or more of a satellite (its counts are scaled up by the lost share): {', '.join(modis_months)}.",
        f"- Months in which 3% or more of the VIIRS count comes from NOAA-20 (S-NPP's lost share, scaled per 10° tile by the S-NPP/NOAA-20 ratio of the 24 healthy months before): {filled}.",
        f"- S-NPP / NOAA-20 of world monthly totals over {noaa20['healthy_months']} healthy months: median {noaa20['usual_monthly_ratio']:.3f}; first year {noaa20['ratio_first_year']:.3f}, last year {noaa20['ratio_last_year']:.3f}.",
        "- Suomi NPP data ended on 2 November 2026; the record is NOAA-20 from November 2026.",
    ]
    tokens = {
        "n_filled": str(len(noaa20["filled"])),
        "n_gap_months": str(len(gap_months)),
        "n_runs": str(len(runs)),
    }
    return lines, tokens


def persistent_sources(metrics):
    p = metrics["persistent_sources"]
    lines = [
        "",
        "## What is left out",
        "",
        f"- **Persistent heat sources**: {p['cells']} cells ({p['next_to_volcano']} next to a volcano FIRMS flags) where the same spots are detected over and over: lava, and gas flares or industry that the fire-type flag missed. "
        f"They held {p['modis'] / 1e3:,.0f} thousand MODIS, {p['snpp'] / 1e3:,.0f} thousand S-NPP and {p['noaa20'] / 1e3:,.0f} thousand NOAA-20 detections.",
    ]
    tokens = {
        "p_cells": str(p["cells"]),
        "p_volcano": str(p["next_to_volcano"]),
        "p_viirs_k": f"{p['snpp'] / 1e3:,.0f}",
    }
    return lines, tokens


def mask_check(metrics):
    check = metrics.get("mask_check", {})
    if not check:
        return [], {}
    v, m = check.get("VIIRS_SNPP_SP"), check.get("MODIS_SP")
    lines = [
        f"- **Other heat sources in near-real-time months** (no fire-type flag): removed by place. Tested on the typed months of 2026: the mask removes {pc(v['other_sources_removed'], 0)} of S-NPP's other sources and {pc(v['fires_removed'], 1)} of its fires, "
        f"leaving a net error of {sg(v['net_error_with_mask'])} where no mask would leave {sg(v['excess_without_mask'])}; for MODIS {pc(m['other_sources_removed'], 0)} and {pc(m['fires_removed'], 1)}, net {sg(m['net_error_with_mask'])} against {sg(m['excess_without_mask'])}."
    ]
    tokens = {
        "mask_removed_modis": pc(m["other_sources_removed"], 0),
        "mask_removed": pc(v["other_sources_removed"], 0),
        "mask_fires": pc(v["fires_removed"], 1),
        "mask_before": sg(v["excess_without_mask"], 0),
        "mask_after": sg(v["net_error_with_mask"]),
    }
    return lines, tokens


def top_countries(metrics):
    rows = sorted(
        [r for r in metrics["countries"] if r["record"] is not None], key=lambda r: -r["viirs_hotspots"]
    )
    lines = [
        "",
        "## The 25 countries with most fire",
        "",
        "| Country | VIIRS hotspots 2012–2025 | VIIRS / MODIS | Record | Best simple method | Ratio per calendar month | One ratio | Step at 2012 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows[:25]:
        seam = "–" if r["seam"] is None else sg(r["seam"])
        lines.append(
            f"| {r['country']} | {r['viirs_hotspots'] / 1e6:.1f} M | {r['ratio']:.1f} | {pc(r['record'])} | {pc(r['best_simple'])} | {pc(r['seasonal_ratio'])} | {pc(r['one_ratio'])} | {seam} |"
        )
    ratios = np.array([r["ratio"] for r in metrics["countries"]])
    tokens = {
        "ratio_lo": f"{np.percentile(ratios, 5):.1f}",
        "ratio_hi": f"{np.percentile(ratios, 95):.1f}",
    }
    return lines, tokens


def theil_sen(months, series, y0, y1):
    """Trend of the yearly totals of whole years y0-y1, per decade and relative to their median, with its 95% interval."""
    by_year = {}
    for m, v in zip(months, series):
        by_year.setdefault(int(m[:4]), []).append(v)
    points = [(y, sum(v)) for y, v in sorted(by_year.items()) if len(v) == 12 and y0 <= y <= y1]
    slopes = np.sort([(b[1] - a[1]) / (b[0] - a[0]) for i, a in enumerate(points) for b in points[i + 1 :]])
    n = len(points)
    c = 1.96 * np.sqrt(n * (n - 1) * (2 * n + 5) / 18)
    lo = slopes[int(max(0, np.floor((len(slopes) - c) / 2)))]
    hi = slopes[int(min(len(slopes) - 1, np.ceil((len(slopes) + c) / 2)))]
    median = np.median([total for _, total in points])
    return np.median(slopes) * 10 / median, lo * 10 / median, hi * 10 / median


def world_trend(idx, world):
    months = idx["months"]
    last = max(int(m[:4]) for m in months) - 1
    record = theil_sen(months, world["h"], 2003, last)
    record19 = theil_sen(months, world["h"], 2003, 2019)
    modis19 = theil_sen(months, world["modis"], 2003, 2019)
    lines = [
        "",
        "## The world's trend",
        "",
        f"- Harmonized record, 2003–{last}: **{sg(record[0], 0)} per decade** (Theil–Sen, 95% interval {sg(record[1], 0)} to {sg(record[2], 0)}). The level of the estimated years carries a further systematic uncertainty of a few percent, which moves this by about ±2 points.",
        f"- 2003–2019, where MODIS is self-consistent: harmonized {sg(record19[0], 1)}, MODIS alone {sg(modis19[0], 1)} per decade. Before 2012 the record's trend comes from MODIS; it is not independent evidence.",
    ]
    tokens = {
        "world_trend": sg(record[0], 0),
        "world_trend_lo": sg(record[1], 0),
        "world_trend_hi": sg(record[2], 0),
        "trend19_h": sg(record19[0], 1),
        "trend19_m": sg(modis19[0], 1),
        "trend_to": str(last),
    }
    return lines, tokens


def step(unit, series):
    """'+8% [+4, +13]': a step of burned_area.py, with its 95% interval."""
    d = unit["level"][series]
    return f"{signed_int(d['step_pct'])}% [{signed_int(d['ci95'][0])}, {signed_int(d['ci95'][1])}]"


def step_words(unit, series, ci=True):
    """'8% [4, 13] below': how far the estimated years sit from the VIIRS years, in hotspots per km² burned."""
    v, (a, b) = unit["level"][series]["step_pct"], unit["level"][series]["ci95"]
    lo, hi = sorted((abs(a), abs(b)))
    interval = f" [{lo:.0f}, {hi:.0f}]" if ci and a * b > 0 else ""
    return f"{abs(v):.0f}%{interval} {'below' if v < 0 else 'above'}"


def burned_area():
    check = read_json(MODEL / "burned_area_check.json")
    if check is None:
        return [], {}
    cci = check["products"]["FireCCI51"]
    units, gfed_units = cci["units"], check["products"]["GFED5"]["units"]
    years = cci["periods"]
    pooled = cci["regions_pooled_variability_r"]
    cross = check["cross_check"]
    regions = [k for k, v in units.items() if v["kind"] in ("world", "region")]
    fails = [
        k
        for k in regions
        if cross[k]["trusted"] and cross[k]["FireCCI51"] == "FAIL" and cross[k]["GFED5"] == "FAIL"
    ]
    world, boas = units["World"], units["BOAS"]

    lines = [
        "",
        "## Independent check: burned area",
        "",
        f"Burned area is mapped from the change in surface reflectance after a fire, by one sensor family that flew unchanged across 2012. If the record is consistent, hotspots per km² burned must not step there. "
        f"Step = estimated years ({years[0]}–{years[1]}) over VIIRS years ({years[2]}–{years[3]}), less one; 95% interval from resampling years. Primary product: ESA FireCCI51; GFED5 as a second opinion "
        "(up to half of its area is itself derived from MODIS hotspots, so it is lenient). The MODIS column is a control: it shows how much the yardstick itself moves for a single sensor. "
        "Burned-area products miss most small, cropland and deforestation fires, so regions where FireCCI51 maps under half of GFED5's area are marked weak. Script: `pipeline/burned_area.py`.",
        "",
        "| Region | Record | Raw sensors joined | MODIS alone (control) | Record over control | Record, GFED5 | Yardstick |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in regions:
        u = units[k]
        if "H_vs_modis" in u["level"]:
            name = "**World**" if k == "World" else GFED_REGIONS.get(k, k)
            own = signed_int(u["level"]["H_vs_modis"]["step_pct"])
            yardstick = "trusted" if cross[k]["trusted"] else "weak"
            lines.append(
                f"| {name} | {step(u, 'H')} | {step(u, 'raw')} | {step(u, 'modis')} | {own}% | {step(gfed_units[k], 'H')} | {yardstick} |"
            )
    lines += [
        "",
        f"- Year-to-year agreement with burned area, pooled over the 14 regions (r): record {pooled['H']['pre']:.2f} in the estimated years and {pooled['H']['post']:.2f} in the VIIRS years; MODIS alone {pooled['modis']['pre']:.2f} and {pooled['modis']['post']:.2f}. "
        "Partly built in before 2012, since the estimates and both products descend from MODIS observations.",
        "- Fails in both products where the yardstick is trusted: "
        + (", ".join(GFED_REGIONS.get(k, k) for k in fails) if fails else "nowhere")
        + ".",
        "- What this can show: that the false step of the raw join is gone and the estimated years sit within about 10% of the VIIRS level. What it cannot: accuracy finer than that, anything per cell or month, or the Terra-only years 2000–2002.",
    ]
    tokens = {
        "ba_h_words": step_words(world, "H"),
        "ba_raw_words": step_words(world, "raw", False),
        "ba_modis_words": step_words(world, "modis", False),
        "ba_gfed_words": step_words(gfed_units["World"], "H", False),
        "ba_boas_words": step_words(boas, "H", False),
        "ba_boas_own_words": f"{abs(boas['level']['H_vs_modis']['step_pct']):.0f} points",
        "ba_h": step(world, "H"),
        "ba_raw": f"{world['level']['raw']['step_pct']:+.0f}%",
        "ba_modis": f"{world['level']['modis']['step_pct']:+.0f}%",
        "ba_gfed": step(gfed_units["World"], "H"),
        "ba_boas": f"{boas['level']['H']['step_pct']:+.0f}%",
        "ba_boas_own": f"{boas['level']['H_vs_modis']['step_pct']:+.0f}%",
        "ba_fails": " and ".join(GFED_REGIONS.get(k, k) for k in fails) if fails else "no region",
        "ba_r_pre": f"{pooled['H']['pre']:.2f}",
        "ba_r_post": f"{pooled['H']['post']:.2f}",
    }
    return lines, tokens


def third_viirs(e13):
    pairs, blind, hat = e13["pairs"], e13["record_blind"], e13["three_cornered_hat"]
    healthy, outage_runs, fills, handover = (
        e13["healthy_months"],
        e13["outage_days"],
        e13["fills"],
        e13["handover"],
    )
    n21_normal = sum(not r["noaa21_lost_any_day"] for r in outage_runs)
    confirmed = sum(r["detected_here_too"] for r in outage_runs)
    lines = [
        "",
        "### A third VIIRS: NOAA-21 (E13)",
        "",
        f"{len(healthy)} months ({healthy[0]} to {healthy[-1]}) in which none of Suomi NPP, NOAA-20 and NOAA-21 lost a day; scored like the record.",
        "",
        "| Predictor (one scale factor) | Countries | 1° boxes | Cells | Countries, weighted by fire | World total |",
        "|---|---|---|---|---|---|",
    ]
    for name, r in pairs.items():
        lines.append(
            f"| {name} | {pc(r['country'])} | {pc(r['box'])} | {r['cell']:.3f} | {pc(r['wcountry'])} | {pc(r['world'])} |"
        )
    own_sd = ", ".join(f"{k} {v:.3f}" for k, v in hat["own_sd"].items())
    lines += [
        f"| **The record's blind test (from MODIS)** | **{pc(blind['country'])}** | **{pc(blind['box'])}** | **{blind['cell']:.3f}** | **{pc(blind['wcountry'])}** | **{pc(blind['world'])}** |",
        "",
        f"- Three-cornered hat on {hat['box_months']:,} 1° box-months with 50 or more hotspots in all three (standard deviation of log counts, scale differences removed): {own_sd} of their own; the record against S-NPP {hat['record_vs_snpp_sd']:.3f}, or {hat['record_own_sd']:.3f} once S-NPP's own part is taken out.",
    ]
    if e13.get("rephasing"):
        periods = []
        for period, v in e13["rephasing"].items():
            errors = ", ".join(f"{k} {pc(x)}" for k, x in v.items() if k != "months")
            periods.append(f"{period} ({v['months']} months): {errors}")
        lines.append(
            "- 1° box error by period, before and after NOAA-20 was re-phased: " + "; ".join(periods) + "."
        )
    lines.append(
        f"- Outage runs of S-NPP or NOAA-20 since March 2023: {len(outage_runs)}; NOAA-21 was normal on all their days in {n21_normal}, and the three-sensor test confirms the loss in {confirmed}. "
        f"NOAA-21 lost {len(e13['noaa21_lost_days'])} days of its own."
    )
    if fills:
        refills = ", ".join(
            f"{r['month']} {sg(r['world_difference'])} / {pc(r['tile_median_abs_difference'])}" for r in fills
        )
        lines.append(
            f"- The months filled from NOAA-20, refilled from NOAA-21 instead (difference, world / median 10° tile): {refills}."
        )
    lines.append(
        f"- November 2026, the record (NOAA-20 alone) against NOAA-21 scaled to S-NPP: world {sg(handover['world_difference'])}, median 10° tile {pc(handover['tile_median_abs_difference'])}."
    )
    tokens = {
        "n21_months": str(len(healthy)),
        "n21_box": pc(pairs["NOAA-21 -> S-NPP"]["box"]),
        "n20_box": pc(pairs["NOAA-20 -> S-NPP"]["box"]),
        "n2_box": pc(pairs["average of NOAA-20 and NOAA-21 -> S-NPP"]["box"]),
        "n21_rec_box": pc(blind["box"]),
        "n21_country": pc(pairs["NOAA-21 -> S-NPP"]["country"]),
        "n20_country": pc(pairs["NOAA-20 -> S-NPP"]["country"]),
        "n21_rec_country": pc(blind["country"]),
        "th_snpp": f"{hat['own_sd']['S-NPP']:.2f}",
        "th_n20": f"{hat['own_sd']['NOAA-20']:.2f}",
        "th_n21": f"{hat['own_sd']['NOAA-21']:.2f}",
        "th_rec": f"{hat['record_own_sd']:.2f}",
        "n21_outages_ok": f"{n21_normal} of {len(outage_runs)}",
        "n21_fill_world": ("at most " + pc(max(abs(r["world_difference"]) for r in fills))) if fills else "–",
        "n21_handover": sg(handover["world_difference"]),
    }
    return lines, tokens


def landsat(e14):
    per_landsat = e14["record_per_landsat"]
    rho = ", ".join(f"{n} {v:.2f}" for n, v in e14["country_month_spearman"].items())
    by_year = ", ".join(f"{y} {v:.2f}" for y, v in per_landsat.items())
    lines = [
        "",
        "### Landsat 8 and 9: fire in 30 m pixels, US and Canada south of 50°N (E14)",
        "",
        "FIRMS's Landsat data stops at 65°N and is sparse north of 50°N, so the test uses the area where it looks: there it has seen fire in cells holding 98% of the record's.",
        "",
        f"- Where Landsat saw two or more fire pixels in a cell-month ({e14['landsat_fire_cell_months']:,}), the record has fire in {pc(e14['record_has_fire_there'], 0)}; where the record has 10 or more hotspots ({e14['record_fire_cell_months']:,}), "
        f"Landsat saw fire in {pc(e14['landsat_saw_fire_there'], 0)} ({pc(e14['landsat_saw_fire_where_record_100'], 0)} where it has 100 or more): Landsat looks once every 8 days or so, by day.",
        f"- Rank correlation of monthly totals: 1° box-months {e14['box_month_spearman']:.2f}; {rho}.",
        f"- Record hotspots per Landsat fire pixel, August to October: {by_year} (2026: near-real-time data, cleaned by place).",
    ]
    tokens = {
        "ls_where100": pc(e14["landsat_saw_fire_where_record_100"], 0),
        "ls_where": pc(e14["record_has_fire_there"], 0),
        "ls_rho": f"{e14['box_month_spearman']:.2f}",
        "ls_2026": f"{per_landsat['2026']:.2f}",
        "ls_before": ", ".join(f"{per_landsat[y]:.2f}" for y in ("2023", "2024", "2025")),
    }
    return lines, tokens


def clock(hours):
    """13.5 -> '13:30'."""
    return f"{int(hours)}:{round(hours % 1 * 60):02d}"


def usual_hour(c):
    """Mean observing hour of 2013-2019 of one satellite's day or night passes."""
    return np.mean([h for y, h in zip(c["years"], c["hour"]) if 2013 <= y <= 2019])


def goes_drift(e15):
    if "comparison" not in e15:
        return [], {}
    passes = {(c["satellite"], c["daynight"]): c for c in e15["comparison"]}
    terra_day, aqua_day, terra_night = passes[("Terra", "D")], passes[("Aqua", "D")], passes[("Terra", "N")]
    total = e15["modis_total"][-1]
    lines = [
        "",
        "### GOES: the daily cycle of fire, and the drift of the MODIS orbits (E15)",
        "",
        f"Tropical South America. The local hour at which each satellite observed fires, read from its detections; the daily cycle of fire from {e15['diurnal']['detections']:,} GOES-16 detections on {e15['diurnal']['files']} days of 2024.",
        "",
        "| | Observing hour 2013–2019 | Observing hour 2026 | Count per S-NPP hotspot in 2026 (2013–2019 = 1): observed | predicted from the daily cycle | Correlation over 2012–2026 |",
        "|---|---|---|---|---|---|",
    ]
    for c, name in ((terra_day, "Terra, day"), (terra_night, "Terra, night"), (aqua_day, "Aqua, day")):
        observed, predicted = c["shift_2026"]
        lines.append(
            f"| {name} | {clock(usual_hour(c))} | {clock(c['hour'][-1])} | {1 + observed:.2f} | {1 + predicted:.2f} | {c['r_all_years']:.2f} |"
        )
    lines += [
        "",
        f"- All of MODIS in this region per S-NPP hotspot in 2026: observed {total['obs']:.2f}, predicted {total['pred']:.2f}: the two satellites' changes largely cancel here.",
    ]
    tokens = {
        "dr_terra_from": clock(usual_hour(terra_day)),
        "dr_terra_to": clock(terra_day["hour"][-1]),
        "dr_aqua_to": clock(aqua_day["hour"][-1]),
        "dr_aqua_from": clock(usual_hour(aqua_day)),
        "dr_terra_obs": f"{1 + terra_day['shift_2026'][0]:.2f}",
        "dr_terra_pred": f"{1 + terra_day['shift_2026'][1]:.2f}",
        "dr_terra_r": f"{terra_day['r_all_years']:.2f}",
        "dr_total_obs": f"{total['obs']:.2f}",
        "dr_total_pred": f"{total['pred']:.2f}",
        "dr_goes_n": f"{e15['diurnal']['detections']:,}",
    }
    return lines, tokens


def experiments():
    """E13-E15, for those that have been run."""
    lines, tokens = [], {}
    results = [read_json(EXPERIMENTS / f"e{n}_results.json") for n in (13, 14, 15)]
    if any(results):
        lines += [
            "",
            "## Tests with three more FIRMS datasets",
            "",
            "None of these is used to make the record. Scripts: `pipeline/experiments/e13_third_viirs.py`, `e14_landsat.py`, `e15_drift.py`; discussion in EXPERIMENTS.md.",
        ]
    for result, section in zip(results, (third_viirs, landsat, goes_drift)):
        if result:
            more_lines, more_tokens = section(result)
            lines += more_lines
            tokens |= more_tokens
    return lines, tokens


def main():
    metrics = json.loads((MODEL / "metrics.json").read_text())
    idx = json.loads((APP_DATA / "index.json").read_text())
    world = json.loads((APP_DATA / "countries.json").read_text())[0]

    head = header(metrics, idx)
    hidden = hidden_years(metrics)
    harder = harder_measures(metrics)
    twin = benchmark(metrics)
    seams = steps(metrics)
    rng = ranges(metrics)
    fresh = fresh_months(metrics)
    aging = final_forward(metrics)
    gaps = outages(metrics)
    heat = persistent_sources(metrics)
    mask = mask_check(metrics)
    top = top_countries(metrics)
    trend = world_trend(idx, world)
    ba = burned_area()
    extra = experiments()

    document = (head, hidden, harder, twin, seams, rng, fresh, aging, gaps, heat, mask, top, trend, ba, extra)
    lines = [line for section_lines, _ in document for line in section_lines]
    (ROOT / "docs/RESULTS.md").write_text("\n".join(lines) + "\n")
    print("wrote RESULTS.md,", len(lines), "lines")

    # demo/tokens.json keeps this key order
    token_order = (head, harder, seams, trend, top, rng, gaps, heat, hidden, twin, fresh, mask, ba, extra)
    tokens = {}
    for _, section_tokens in token_order:
        tokens |= section_tokens
    (ROOT / "demo/tokens.json").write_text(json.dumps(tokens, indent=1))

    for name in ("SUBMISSION.md", "SUBMISSION_FORM.md"):
        text = (ROOT / "pipeline/templates" / name).read_text()
        for k, v in tokens.items():
            text = text.replace("{{" + k + "}}", v)
        assert "{{" not in text, (name, text[text.index("{{") :][:40])
        (ROOT / "docs" / name).write_text(text)
        print("wrote", name)


if __name__ == "__main__":
    main()
