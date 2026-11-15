# Lab notebook: the experiments behind Burning Activity Calendar

Each entry has a question, what we did, what came out and what we decided. The world model is
`pipeline/stage2_model.py`; the scripts of E11-E15 are in `pipeline/experiments/`. E1-E8 ran on an earlier regional
prototype; their scripts and tables are in the repository history at commit `1718f88`. Three scores are used
throughout, always on months the model was not trained on:

- **region / country**: median error of monthly totals of a whole region or country;
- **box**: median error of monthly totals of 1° boxes (box-months with 50 or more real hotspots);
- **cell**: log-RMSE over 0.25° cell-months where either sensor saw fire.

"Both directions" means trained on 2012–2018 and tested on 2019–2025, and the reverse.

## E1. The seam test: does the record pass through 2012 without a step?

**Question.** MODIS flew the whole time, so it is the yardstick. If the sensor of origin no longer matters, the ratio
harmonized / MODIS must be the same before 2012 (model estimates) and after (real VIIRS), calendar month by calendar
month. Is it?

**Method.** `e1_seam.py`: the step in harmonized / MODIS at February 2012, weighted by fire, July 2002–2019.

**Result.** Our first model, which had passed every earlier test, has a real step in six of eight regions:

| Region | Step at 2012 | VIIRS hotspots where MODIS saw nothing | Step that share would cause |
|---|---|---|---|
| Greece | +33.3% | 24.0% | +31.6% |
| Córdoba | +28.3% | 17.1% | +20.6% |
| Portugal | +20.4% | 9.5% | +10.5% |
| Chile | +16.2% | 14.4% | +16.9% |
| California | +13.4% | 5.6% | +5.9% |
| Florida | +9.3% | 11.4% | +12.8% |
| Paraguay | +0.2% | 4.1% | +4.2% |
| Zambia | +0.1% | 0.8% | +0.8% |

The cause: VIIRS also finds fires in cells and months where MODIS found none. In the overlap those cell-months are
rows in the table, because VIIRS made them. Before 2012 they do not exist, so the model has nothing to convert and
those fires vanish. The share of such hotspots predicts the step (correlation 0.90).

**Second finding.** The same blind spot flattered our earlier accuracy tests: the test tables contained a row
wherever VIIRS saw fire, which told the model where the invisible fires were. Scored honestly, on every
fire-prone cell and month (`e1b_dense.py`, `e1c_variants.py`), the first model **as it is really deployed** has a
28% regional error, worse than one scale factor (19%). The earlier headline numbers (7.8% against 19.7% in
California) are withdrawn.

**Decision.** Model the complete grid: every fire-prone cell, every month, zeros included. All later scores use it.
After the change the step falls to within ±5% in five regions. It stays positive in Greece (+9 to +15%), Portugal
(+10 to +14%) and Córdoba (+14 to +25%, depending on the inputs): part of a step can be real, because fires before
2012 need not have had the same mix of sizes.

## E2. One model for everywhere, or one per region?

**Method.** `e2_universal.py`, 2019–2025: a model per region; one pooled model with and without latitude/longitude;
a model that never saw the region. (Run before E1, so its absolute numbers share the old scoring; E8 repeats the
location question on the world grid.)

**Result.** Mean regional error: own model 12.4%, pooled without location 14.2%, **pooled with location 11.5%**,
never-seen region 17.4% (totals off by 0.78× to 1.37×).

**Decision.** One world model with location inputs, trained on every place. A model cannot be carried to a place it
has never seen; with the global archive it never has to be.

## E3. Which form of model, at every area size?

**Method.** `e3_modelform.py`, complete grid, both directions, eight regions: one ratio (A), a ratio per calendar
month (B), a ratio per calendar month and 1° box shrunk toward B (C), gradient boosting with the first inputs (D0)
and with the cell's MODIS and small-fire climatology (D2), boosting that learns a correction to B or C (F, FC), and
averages of a ratio and the model (G, GC).

| Model | Region | Box | Cell |
|---|---|---|---|
| A one ratio | 17.9% | 23.9% | 1.049 |
| B ratio per calendar month | 14.3% | 23.7% | 1.051 |
| C local seasonal ratio | 14.6% | 21.7% | 1.044 |
| D0 boosting, first inputs | 14.0% | 22.3% | 0.776 |
| D2 boosting + climatologies | 15.0% | 21.1% | 0.728 |
| F / FC boosting from a ratio baseline | 15.2% / 14.8% | 21.1% | 0.732 / 0.731 |
| G average of B and D2 | 13.3% | 20.4% | 0.830 |
| GC average of C and D2 | **13.3%** | **19.8%** | 0.826 |

**Result.** A plain ratio per calendar month is a strong rival for whole-region totals: an honest baseline we had not
tried. Boosting is far better per cell. Averaging the two is best for totals.

**Decision.** Keep the boosting model's cell detail and set each 1° box-month total to the average of the model and
the local seasonal ratio ("reconciliation"; later documents call it averaging the box totals).

## E4. Which family of model? (regional prototype)

**Method.** On the California prototype we compared seven model families (linear and log-linear regression,
random forest, gradient boosting in scikit-learn and LightGBM with several losses, a small neural network in
PyTorch), each tuned, on the 2019–2025 test years. The script, `benchmark.py`, was removed when the pipeline moved
to the world grid and is in the repository's history.

**Result.** Every flexible model landed within about one point of the others. A log-target model under-predicted
totals by about 16%; a Poisson loss did not.

**Decision.** Gradient boosting with a Poisson loss: as good as anything else, fast, and it handles zeros.

## E5. How accurate can any conversion be? The twin-sensor benchmark

**Question.** How close to perfect is possible at all?

**Method.** `e5_floor.py`. S-NPP and NOAA-20 carry VIIRS instruments of the same design in the same orbital plane
(half an orbit, about 50 minutes, apart until March 2024). Predicting S-NPP counts from NOAA-20 counts shows how
far two good sensors disagree: what is left is fire changing between passes, clouds and scan geometry. California, 2019–2025:

| Predictor of S-NPP | Region | Box | Cell |
|---|---|---|---|
| Twin VIIRS sensor (NOAA-20): the benchmark | 5.3% | 12.0% | 0.673 |
| One ratio on MODIS | 19.7% | 32.4% | 1.160 |
| Ratio per calendar month | 10.6% | 26.1% | 1.128 |
| Complete-grid model | 16.2% | 25.1% | 0.812 |
| Model, reconciled | 12.8% | 22.0% | 0.831 |

**Decision.** Report every result against this reference. (We first called it a "physical floor" that no method
fed by MODIS could beat. The review in E10 showed that is too strong: the two VIIRS view a cell from different
angles and at different times, so it is a measured benchmark, not a limit.)

## E6. Physics-motivated inputs

**Idea.** S-NPP passes at 13:30, like Aqua; Terra passes at 10:30. Aqua's detections are nearly simultaneous with
VIIRS and Terra's are not. So give the model the counts **by satellite and day/night**, and the **shape** of the
month: days with fire, the busiest day, distinct 1 km pixels, median and 90th-percentile fire power, share of weak
detections.

**Result** (`e6_features.py`; California, Greece, Chile; both directions): region 16.8% → 16.0%, box 24.2% → 23.5%,
cell 0.768 → 0.763. Small but consistent. For the months before Aqua (July 2002), a model that only ever sees Terra
beats scaling Terra's counts by a factor per box and cell (box 32.0% against 36.8%, cell 0.796 against 0.898); on
whole-region totals it is slightly worse (21.1% against 20.6%).

**Decision.** Adopt both input groups and the Terra-only model.

## E7. Day-by-day pairing (a negative result)

**Idea.** Convert each day's MODIS detections, since the sensors see the same fire on the same day, and estimate the
VIIRS hotspots of MODIS-free days with a second model.

**Result** (`e7_daily.py`, California): monthly model 12.5% / 21.7% / 0.783, daily pairing 13.2% / 22.1% / 0.786.
No gain. (The average of the two was marginally better, 12.4% / 20.8% / 0.780: not worth a second model.)

**Decision.** Not adopted. The gap to the benchmark is information MODIS's 1 km pixels do not carry, not something
lost by adding up months.

## E8. Tuning the world model without touching the test years

**Method.** `e8_global_tune.py`: train 2012–2016, validate 2017–2018, world grid. Score = mean of the three errors,
each divided by the seasonal ratio's (1.0 = no better than a seasonal ratio).

| Change from the baseline (0.788) | Score |
|---|---|
| Reconciliation weight 0 / 0.25 / 0.75 (baseline 0.5) | 0.833 / 0.819 / 0.799 |
| No location inputs | 0.800 |
| Tile weighting 0 or 1; zero-sample 3% or 20% | 0.781–0.784 (no effect) |
| Extra context (wider ring, two months either side, tile activity) | 0.786–0.791 (no gain) |
| 600 trees / 127 leaves / 255 leaves | 0.770 / 0.763 / 0.750 |
| 255 leaves, 600 trees, minimum leaf 50 | **0.744** |
| 511 leaves, 400 trees, minimum leaf 50 | 0.745 |
| Three seeds averaged | 0.782 (no gain) |

**Decision.** 255 leaves, 600 trees, minimum leaf 50, reconciliation weight 0.5, location inputs on.

## E9. Suomi NPP's outages (found while checking 2026), and a correction

**Finding.** In 2026 the world's S-NPP count fell well below NOAA-20's in several months, and day by day S-NPP has
whole days with no data (10–12 March and 28–30 April 2026, for example).

**First decision (replaced in E10).** Take a whole month from NOAA-20 when the world's S-NPP/NOAA-20 ratio falls
more than 7% below its usual value.

**Correction.** We wrote here that "the satellite, not our pipeline, was silent". The review (E10) showed that
was only partly true. Our downloader glued two rows together whenever a 5-day window had to be fetched day by day,
which made stage 1 drop three whole files, and six files had been saved cut short. About three quarters of the
March, April and June 2026 shortfall was our own loss. The real gaps (10–12 March, 28–30 April, 1–2 June, 10–16 July,
3–4 August, 12–13 October 2026) match NASA's outage notices and are much smaller. The published record was barely affected, because
those months were taken from NOAA-20 either way, but the diagnosis was wrong. The downloader now refuses any answer
with a cut or glued row, the six files were fetched again, and outages are found day by day for every satellite (E10).

## E10. The review: six independent attempts to break the project, and the rebuild that followed

**Question.** The world model passed our own tests. What would referees find who did not share our assumptions?

**Method.** Six independent reviews, each given one part to attack and none shown our conclusions: (A) the tests and
possible leakage; (B) the path from raw FIRMS files to tables; (C) every headline number, recomputed from the saved
arrays with separate code, then stress-tested; (D) the numbers the browser computes; (E) the live app; (F) every
factual claim against NASA documents and the literature. The reviewers could read and run everything and change
nothing. The review was conducted as a rigorous, independent adversarial audit; every finding below was reproduced before we acted.

**What they found, and what we changed.**

| Finding (who) | Evidence | Change |
|---|---|---|
| One model input, the cell's usual MODIS count, included the row's own month, but only for 2003–2019. A model trained inside those years and applied outside saw combinations that cannot occur in training (A, C) | Months before Aqua about 13% low for the world, 35–40% in boreal Asia; step of +15% at July 2002 against Terra; forward test doubled big boreal fire months (Canada 2023: 2.78 M predicted, 1.64 M real) | The climatology leaves the row's own month out. Forward error on fire-weighted country totals went from worse than a seasonal ratio to better (7.6% against 9.1%); the July 2002 step fell to about +5% |
| MODIS outages were not handled: only S-NPP was checked (B, C, F) | Terra silent 15 June–3 July 2001: June 2001 was 40–50% low. Aqua silent 1–16 April 2022: blind test off by 40% that month | Outage days are found for all four satellites from the world's detections per day, against the partner sensor. The list matches NASA's notices. MODIS counts are scaled up by the lost share; long outages are kept out of training |
| Our downloader glued two rows whenever a 5-day window was fetched day by day; stage 1 then dropped the whole file. Six files were also cut short (B) | 380,616 S-NPP detections missing in March, April and June 2026: three quarters of what E9 called satellite outages | Downloader fixed and strict; files fetched again; E9 corrected |
| Months without a fire-type flag (near-real-time, from August 2026) counted gas flares and industry (B, F) | +10% for the world, four to six times too high in Iraq, Iran, Libya, Saudi Arabia, Egypt | A place mask built from the typed data since 2023: removes 92% of the other sources and 1% of fires; net error −0.2% |
| Lava was counted as fire, and the model then invented eruptions before 2012 (C, E) | Kilauea 2018: 28,824 VIIRS hotspots; Galápagos June 2008: 142 MODIS detections became 7,381; Iceland's busiest month was the Holuhraun lava field | Cells where the same spots are detected over and over are left out (206 cells): next to a volcano FIRMS flags, or for four months within a year |
| The final model trained on 2012–2025 although MODIS's orbits drift from 2020 (A, F) | Trained on the drift years, the estimates for 2002–2011 came out about 2% higher; backward test biased high in every year | The record's models train on 2012–2019 only. A new test, the analogue (train 2016–2019, test 2012–2015), mirrors the real task: bias −0.3% |
| Box totals were halved wherever a 1° box had no MODIS hotspot, and our baselines could not predict fire where MODIS saw none (A, C) | 42% of Libya's hotspots, 24% of France's, sat in such box-months; "closes 76% of the gap" was measured against a ratio that predicts zero in 44% of the scored cell-months | A best simple method: local seasonal ratio plus each cell's usual small fires. It is now the baseline everywhere and the partner in the box totals |
| The ranges were too narrow (A, C, F) | Nominal 94%; 84% of country-months inside, 68% weighted by fire; misses one-sided | Ranges widened until 90% holds by both counts, more for earlier years and before Aqua |
| The 2012 seam test cannot tell the model from a fixed ratio (A, C) | A ratio passes by construction; the old +0.6% was partly luck | Reported for the record, the model alone and the simple method; a second step test at July 2002; an independent check against burned area |
| Border cells went wholly to one country; cells that first burned in 2026 had none (B) | Eritrea −29%, Lesotho −28%; Russia's August 2026 17% low | Cells are shared between countries in proportion to their hotspots; new cells inherit from their neighbours |
| The export dropped estimates under 0.25 where a whole 1° box was below it (D) | Sweden's record before 2012 was 13% low in the app; its "step at 2012" read +17% for a model value of +7% | Loss-free folding (box totals asserted equal); country series come straight from the model's arrays |
| Claims were too strong (F) | "Physical floor"; "50 minutes apart" (true only until March 2024); "VIIRS took over in 2012"; "sees four times more fires" | Texts corrected; prior work cited |
| 28 defects in the live app (E) | A tap on a calendar month often did nothing on a phone; typing "Nigeria" jumped to Niger; typing coordinates wrecked the area | Fixed; the parity test was rewritten and now catches 19 of 19 planted bugs (the old one caught 5 of 17) |

**Two decisions that needed their own experiments.**

- *What counts as lava?* Our first rule (the same spots detected again and again in a month) also removed peat
  fires in Sumatra and Kalimantan and California's Creek Fire: they repeat nearly as much as lava for a month or
  three. The rule that works needs a second condition: next to a volcano FIRMS flags, or four such months within a
  year. Peat and long forest fires stay.
- *Should box totals still be averaged with a simple method (E3)?* With the inputs corrected the model alone is
  slightly better on blind world totals (0.1–0.7 points) and fire-weighted errors. But the averaged record is
  steadier where the sources change: median country step at 2012 of 3.9% against 6.2%, and +5.1% against +7.6%
  at July 2002 (before the bridge of E11). Steps turn into false trends (roughly 0.5 to 1 point per decade for each
  1% of step), so we kept the averaging: continuity is the first duty of a harmonized record. RESULTS.md shows both.

**What the corrected results say.** The model's advantage is real but narrower than we had claimed. Below country
size it beats every simple method in every test (1° boxes about 18% against 20%; cells 0.71 against 0.84). For
whole countries it wins across the drift years (17.5% against 19.8% for a seasonal ratio) and in big fire months,
but with stable orbits a seasonal ratio per country is just as good (17.2% both). The old headline of 16.9%
against 21.3% rested on a weaker baseline and on country borders drawn by majority.

**What still failed after the rebuild** (and led to E11 and E12).
- Against burned area the record steps by about −8% at 2012 for the world (MODIS alone: −6%, so most of it is the
  yardstick), but by −29% in boreal Asia, of which about 13 points are specific to our estimates.
- The months before Aqua still stepped by about +5% against Terra.
- By 2026 every method reads 12–15% low, because MODIS now sees a smaller share of the fires. A conversion trained
  on earlier years ages as the orbits drift.

## E11. A bridge for the months before Aqua

**Question.** After E10 the record still stepped by +5.1% at July 2002 against Terra: the Terra-only estimates
before it sit lower than the full-input estimates after it. Satellite records are cross-calibrated through an
overlap. Is there one here?

**Idea.** From July 2002 the Terra-only model can be run as well as the full one. The ratio of the two, per 10°
tile and calendar month over July 2002–January 2012, is a "bridge": multiplying the Terra-only estimates by it
ties them to the full ones. No VIIRS data is involved.

**Test where the truth is known** (`e11_bridge.py`). Both models trained on 2016–2019; the bridge learned on
2014–2015; applied to the Terra-only estimates of February 2012–December 2013; scored against real VIIRS.

| | Countries | 1° boxes | Cells | World total | Countries, weighted by fire | Bias |
|---|---|---|---|---|---|---|
| Terra-only | 22.5% | 25.3% | 0.797 | 2.5% | 9.5% | −2.5% |
| Terra-only, bridged | 22.2% | 25.3% | 0.796 | 2.1% | 9.1% | −1.5% |
| Full inputs (for scale) | 16.1% | 17.1% | 0.705 | 0.9% | 5.6% | +0.1% |

**Result.** A small gain on every measure and none worse. On the record the bridge is 1.03 for the world (0.87
to 1.12 across tiles and months): the months before Aqua rise by 2.7%, and the step at July 2002 falls from +5.1%
to +2.4%, the size the best simple method alone gives (+2.7%).

**Decision.** Adopted in `stage2_model.py`. The gain in accuracy is small; the point is continuity.

## E12. A step at 2012: is the conversion off, or did the fires change?

**Question.** Russia's record steps against MODIS at 2012, and the burned-area check fails in boreal Asia. Does
that show a biased conversion?

**Method** (`e12_mix.py`). A step in record / MODIS has two possible sources. The *mix*: fire moves between places
and seasons whose VIIRS/MODIS ratio differs, so a country's overall ratio moves although no local ratio did. The
*conversion*: the estimated ratio of a place and season before 2012 differs from the one observed there after. We
split each country's step with strata of 1° box × calendar month: "mix" is the step a fixed ratio per stratum
would show, "within" is the rest.

| Country | Step at 2012 | From the mix | Within places and seasons |
|---|---|---|---|
| World | +2.2% | +1.4% | +0.8% |
| Russia | +16.1% | +10.9% | +4.7% |
| Canada | +13.6% | +7.5% | +5.7% |
| United States | +2.4% | +6.4% | −3.8% |
| India | +1.8% | +8.8% | −6.4% |
| China | −4.5% | +5.8% | −9.8% |
| Nigeria | +5.2% | −1.9% | +7.3% |
| Brazil | +1.4% | −0.7% | +2.1% |
| DR Congo | −0.8% | 0.0% | −0.8% |

(Steps here compare whole periods, July 2002–January 2012 against February 2012–2019, so they are larger than the
calendar-month-matched steps of RESULTS.md where the season of the fires shifted: Russia +16.1% here, +11.0% there;
Canada +13.6% and +7.8%.)

**Result.** In Russia two thirds of the step is the mix: summer forest fire north of 55°N rose from 24% to 50%
of Russia's MODIS hotspots, and it has the highest VIIRS/MODIS ratio (4.65, against 3.5 for spring fires in the
south). That is a real change in the fire regime, which a harmonized record should show. About 5% remains within
places and seasons, in Russia and in Canada: it may be a bias of the estimates, or bigger fires within the same
places, and nothing we have can tell the two apart. The same split suggests estimates about 10% high in China, 6%
high in India and 7% low in Nigeria; changes in crop burning could explain part. Across the 19 countries with most
fire the median "within" part is 2.1%, and 79% are inside ±5%.

**Decision.** No change to the model. The claim is corrected: the estimates for boreal countries before 2012 may
be about 5% low, not 10%; most of what looks like a step there is the fires themselves.


## E13. A third VIIRS: NOAA-21 tests the benchmark, the outage repairs and the hand-over

**Question.** The twin-sensor benchmark rested on one pair, NOAA-20 predicting Suomi NPP. Is 8–10% a property of
that pair or of VIIRS itself? How large is each sensor's own random error, and the record's? And were the outage
repairs, which fill Suomi NPP's lost days from NOAA-20, right?

**Method** (`e13_third_viirs.py`). NOAA-21 carries the same VIIRS instrument; it is in FIRMS from March 2023
(science data to July 2026, near-real-time after). It goes through stage 1 with the same cleaning; the place mask
is built from Suomi NPP and NOAA-20 only, so NOAA-21 cannot change the record. On NOAA-21 the mask removes 91–95%
of the other heat sources and 1–2% of the fires. All scores use stage 2's own scoring, on the 25 of 44 months
(March 2023–October 2026) in which none of the three lost a day.

**Result.**

| On the same 25 months | Country-month | 1° box-month | Cell (log-RMSE) |
|---|---|---|---|
| NOAA-20 → Suomi NPP | 7.6% | 10.0% | 0.63 |
| NOAA-21 → Suomi NPP | 8.0% | 10.0% | 0.64 |
| NOAA-21 → NOAA-20 | 8.1% | 10.6% | 0.66 |
| NOAA-20 and NOAA-21 averaged → Suomi NPP | 6.7% | 8.5% | 0.56 |
| The record, blind (MODIS → Suomi NPP) | 17.4% | 21.1% | 0.74 |

- Every pair disagrees by the same amount, so the benchmark belongs to VIIRS, not to one pair: three identical
  instruments, looking at the same places within about an hour of each other, differ by 8% per country-month.
  Averaging two lowers it to 6.7%, so much of it is chance (which fires burn and which clouds pass when each looks).
- Three-cornered hat (48,917 box-months with 50 or more hotspots in all three): the three pairwise log standard
  deviations, 0.18, 0.18 and 0.19, give each sensor an own random error of 0.12 (Suomi NPP), 0.13 (NOAA-20) and
  0.13 (NOAA-21). The record against Suomi NPP: 0.41; with Suomi NPP's own error taken out, 0.39. The record's
  error per box-month is about three times a VIIRS sensor's own, and almost all of it comes from MODIS, not from
  noise in the target. The hat assumes independent errors; the three share a design and an early-afternoon orbit,
  so errors they share (clouds at that hour, say) are hidden, and their own errors are lower bounds.
- Before and after NOAA-20 was re-phased (March–April 2024): 1° box error 10.6% and 9.7% (NOAA-20 → Suomi NPP),
  9.9% and 10.7% (NOAA-21 → NOAA-20). No effect beyond a point either way.
- Outages: of the 21 runs of lost days that stage 2 found for Suomi NPP or NOAA-20 since March 2023, NOAA-21 was
  normal on all their days in all 21, so the losses were the sensors', not a lull in the fires. The three-sensor
  test confirms the loss in 18; the other 3 are partial (52–64% lost), all in the near-real-time months of 2026.
  NOAA-21 itself lost 4 days.
- The 13 months in which stage 2 filled some of Suomi NPP's days from NOAA-20, refilled from NOAA-21 instead:
  world totals change by at most 0.8% (July 2024, 44% of the month filled), the median 10° tile by at most 2.5%.
- Hand-over: Suomi NPP stopped on 2 November 2026, so the record's November is NOAA-20 alone, scaled to Suomi NPP.
  NOAA-21, scaled the same way, agrees: world −0.1%, median 10° tile 6.8% (74 tiles, 1–13 November).

**Decision.** No change to the record: NOAA-21 stays a test. The benchmark is restated as a property of VIIRS
("three identical sensors disagree by 8% per country-month"); the outage repairs and the hand-over stand. Using
NOAA-21 in the record itself, as a third VIIRS average, would lower the target's own noise (6.7% instead of 8%),
and is listed as a next step.


## E14. Landsat: where does a much finer sensor see fire?

**Question.** Landsat 8 and 9 see fire in 30 m pixels, far finer than VIIRS, but only about once every 8 days and
only by day. They cannot test the years before 2012 (they are in FIRMS from June 2022), but they can test where the
VIIRS-era record puts fire, and whether the near-real-time months of 2026, cleaned by place rather than by type,
carry industry that the cleaning missed.

**Method** (`e14_landsat.py`). Landsat detections of nominal or high confidence, July 2022–October 2026, on the
record's 0.25° grid. FIRMS's Landsat data stops at 65°N and is sparse north of 50°N (it has fire in 5% of the
record's fire cells north of 60°N), so the comparison uses the United States and Canada south of 50°N, where
Landsat has seen fire in cells holding 98% of the record's.

**Result.**
- Where the record has 100 or more hotspots in a cell-month, Landsat saw fire there 80% of the time (74% at 10 or
  more); the rest fits an 8-day revisit.
- Where Landsat saw two or more fire pixels, the record has fire in only 54% of the cell-months. Landsat's 30 m
  pixels find crop-residue and prescribed burns that are too small or too short for VIIRS. A VIIRS-equivalent
  count is what VIIRS would record, not every fire.
- Monthly totals rise and fall together: rank correlation 0.60 over 1° box-months, 0.65 for the United States,
  0.72 for southern Canada.
- Record hotspots per Landsat fire pixel, August to October: 0.65 (2023), 0.67 (2024), 0.94 (2025) and 0.52 (2026,
  near-real-time). No sign that the place mask let industry through; but the ratio moves by half between years
  with the mix of fires, so this test could not detect a leak of 10–25%.

**Decision.** No change to the record. The limitation "VIIRS-equivalent is not every fire" goes into the write-up.

## E15. Why do conversions age? The drift of the MODIS orbits, measured

**Question.** Every conversion trained on earlier years reads low by 2026, and we had only written "consistent with
the drift of the MODIS orbits". Can the drift be measured, and does it explain the change?

**Method** (`e15_drift.py`). Three steps, all in tropical South America (20°S–5°N, 75°W–35°W), which GOES-East
sees well:
1. *When did each satellite actually look?* The local solar time of every fire detection, from the detections
   themselves (UTC time, longitude, equation of time), median per satellite and year.
2. *How does fire change over the day?* GOES-16 scans the Americas every 10 minutes. From 36 days of 2024
   (663,000 detections, FIRMS) we built the daily cycle of fire: it peaks at 14:45 local time; at 09:00 there is
   about a sixth as much as at 13:30.
3. *Prediction against observation.* Each satellite's count per Suomi NPP hotspot (S-NPP with its lost days
   filled from NOAA-20; months in which Terra or Aqua lost data left out), relative to 2013–2019, against the
   daily cycle evaluated at that year's observing hour.

**Result.**

| | 2003–2019 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Terra, daytime observing hour | 10:31 | 10:17 | 10:07 | 9:44 | 9:20 | 8:46 |
| Terra daytime count: observed / predicted | 1.00 | 0.87 / 0.89 | 0.90 / 0.82 | 0.62 / 0.66 | 0.67 / 0.52 | 0.47 / 0.36 |
| Aqua, daytime observing hour | 13:42 | 13:46 | 14:01 | 14:23 | 15:01 | 15:26 |
| Aqua daytime count: observed / predicted | 1.00 | 0.94 / 1.01 | 0.96 / 1.03 | 0.85 / 1.05 | 1.11 / 1.04 | 1.12 / 1.00 |
| Suomi NPP and NOAA-20, observing hour | 13:38 | | 13:41 | | 13:41 | 13:35 |

- Terra drifted almost two hours into the morning, when little burns: its daytime count fell by half, and the
  daily cycle predicts the fall year by year (correlation 0.97 over 2012–2026; before 2020 the count moved by ±2%
  a year). The prediction is somewhat too steep for 2025–2026, plausibly because GOES's 2 km pixels miss more of
  the small morning fires than MODIS does.
- Terra's night pass moved into the evening, when more burns: its night count rose (1.75 by 2026 against 1.49
  predicted; correlation 0.87).
- Aqua drifted across the afternoon peak of the fire day, so the cycle predicts almost no change; what is
  observed is within the year-to-year noise.
- For all of MODIS in this region the effects largely cancel: observed +3% by 2026, predicted −10%.

**Decision.** The drift is now a measured mechanism, not an assumption: for each satellite separately it explains
large changes. It does not explain the worldwide shortfall of 2026 by itself, because in the region GOES can see,
the losses and gains of the two satellites cancel; other regions have other daily cycles, and GOES does not see
them. The write-up says exactly that, and the record is still made only from the years of stable orbits.

## The world model: final results

See [RESULTS.md](RESULTS.md) for every number of the final world run (three blind tests, the twin-sensor
benchmark, the steps, range coverage, 2026, outages, the burned-area check). They are written by
`pipeline/stage2_model.py` into `data/global/model/metrics.json`, turned into tables by `pipeline/report.py`, and
shown in the app under "How we know".
