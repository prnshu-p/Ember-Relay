# Ember-Relay

**NASA Space Apps Challenge 2026 · Harmonization of MODIS and VIIRS Hot Spots**

Ember-Relay harmonizes 26 years of NASA MODIS and VIIRS satellite active fire detections into a single, continuous, sensor-agnostic planetary fire calendar at 0.25° (25 km) resolution.

## Team
- **Pranshu Patel** (@prnshu-p) - Machine Learning & Planetary Data Pipeline
- **Bhardwaj Thummar** (@BhardwajThummar) - Full-Stack GIS, Visualization & Frontend

## The Challenge
MODIS (Terra & Aqua) has provided continuous global fire records since late 2000. In 2012, VIIRS (Suomi-NPP & NOAA-20) introduced 375 m resolution imagery, detecting roughly 4× more hotspots. A raw join of the two time series creates an artificial +304% jump at the 2012 boundary. Ember-Relay models the relationship across space and time to produce consistent VIIRS-equivalent records spanning November 2000 to the present.

## Architecture Plan
- `pipeline/`: Data ingestion, spatial binning, outage correction, and ML harmonization.
- `frontend/`: Interactive React + Leaflet web application with monthly calendar matrix and fire season analytics.
- `docs/`: Technical writeups, validation experiments, and Space Apps submission package.
