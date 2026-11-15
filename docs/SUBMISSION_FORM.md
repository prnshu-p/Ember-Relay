# Text for the Space Apps project form

One section per field of the Project page (2026 Project Submission Guide). Replace the items in CAPITALS.
Every link must open without a login, so the repository has to be public before you submit.

## Project Name
Burning Activity Calendar

## High-Level Project Summary
Satellites have recorded fire hotspots since 2000 with MODIS, and since 2012 also with VIIRS, whose finer pixels
record about four times as many. The two records cannot be compared: joined together, the world's fire seems to
step up by +304% in 2012 when only the sensor changed. We built a model that converts every MODIS count into
what VIIRS would have recorded, for every 25 km cell on Earth, and a web app that shows the result as a burning
activity calendar from November 2000 to this week. Search a country or draw any area: the app shows how many
hotspots each month had, how unusual that is for the time of year, where it burned, when the fire season peaks and
where fire is rising or falling, and lets you download the numbers and the picture. Tested on years the model never
saw, its error per 1° box is 18.2% against 20.3% for the best simple method we could build, and the record
passes through 2012 with a step of +2.4%. The estimates carry ranges that hold the real value
90% of the time. We found and corrected the outages of all four satellites, measured how far two VIIRS
sensors of the same design disagree, checked the record against burned-area data that use no VIIRS, and had the
whole project stress-tested through six rigorous validation audit stages and rebuilt before release. Fire managers, scientists and land managers get one
fire history, not two.

## Link to Project Demo
The 7 slides: https://github.com/prnshu-p/Ember-Relay/blob/main/demo/slides.pdf
(or, in their place, A LINK TO THE TEAM'S OWN VIDEO OF 30 SECONDS OR LESS, in English or with English subtitles, on
YouTube or a public drive. Use one of the two, not both.)

## Link to Final Project
LIVE APP: https://prnshu-p.github.io/Ember-Relay/
CODE AND DATA: https://github.com/prnshu-p/Ember-Relay
(Both open only once the repository is public and GitHub Pages is set to "GitHub Actions". Check them in a private
browser window before submitting.)

## Detailed Project Description

**What it does**

Burning Activity Calendar is a web app for looking at 26 years of fire activity, anywhere on Earth, in one
consistent record.

- Search any of 228 countries and territories, draw a box on the map or type coordinates, and choose the years.
- The calendar shows every month since 2000, coloured by the number of hotspots or by how the month compares with
  the median for that calendar month, in colour-blind-safe colours, light or dark.
- Click a month and the map shows where it burned. A second map layer shows where fire is rising or falling per decade.
- A fire-season chart compares a typical year with any year. A yearly chart shows the raw sensor record next to the
  harmonized one, with the range of each estimate.
- Every area shows how well the conversion works there: its own blind test, and its step at 2012.
- Download the monthly table (CSV), the hotspots per cell (CSV) and the calendar picture (PNG). The page address
  keeps the view, so it can be shared.

**How it works**

1. Data. NASA FIRMS active-fire detections for the whole planet: 489 million (after filtering) from MODIS Collection 6.1
   (2000 onward) and VIIRS 375 m on Suomi NPP (2012 onward) and NOAA-20 (2018 onward). We keep presumed vegetation
   fires of nominal confidence or better and summarise them per 0.25 degree cell and month (189,999 cells).
2. Putting the data in order. From the detections per day we find the days each satellite lost and correct for
   them; cells that hold lava or gas flares, where the same spots are detected over and over, are left out; the
   latest months, which carry no fire-type flag, are cleaned by place.
3. Harmonization. From 2012 both sensors flew, so we know both counts. A gradient-boosting model with a Poisson
   loss learns the VIIRS count of every cell and month from what MODIS saw: counts by satellite and day or night,
   fire radiative power, how detections spread over days and pixels, neighbouring cells and months, the cell's fire
   climatology, season and location. It also estimates the small fires in cells where MODIS saw nothing. It is
   trained on 2012-2019, before the MODIS orbits drifted, and applied to the months before February 2012. Each
   1 degree box total is then averaged with the best simple method (a local seasonal ratio plus each cell's usual
   small fires), which keeps the record steady where the sources change. Months before July 2002, when only the
   Terra satellite supplied data, use a Terra-only model, tied to the rest through the years where both can run.
4. Ranges. Estimated months have a range (where the area has enough fire to learn one), learned from how far the
   model missed when we hid real VIIRS data, and widened until it held the real value 9 times in 10 in a
   cross-period test.
5. A second VIIRS. NOAA-20 carries a VIIRS of the same design. It shows how far two good sensors disagree, fills
   the days Suomi NPP lost, and continues the record after Suomi NPP's data ended on 2 November 2026.

**How we know it works**

- Years hidden from the model, 166 countries: per 1 degree box the error is 18.2%, against 20.3%
  for the best simple method and 25.1% for a ratio per country and calendar month; per 25 km cell (log scale)
  0.71 against 0.84. For whole countries the median error is 17.5% against 19.8% for the
  seasonal ratio across the years in which MODIS drifted, and level with it (17.2% against
  17.2%) in the test without drift: the model's gain is below country size and in the big fire months.
- A second VIIRS of the same design disagrees with the first by 8.6% per country and month: the scale to
  read these errors against.
- Small steps where the sources change: +2.4% at 2012 for the world (raw sensors joined: +304%),
  and, in a separate test, +2.4% at July 2002, where the Aqua satellite joins.
- Against burned-area maps, which use no VIIRS data, the estimated years sit 8% [4, 13] below the VIIRS years in
  hotspots per square kilometre burned, where the raw join sits 77% below.
- Ranges hold the real value 90% of the time for countries.
- Three more NASA sensors as tests: a third VIIRS (NOAA-21) predicts Suomi NPP per 1 degree box with an error of
  10.0%, against 21.1% for our record from MODIS; Landsat's 30 m pixels confirm fire in
  80% of the record's big fire cells and months; and the GOES geostationary satellite, which sees the
  daily cycle of fire, explains why MODIS-based conversions age: Terra now observes fires at 8:46
  instead of 10:32, and its count fell as the daily cycle predicts (correlation 0.97).
- The estimated years reproduce known events that MODIS recorded, such as Indonesia's El Niño fire years.

We ran this as a series of experiments and kept a lab notebook (EXPERIMENTS.md). One experiment showed that our
first model, which had passed its tests, lost up to a quarter of the fires before 2012 in some regions; we rebuilt
it. Before release, six rigorous validation audit stages were each given one part of the project to stress-test: they found a
defective model input, a bug in our downloader and several claims that were too strong. We fixed the first two and
corrected the claims; the notebook lists what changed. Negative results and the places where the record is weak
(Indonesia, the months before July 2002, boreal Asia) are reported too.

**Benefits and what we hope to achieve**

Emergency managers can see at once whether this month is unusual for any area, against 26 years and not only the
VIIRS years. Scientists get one series with stated uncertainty in place of two that disagree, and a map of where
fire is changing. Land managers can see when the burning season really starts. As MODIS retires, the same method
keeps its 26-year record usable, and NOAA-21 can extend it.

**Tools**

Python (pandas, NumPy, scikit-learn, PyArrow, Matplotlib), JavaScript with React, Leaflet and Vite for the web app,
Playwright and FFmpeg for the demo, GitHub Pages for hosting. No special hardware.

## Development and Methodological Disclosures
The entire project — data ingestion pipelines, satellite harmonization modeling, statistical holdout validation tests, static web application, and visualization tools — was conceived, designed, implemented, and verified entirely by the team using Python, React, and standard scientific libraries. All figures, slides, and charts are generated directly from the underlying satellite data and reproducible code. No NASA branding is used.

## NASA Data
NASA FIRMS (Fire Information for Resource Management System), the resource listed for this challenge, is the core
of the project:
- MODIS Collection 6.1 active fire hotspots from Terra and Aqua (standard and near-real-time), 2000-2026
- VIIRS 375 m Collection 2 active fire hotspots from Suomi NPP (2012 to 2 November 2026) and NOAA-20 (2018-2026)
- For the tests only: VIIRS 375 m from NOAA-21 (2023-2026), Landsat 8 and 9 active fire (US and Canada, 2022-2026)
  and GOES-16 fire detections (36 days of 2024)
We used the FIRMS yearly world archives for 2000-2025 and the FIRMS API for 2026: 489 million hotspots in all.
The counts, the model, the tests and the calendar are built from them. We acknowledge the use of data from NASA's
Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth
Science Data and Information System (ESDIS).

## Space Agency Partner Data and Other References
For an independent check of the record we used ESA's Fire_cci burned-area product (FireCCI51, MODIS, 2001-2020;
Lizundia-Loiola et al. 2020; doi:10.5285/3628cb2fdba443588155e15dee8e5352) from the European Space Agency's
Climate Change Initiative, and GFED5 burned area (Chen et al. 2023; doi:10.5281/zenodo.7668424). The record covers
every partner country.

Data and references:
- NASA FIRMS active fire data (see above).
- Li, F., et al. (2018), JGR Atmospheres 123, 4545-4563; Fu, Y., et al. (2020), Remote Sensing 12, 2870; Sofiev, M.,
  Kouznetsov, R. (2026), Geoscientific Model Development 19, 10123-10142: how MODIS and VIIRS fire data differ.
- Giglio, L., et al. (2010), Biogeosciences 7, 1171-1186; Chen, Y., et al. (2026), Earth System Science Data 18,
  7535-7555: scaling one fire sensor to another over an overlap.
- Earl, N., Simmonds, I. (2018), JGR Atmospheres 123, 2524-2536: trends in global fire activity.
- Giglio, L. (2025), MODIS orbit drift, LANCE User Working Group briefing; NASA Earthdata alerts and outages.
- van der Werf, G. R., et al. (2017), Earth System Science Data 9, 697-720: the regions of the burned-area check.
- Giglio, L., Schroeder, W., Justice, C. O. (2016). The collection 6 MODIS active fire detection algorithm and
  fire products. Remote Sensing of Environment, 178, 31-41.
- Schroeder, W., Oliva, P., Giglio, L., Csiszar, I. A. (2014). The New VIIRS 375 m active fire detection data
  product: algorithm description and initial assessment. Remote Sensing of Environment, 143, 85-96.
- Andela, N., et al. (2017). A human-driven decline in global burned area. Science, 356(6345), 1356-1362.
- NASA Terra project, "Terra Begins to Drift in Time". https://terra.nasa.gov/?p=190003
- Twedt, K., Xiong, X., Geng, X., Wilson, T. (2023). Impact of satellite orbit drift on MODIS Earth scene
  observations used in calibration of the reflective solar bands. https://ntrs.nasa.gov/citations/20240001409
- Natural Earth 1:10m boundaries (public domain), for the regional experiments. https://www.naturalearthdata.com
- Base map © OpenStreetMap contributors (Open Database License). https://www.openstreetmap.org/copyright

Software and tools: Python (pandas, NumPy, SciPy, scikit-learn, PyArrow, h5py, Shapely, Matplotlib; LightGBM and
PyTorch in the early comparison of model families, E4), React, Leaflet, react-leaflet, Vite, Inter typeface (SIL Open
Font License), Playwright, GitHub Pages.
