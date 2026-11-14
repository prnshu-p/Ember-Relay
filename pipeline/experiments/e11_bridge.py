"""E11: the "bridge" that ties the Terra-only months before Aqua to the rest of the record.

Tested where the truth is known, then applied to the record. Needs stage 2's outputs (about 15 minutes).
Run: python3 pipeline/experiments/e11_bridge.py -> pipeline/experiments/e11_results.json
"""

import json
import pathlib
import sys

import numpy as np
from scipy import sparse

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import stage2_model as S2  # noqa: E402
from common import MODEL, month_index  # noqa: E402

g = S2.Grid()
shares = sparse.load_npz(MODEL / "shares.npz")


def record(tr, months, terra):
    """The record's recipe (model, box totals averaged with the best simple method) for these months."""
    model, sf = g.fit(tr, terra)
    kbf = g.local_ratio(tr, terra, fire_only=True)
    p = g.predict(model, sf, months, terra)
    return {t: g.reconcile(p[t], g.simple(t, kbf, sf, terra)) for t in months}


# ---- where the truth is known: models trained on 2016-19, bridge learned on 2014-15 (no VIIRS used),
# applied to the Terra-only estimates of Feb 2012 - Dec 2013 ----
tr = g.span(S2.MID, S2.DRIFT)
cal_m = list(range(month_index("2014-01"), month_index("2016-01")))
test = list(range(S2.VIIRS0, month_index("2014-01")))
F = record(tr, cal_m + test, False)
G = record(tr, cal_m + test, True)
k, kw = S2.bridge(g, F, G, cal_m)
B = {t: (G[t] * k[g.tl, g.cal[t]]).astype(np.float32) for t in test}
tiles_5_95 = [float(v) for v in np.percentile(k, [5, 95])]
print(
    f"test (train 2016-19, bridge from 2014-15, score Feb 2012 - Dec 2013); bridge for the world {kw:.3f},"
    f" tiles and months 5th-95th percentile {tiles_5_95}"
)
keep = ("country", "box", "cell", "wcountry", "wbox", "world", "bias")
out = {"test": {}}
for n, P in (("Terra-only", G), ("Terra-only, bridged", B), ("full inputs", F)):
    all_scores = S2.scores(g, P, test, shares)
    s = {x: all_scores[x] for x in keep}
    out["test"][n] = s
    print(
        f"  {n:<22} country {s['country']:.1%}  box {s['box']:.1%}  cell {s['cell']:.3f}"
        f"  world {s['world']:.1%} | weighted: country {s['wcountry']:.1%} box {s['wbox']:.1%}"
        f" | bias {s['bias']:+.1%}"
    )
out["test"]["bridge_world"] = float(kw)
out["test"]["bridge_tiles_5_95"] = tiles_5_95

# ---- on the record: bridge learned on Jul 2002 - Jan 2012, applied to Nov 2000 - Jun 2002 ----
# stage 2 now applies this bridge itself, so H.npy is already bridged before Aqua
AQUA, VIIRS0 = S2.AQUA, S2.VIIRS0
H = np.load(MODEL / "H.npy")
G = record(g.span(VIIRS0, S2.DRIFT), list(range(0, VIIRS0)), True)
k, kw = S2.bridge(g, {t: H[:, t] for t in range(AQUA, VIIRS0)}, G, list(range(AQUA, VIIRS0)))
Hb = H.copy()
for t in range(0, AQUA):
    Hb[:, t] = G[t] * k[g.tl, g.cal[t]]

terra = S2.monthly_totals(g.MT)
year_2001 = range(month_index("2001-01"), month_index("2002-01"))
out["record"] = {
    "bridge_world": float(kw),
    "bridge_tiles_5_95": [float(v) for v in np.percentile(k, [5, 95])],
    "step_2002_before": S2.step(g, S2.monthly_totals(H), terra, 0, AQUA, AQUA, VIIRS0),
    "step_2002_bridged": S2.step(g, S2.monthly_totals(Hb), terra, 0, AQUA, AQUA, VIIRS0),
    "total_before_aqua_millions": [float(H[:, :AQUA].sum() / 1e6), float(Hb[:, :AQUA].sum() / 1e6)],
    "year_2001_millions": [float(sum(A[:, t].sum() for t in year_2001) / 1e6) for A in (H, Hb)],
}
print("record:", json.dumps(out["record"], indent=1))
np.save(MODEL / "H_bridged_before_aqua.npy", Hb[:, :AQUA])
(pathlib.Path(__file__).parent / "e11_results.json").write_text(json.dumps(out, indent=1))
