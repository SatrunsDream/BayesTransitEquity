# BayesTransitEquity
A Bayesian spatial analysis of urban transit accessibility. This project combines GTFS transit data, census demographics, and geospatial networks to measure access to jobs and essential services across city neighborhoods. Hierarchical Bayesian models and spatial analysis are used to detect underserved areas and quantify uncertainty in accessibility estimates. Results are presented through interactive maps and dashboards.

## Data layout (quick reference)

- **Study extent** — `bbox` in `configs/san_diego.yaml` (single source of truth for scripts and the main pipeline).
- **Exploratory notebooks** — `notebooks/eda/` (01–07): diagnostics only; run in any order for exploration, but **re-run spatial notebooks after bbox changes**.
- **Analysis pipeline** — `notebooks/01_data_exploration.ipynb` through `07_intervention_simulation.ipynb` at repo root: strict sequence; feeds `src/` and `data/processed/`.
- **Downloads** — `python scripts/download_data.py --config configs/san_diego.yaml` (see `--sources`). LODES WAC lands at `data/raw/external/lodes/ca_wac_2021.csv.gz`. OSM walk network (EDA): `data/raw/osm/sd_walk_network.graphml` (re-fetch with `--sources osm --force` after changing `bbox`). **r5py** needs a separate **`.osm.pbf`** clip at `r5.osm_pbf` in `configs/san_diego.yaml` — build with `python scripts/download_data.py --config configs/san_diego.yaml --sources osm_pbf --download-geofabrik-ca` (requires [osmium-tool](https://osmcode.org/osmium-tool/)) or `python scripts/extract_osm_pbf.py --input <path-to-california-latest.osm.pbf>`.
