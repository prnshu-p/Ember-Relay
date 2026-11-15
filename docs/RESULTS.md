# Results of the world run

Written by `pipeline/report.py` from the metrics of `pipeline/stage2_model.py`. Method and discussion: [SUBMISSION.md](SUBMISSION.md); how we got here, including the review that rebuilt the pipeline: [EXPERIMENTS.md](EXPERIMENTS.md).

- Grid: **189,999 cells** of 0.25° (every cell where either sensor ever saw a vegetation fire) × **313 months** from November 2000.
- Hotspots used: MODIS 105.3 million, VIIRS S-NPP 242.8 million, VIIRS NOAA-20 140.8 million.
- The record is the row in bold: the model with each 1° box total averaged with the best simple method. Against the model alone that costs a few tenths of a point on world totals in these tests and buys continuity where the sources change: the median country step at 2012 is 3.9% against 6.2% for the model alone (E10).

## Accuracy on years hidden from the model

- **Countries**: for each country, the median error of its monthly totals (months with 20 or more real hotspots; countries with 12 or more such months); then the median over countries.
- **1° boxes**: median error of box-months with 50 or more real hotspots. **Cells**: log-RMSE over 0.25° cell-months where either sensor saw fire. **World**: median error of the world's monthly total.
- Border cells count for each country by its share of the hotspots there. (The two ratios per country are fitted with each cell given to the country that has most of its hotspots, and scored the same way as everything else.) Lower is better.

### Forward: trained on 2012–2018, tested on 2019–2025

MODIS's orbits drift in the test years (Terra from 2020, Aqua from 2022), and every method reads low.

| Method | Countries | 1° boxes | Cells | World total | All hotspots (bias) |
|---|---|---|---|---|---|
| One ratio per country | 25.5% | 26.7% | 1.132 | 5.0% | -4.3% |
| Ratio per country and calendar month | 20.0% | 25.3% | 1.129 | 3.4% | -3.5% |
| Ratio per 1° box and calendar month | 20.5% | 21.8% | 1.118 | 3.5% | -3.8% |
| Best simple method (local ratio + the cell's usual small fires) | 19.6% | 20.6% | 0.846 | 3.2% | -3.6% |
| Model | 17.4% | 18.9% | 0.718 | 1.8% | -2.3% |
| **Model, box totals averaged with the best simple method** | **17.9%** | **18.6%** | **0.719** | **2.5%** | **-2.9%** |

### Backward: trained on 2019–2025, tested on 2012–2018

Trained on the drift years; every method reads high.

| Method | Countries | 1° boxes | Cells | World total | All hotspots (bias) |
|---|---|---|---|---|---|
| One ratio per country | 25.0% | 26.7% | 1.130 | 4.3% | +4.5% |
| Ratio per country and calendar month | 19.7% | 24.9% | 1.125 | 4.3% | +4.2% |
| Ratio per 1° box and calendar month | 19.3% | 21.2% | 1.114 | 3.8% | +3.7% |
| Best simple method (local ratio + the cell's usual small fires) | 18.9% | 19.9% | 0.835 | 3.3% | +2.9% |
| Model | 17.6% | 17.8% | 0.706 | 2.0% | +1.6% |
| **Model, box totals averaged with the best simple method** | **17.1%** | **17.7%** | **0.707** | **2.5%** | **+2.2%** |

### Analogue of the real task: trained on 2016–2019, tested on 2012–2015

Stable orbits on both sides and backward in time, as when 2000–2011 is estimated from 2012–2019: the closest test to the real task.

| Method | Countries | 1° boxes | Cells | World total | All hotspots (bias) |
|---|---|---|---|---|---|
| One ratio per country | 23.8% | 25.9% | 1.116 | 3.1% | +1.0% |
| Ratio per country and calendar month | 17.2% | 24.0% | 1.112 | 1.1% | +1.2% |
| Ratio per 1° box and calendar month | 17.2% | 20.3% | 1.099 | 1.3% | +0.5% |
| Best simple method (local ratio + the cell's usual small fires) | 18.6% | 19.4% | 0.859 | 1.5% | -0.5% |
| Model | 17.3% | 17.2% | 0.700 | 0.9% | -0.1% |
| **Model, box totals averaged with the best simple method** | **17.2%** | **17.0%** | **0.701** | **1.0%** | **-0.3%** |

### The same analogue with Terra-only inputs (the model used before July 2002)

The month's inputs come from Terra alone; the simple methods use Terra counts too.

| Method | Countries | 1° boxes | Cells | World total | All hotspots (bias) |
|---|---|---|---|---|---|
| One ratio per country | 33.3% | 42.3% | 1.538 | 6.7% | -1.8% |
| Ratio per country and calendar month | 26.7% | 41.0% | 1.533 | 2.5% | -1.3% |
| Ratio per 1° box and calendar month | 27.7% | 33.7% | 1.523 | 3.6% | -2.5% |
| Best simple method (local ratio + the cell's usual small fires) | 25.8% | 27.8% | 1.015 | 3.6% | -3.1% |
| Model | 23.9% | 25.8% | 0.788 | 2.4% | -1.9% |
| **Model, box totals averaged with the best simple method** | **23.2%** | **25.1%** | **0.793** | **2.7%** | **-2.5%** |

### Harder measures (forward / backward)

Weighted by fire (sum of absolute errors over sum of real hotspots, every month and area counted, so big fire months dominate), over all cell-months (zeros included), and the worst tenth of months for the world total.

| Method | Countries, weighted | 1° boxes, weighted | All cells (log-RMSE) | World total, 90th percentile |
|---|---|---|---|---|
| One ratio per country | 11.8% / 12.6% | 24.7% / 25.6% | 0.565 / 0.562 | 10.5% / 13.8% |
| Ratio per country and calendar month | 9.1% / 8.6% | 23.7% / 23.7% | 0.563 / 0.559 | 7.8% / 8.3% |
| Ratio per 1° box and calendar month | 8.6% / 8.2% | 20.6% / 20.4% | 0.557 / 0.554 | 8.1% / 7.1% |
| Best simple method (local ratio + the cell's usual small fires) | 8.7% / 8.2% | 20.3% / 19.8% | 0.501 / 0.498 | 7.3% / 6.9% |
| Model | 7.2% / 6.2% | 17.4% / 16.3% | 0.438 / 0.439 | 6.1% / 4.1% |
| **Model, box totals averaged with the best simple method** | **7.6% / 6.8%** | **17.8% / 16.8%** | **0.446 / 0.446** | **6.7% / 4.9%** |

- Countries scored in both directions: **166**. The record beats one ratio in **141**, the ratio per calendar month in **119**, the ratio per 1° box in **119** and the best simple method in **140**.
- Bias of the record by test year (all predicted over all real hotspots, less one): analogue 2012 +0.2%, 2013 0.0%, 2014 -0.5%, 2015 -0.8%; backward 2012 +2.0%, 2013 +2.4%, 2014 +1.9%, 2015 +1.8%, 2016 +1.5%, 2017 +3.9%, 2018 +2.3%; forward 2019 -1.9%, 2020 -1.0%, 2021 -1.5%, 2022 -2.8%, 2023 -3.2%, 2024 -4.1%, 2025 -6.3%.

## The twin-sensor benchmark

NOAA-20 predicting S-NPP (a VIIRS of the same design in the same orbital plane) with one scale factor, over the 69 months of 2019–2025 in which neither lost 2% or more of its detections. It is a measured reference, not a theoretical limit: the two view each cell from different angles and at different times.

| | Countries | 1° boxes | Cells |
|---|---|---|---|
| Twin VIIRS sensor | 8.6% | 10.4% | 0.620 |
| The record, the same months | 18.0% | 18.4% | 0.718 |
| Best simple method (both directions) | 19.2% | 20.3% | 0.840 |

Share of the gap between the best simple method and the twin sensor that the record closes: countries 11%, boxes 19%, cells 56%.
Until NOAA-20 was re-phased in March–April 2024 the two were half an orbit (about 50 minutes) apart, afterwards about a quarter orbit: twin error per country 8.4% (54 months) before and 5.4% (13 months) after. The second figure rests on few months, so only countries with fire in nearly every month are scored: the two are not directly comparable.

## Steps where the sources change

Step in (record / yardstick) between the months before a change and the months after, weighted by fire, calendar month by calendar month. Zero means no step. A fixed ratio passes the 2012 test by construction, so it shows that no fire is lost or invented at the change, not that the conversion is accurate.

| | At February 2012 (yardstick: MODIS; Jul 2002–Jan 2012 against Feb 2012–2019) | At July 2002 (yardstick: Terra; before Aqua against Jul 2002–Jan 2012) |
|---|---|---|
| **The record** | **+2.4%** | **+2.4%** |
| The record before its Terra-only months were bridged to the rest (E11) | | +5.1% |
| Model alone (not bridged) | +2.8% | +7.6% |
| Best simple method alone (not bridged) | +2.1% | +2.7% |
| Raw sensors joined (MODIS, then VIIRS) | +304% | |
| Real VIIRS, first 20 months against the rest (what no step looks like) | | +0.6% |

- Countries at 2012: median absolute step **3.9%**; within ±5%: 55%; within ±10%: 73% of 166.

## Are the ranges honest?

The app's range of an estimate is the 3rd to 97th percentile of the blind-test errors of similar months in the same area. Learned on one half of 2012–2025 and tested on the other, that alone held the real value in 84% of country-months (68% when weighted by fire): too narrow, because the relation between the sensors drifts. So every range is widened by ±9%, the smallest amount that brings both figures to 90%, plus 0.5% for each year before 2012 (the drift of the bias per year in the analogue test, at least 0.5%), and the error part is multiplied by 1.35 before July 2002 (Terra-only against full inputs in the analogue test).

| Area | Areas tested | Real value inside the range | Weighted by fire | In each area's biggest 10% of months | Before widening |
|---|---|---|---|---|---|
| Country | 192 | 90% | 93% | 93% | 84% |
| 2 degree box | 3,687 | 90% | 90% | 89% | 87% |
| 0.5 degree box | 34,055 | 93% | 89% | 89% | 92% |

## 2026: months no model was trained on

10 whole months of 2026, predicted by the model trained on the latest years (2019–2025). (The outage rule and the place mask were built with 2026 data in hand; no model saw it.) In 4 of them the real count is S-NPP alone; in the rest part of it was filled from NOAA-20.

| | Countries | 1° boxes | Cells | All hotspots (bias) |
|---|---|---|---|---|
| One ratio per country | 27.7% | 32.7% | 1.181 | -14.3% |
| Ratio per country and calendar month | 23.5% | 32.2% | 1.176 | -13.5% |
| Ratio per 1° box and calendar month | 23.1% | 29.9% | 1.169 | -13.9% |
| Best simple method (local ratio + the cell's usual small fires) | 21.8% | 27.9% | 0.902 | -14.3% |
| Model, box totals averaged with the best simple method | 19.6% | 25.6% | 0.767 | -13.1% |

Of 146 countries with enough fire in those months the record beats one ratio in 101, the ratio per calendar month in 93 and the best simple method in 100. Every method reads low, consistent with MODIS seeing a smaller share of the fires than in any training year: by 2026 Terra crossed the equator near 09:00 and Aqua near 15:30.

## The final model, forward in time

The record before 2012 is made by models trained on 2012–2019 only (stable orbits). Run forward over the drift years, which they never saw, they show how fast the conversion ages:

| Period | Record: countries | Record: bias | Best simple method: countries | Best simple method: bias |
|---|---|---|---|---|
| 2020–2025 | 18.6% | -2.8% | 20.3% | -3.4% |
| 2026 | 23.4% | -14.6% | 25.0% | -15.0% |

## Outages found and put right

From the world's detections per day and satellite (90 runs of lost days). A day is lost when it brings under half of what the partner sensor and the days around it lead to expect. Whole days and days at least four fifths lost:

- **Terra**: 2001-06-15 to 07-03; 2002-03-20 to 03-28; 2002-04-15; 2003-02-01; 2003-12-17 to 12-24; 2004-02-19; 2006-06-21; 2006-08-23; 2008-12-20 to 12-23; 2014-10-26; 2016-02-19 to 02-27; 2017-04-24; 2022-10-11 to 10-23; 2024-05-12; 2026-01-12; 2026-03-27.
- **Aqua**: 2002-07-30 to 08-07; 2002-09-13; 2002-11-15; 2003-05-12; 2016-02-19; 2016-02-28; 2016-04-17; 2020-08-16 to 09-02; 2021-09-23 to 09-24; 2022-04-01 to 04-16; 2024-02-01 to 02-02.
- **Suomi NPP**: 2012-03-24 to 03-26; 2022-07-27 to 08-10; 2023-07-26 to 07-27; 2024-05-30 to 06-03; 2024-07-10 to 07-16; 2024-07-24 to 07-29; 2024-09-26 to 09-27; 2024-11-03 to 11-06; 2025-07-05 to 07-07; 2025-11-12; 2026-03-10 to 03-12; 2026-04-28 to 04-30; 2026-06-01 to 06-02; 2026-07-10 to 07-16; 2026-08-03 to 08-04; 2026-10-12 to 10-13.
- **NOAA-20**: 2023-07-19 to 07-22; 2023-09-30 to 10-01; 2024-02-04 to 02-05.

- MODIS months that lost 5% or more of a satellite (its counts are scaled up by the lost share): 2001-06 (Terra 55%), 2001-07 (Terra 6%), 2002-03 (Terra 28%), 2002-07 (Aqua 9%), 2002-08 (Aqua 20%), 2003-02 (Terra 6%), 2003-12 (Terra 28%), 2008-12 (Terra 14%), 2016-02 (Terra 25% and Aqua 6%), 2020-08 (Aqua 39%), 2020-09 (Aqua 5%), 2022-04 (Aqua 57%), 2022-10 (Terra 32%), 2024-02 (Aqua 5%).
- Months in which 3% or more of the VIIRS count comes from NOAA-20 (S-NPP's lost share, scaled per 10° tile by the S-NPP/NOAA-20 ratio of the 24 healthy months before): 2021-08 (3%), 2022-06 (3%), 2022-07 (18%), 2022-08 (31%), 2023-07 (6%), 2024-05 (6%), 2024-06 (7%), 2024-07 (44%), 2024-09 (4%), 2024-11 (15%), 2025-07 (8%), 2026-03 (8%), 2026-04 (8%), 2026-06 (5%), 2026-07 (22%), 2026-08 (7%), 2026-10 (4%), 2026-11 (95%).
- S-NPP / NOAA-20 of world monthly totals over 81 healthy months: median 1.016; first year 1.020, last year 1.015.
- Suomi NPP data ended on 2 November 2026; the record is NOAA-20 from November 2026.

## What is left out

- **Persistent heat sources**: 206 cells (45 next to a volcano FIRMS flags) where the same spots are detected over and over: lava, and gas flares or industry that the fire-type flag missed. They held 148 thousand MODIS, 995 thousand S-NPP and 541 thousand NOAA-20 detections.
- **Other heat sources in near-real-time months** (no fire-type flag): removed by place. Tested on the typed months of 2026: the mask removes 92% of S-NPP's other sources and 1.1% of its fires, leaving a net error of -0.2% where no mask would leave +10.3%; for MODIS 81% and 1.0%, net +0.1% against +6.3%.

## The 25 countries with most fire

| Country | VIIRS hotspots 2012–2025 | VIIRS / MODIS | Record | Best simple method | Ratio per calendar month | One ratio | Step at 2012 |
|---|---|---|---|---|---|---|---|
| Democratic Republic of the Congo | 24.0 M | 3.9 | 6.8% | 7.0% | 7.4% | 12.9% | -0.4% |
| Brazil | 17.6 M | 3.8 | 4.7% | 5.8% | 6.1% | 11.8% | +1.5% |
| Angola | 15.6 M | 3.5 | 6.7% | 8.2% | 7.0% | 25.3% | -1.1% |
| Australia | 15.4 M | 4.6 | 3.4% | 4.1% | 5.4% | 5.3% | -0.1% |
| Russian Federation | 14.7 M | 4.2 | 6.3% | 8.6% | 11.1% | 18.1% | +11.0% |
| Zambia | 10.1 M | 3.7 | 8.4% | 8.4% | 7.4% | 14.2% | -0.1% |
| Mozambique | 9.2 M | 4.9 | 8.3% | 8.8% | 8.6% | 24.4% | +0.5% |
| South Sudan | 8.4 M | 3.6 | 9.3% | 10.3% | 9.8% | 16.3% | -0.4% |
| Central African Republic | 7.7 M | 3.7 | 10.7% | 13.2% | 14.4% | 28.2% | -0.1% |
| Canada | 6.2 M | 5.7 | 9.0% | 11.8% | 19.6% | 28.4% | +7.8% |
| India | 6.0 M | 5.6 | 9.2% | 10.0% | 9.8% | 12.3% | -0.2% |
| United States | 5.6 M | 3.6 | 7.1% | 7.6% | 10.1% | 16.7% | +1.9% |
| Tanzania | 5.3 M | 5.0 | 6.9% | 7.6% | 9.3% | 21.4% | +2.1% |
| Nigeria | 4.6 M | 5.4 | 9.0% | 10.3% | 13.4% | 24.3% | +3.8% |
| Madagascar | 4.2 M | 5.1 | 7.4% | 8.6% | 8.5% | 16.9% | +0.2% |
| Myanmar | 4.1 M | 5.3 | 12.5% | 11.2% | 11.7% | 17.0% | +5.2% |
| China | 4.1 M | 3.6 | 11.5% | 12.2% | 15.0% | 14.3% | -5.3% |
| Bolivia | 3.7 M | 3.8 | 9.8% | 12.0% | 9.6% | 11.6% | -0.9% |
| Guinea | 3.5 M | 3.8 | 6.3% | 8.6% | 9.5% | 10.4% | +1.4% |
| Mexico | 3.2 M | 3.9 | 7.2% | 7.2% | 6.5% | 9.1% | +0.5% |
| Indonesia | 3.1 M | 5.1 | 14.6% | 20.6% | 10.3% | 10.4% | +3.8% |
| Ethiopia | 2.8 M | 4.4 | 6.8% | 8.3% | 9.7% | 14.2% | -0.4% |
| Venezuela | 2.7 M | 4.6 | 9.6% | 10.0% | 11.3% | 11.5% | +0.5% |
| Argentina | 2.6 M | 3.3 | 8.2% | 9.3% | 7.7% | 9.9% | +4.1% |
| Cameroon | 2.4 M | 4.3 | 8.9% | 10.0% | 10.4% | 25.9% | +2.2% |

## The world's trend

- Harmonized record, 2003–2025: **-7% per decade** (Theil–Sen, 95% interval -11% to -2%). The level of the estimated years carries a further systematic uncertainty of a few percent, which moves this by about ±2 points.
- 2003–2019, where MODIS is self-consistent: harmonized -10.3%, MODIS alone -11.8% per decade. Before 2012 the record's trend comes from MODIS; it is not independent evidence.

## Independent check: burned area

Burned area is mapped from the change in surface reflectance after a fire, by one sensor family that flew unchanged across 2012. If the record is consistent, hotspots per km² burned must not step there. Step = estimated years (2003–2011) over VIIRS years (2013–2020), less one; 95% interval from resampling years. Primary product: ESA FireCCI51; GFED5 as a second opinion (up to half of its area is itself derived from MODIS hotspots, so it is lenient). The MODIS column is a control: it shows how much the yardstick itself moves for a single sensor. Burned-area products miss most small, cropland and deforestation fires, so regions where FireCCI51 maps under half of GFED5's area are marked weak. Script: `pipeline/burned_area.py`.

| Region | Record | Raw sensors joined | MODIS alone (control) | Record over control | Record, GFED5 | Yardstick |
|---|---|---|---|---|---|---|
| **World** | -8% [-13, -4] | -77% [-78, -76] | -6% [-11, -2] | -2% | -3% [-7, 0] | trusted |
| boreal North America | -7% [-26, +15] | -80% [-84, -75] | +3% [-21, +30] | -10% | -8% [-29, +20] | trusted |
| temperate North America | -13% [-22, -3] | -73% [-75, -69] | -5% [-15, +6] | -9% | -18% [-28, -5] | trusted |
| Central America | -14% [-26, 0] | -79% [-82, -75] | -13% [-26, +2] | -1% | +3% [-4, +10] | weak |
| northern South America | -7% [-16, +2] | -79% [-81, -77] | -6% [-15, +3] | -1% | -3% [-10, +5] | trusted |
| southern South America | +8% [-8, +28] | -70% [-75, -64] | +8% [-8, +30] | 0% | +4% [-4, +12] | weak |
| Europe | -7% [-22, +8] | -71% [-75, -66] | +1% [-13, +16] | -8% | -5% [-12, +3] | weak |
| Middle East | 0% [-20, +25] | -78% [-82, -74] | -4% [-17, +11] | +4% | +1% [-11, +17] | weak |
| Africa north of the equator | -8% [-11, -5] | -77% [-77, -76] | -8% [-11, -5] | 0% | -3% [-6, -1] | trusted |
| Africa south of the equator | -9% [-13, -5] | -77% [-78, -76] | -9% [-13, -5] | 0% | 0% [-2, +1] | trusted |
| boreal Asia | -29% [-43, -13] | -81% [-85, -78] | -19% [-32, -4] | -13% | -36% [-49, -21] | trusted |
| central Asia | -24% [-34, -13] | -77% [-80, -73] | -21% [-32, -10] | -3% | -3% [-9, +4] | trusted |
| South-East Asia | +10% [-2, +27] | -78% [-80, -74] | +15% [+1, +33] | -4% | -2% [-6, +3] | weak |
| equatorial Asia | +5% [-8, +25] | -78% [-81, -74] | +13% [-1, +33] | -7% | -9% [-17, +4] | weak |
| Australia and New Zealand | -14% [-28, +2] | -81% [-84, -78] | -13% [-25, -1] | -1% | -8% [-23, +7] | trusted |

- Year-to-year agreement with burned area, pooled over the 14 regions (r): record 0.88 in the estimated years and 0.79 in the VIIRS years; MODIS alone 0.88 and 0.81. Partly built in before 2012, since the estimates and both products descend from MODIS observations.
- Fails in both products where the yardstick is trusted: temperate North America, boreal Asia.
- What this can show: that the false step of the raw join is gone and the estimated years sit within about 10% of the VIIRS level. What it cannot: accuracy finer than that, anything per cell or month, or the Terra-only years 2000–2002.

## Tests with three more FIRMS datasets

None of these is used to make the record. Scripts: `pipeline/experiments/e13_third_viirs.py`, `e14_landsat.py`, `e15_drift.py`; discussion in EXPERIMENTS.md.

### A third VIIRS: NOAA-21 (E13)

25 months (2023-03 to 2026-10) in which none of Suomi NPP, NOAA-20 and NOAA-21 lost a day; scored like the record.

| Predictor (one scale factor) | Countries | 1° boxes | Cells | Countries, weighted by fire | World total |
|---|---|---|---|---|---|
| NOAA-20 -> S-NPP | 7.6% | 10.0% | 0.633 | 3.0% | 0.5% |
| NOAA-21 -> S-NPP | 8.0% | 10.0% | 0.639 | 3.1% | 0.7% |
| NOAA-21 -> NOAA-20 | 8.1% | 10.6% | 0.657 | 3.0% | 0.7% |
| average of NOAA-20 and NOAA-21 -> S-NPP | 6.7% | 8.5% | 0.556 | 2.7% | 0.5% |
| **The record's blind test (from MODIS)** | **17.4%** | **21.1%** | **0.738** | **10.2%** | **5.2%** |

- Three-cornered hat on 48,917 1° box-months with 50 or more hotspots in all three (standard deviation of log counts, scale differences removed): S-NPP 0.119, NOAA-20 0.134, NOAA-21 0.132 of their own; the record against S-NPP 0.412, or 0.394 once S-NPP's own part is taken out.
- 1° box error by period, before and after NOAA-20 was re-phased: before (Mar 2023 - Feb 2024) (6 months): NOAA-20 -> S-NPP 10.6%, NOAA-21 -> S-NPP 10.2%, NOAA-21 -> NOAA-20 9.9%; after (May 2024 on) (17 months): NOAA-20 -> S-NPP 9.7%, NOAA-21 -> S-NPP 9.9%, NOAA-21 -> NOAA-20 10.7%.
- Outage runs of S-NPP or NOAA-20 since March 2023: 21; NOAA-21 was normal on all their days in 21, and the three-sensor test confirms the loss in 18. NOAA-21 lost 4 days of its own.
- The months filled from NOAA-20, refilled from NOAA-21 instead (difference, world / median 10° tile): 2023-07 -0.1% / 0.5%, 2024-05 0.0% / 0.3%, 2024-06 0.0% / 0.4%, 2024-07 -0.8% / 2.5%, 2024-09 0.0% / 0.2%, 2024-11 0.0% / 0.6%, 2025-07 0.0% / 0.3%, 2026-03 0.0% / 0.4%, 2026-04 +0.1% / 0.4%, 2026-06 0.0% / 0.3%, 2026-07 0.0% / 1.0%, 2026-08 0.0% / 0.3%, 2026-10 -0.3% / 0.3%.
- November 2026, the record (NOAA-20 alone) against NOAA-21 scaled to S-NPP: world -0.1%, median 10° tile 6.8%.

### Landsat 8 and 9: fire in 30 m pixels, US and Canada south of 50°N (E14)

FIRMS's Landsat data stops at 65°N and is sparse north of 50°N, so the test uses the area where it looks: there it has seen fire in cells holding 98% of the record's.

- Where Landsat saw two or more fire pixels in a cell-month (179,024), the record has fire in 54%; where the record has 10 or more hotspots (26,931), Landsat saw fire in 74% (80% where it has 100 or more): Landsat looks once every 8 days or so, by day.
- Rank correlation of monthly totals: 1° box-months 0.60; United States 0.65, Canada south of 50N 0.72.
- Record hotspots per Landsat fire pixel, August to October: 2023 0.65, 2024 0.67, 2025 0.94, 2026 0.52 (2026: near-real-time data, cleaned by place).

### GOES: the daily cycle of fire, and the drift of the MODIS orbits (E15)

Tropical South America. The local hour at which each satellite observed fires, read from its detections; the daily cycle of fire from 662,867 GOES-16 detections on 36 days of 2024.

| | Observing hour 2013–2019 | Observing hour 2026 | Count per S-NPP hotspot in 2026 (2013–2019 = 1): observed | predicted from the daily cycle | Correlation over 2012–2026 |
|---|---|---|---|---|---|
| Terra, day | 10:32 | 8:46 | 0.47 | 0.36 | 0.97 |
| Terra, night | 22:39 | 20:48 | 1.75 | 1.49 | 0.87 |
| Aqua, day | 13:41 | 15:26 | 1.12 | 1.00 | -0.25 |

- All of MODIS in this region per S-NPP hotspot in 2026: observed 1.03, predicted 0.90: the two satellites' changes largely cancel here.
