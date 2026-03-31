# Exploratory data analysis (`notebooks/eda/`)

This folder holds **EDA only**. The main analysis pipeline stays in `notebooks/` as `01_…` through `07_…` so numbering never collides.

**Order:** inventory and provenance first, then per-source exploration, then cross-source integration.

---

## Notebooks

| Notebook | Focus |
|----------|--------|
| `01_inventory_and_provenance.ipynb` | What exists on disk, feed versions, download dates, paths from `configs/`, sizes/checksums or manifests. Ties to `context/DATASETS.md`. |
| `02_gtfs_schedule_exploration.ipynb` | MTS + NCTD schedule quality: routes, stops, trips, calendars, spatial extent vs bbox, **per-route / agency-level frequency** summaries. |
| `03_census_tracts_and_acs.ipynb` | TIGER tracts for the study area, ACS need variables (vehicle access, poverty, disability, income, etc.). **Primary EDA result for the paper:** test whether **ACS margin of error (MOE) covaries with demographic disadvantage**—e.g. uncertainty is largest where need is highest. That pattern is the empirical motivation for **Bayesian partial pooling** in `notebooks/04_bayesian_model.ipynb`. Maps/tables supporting that claim should be exported to `artifacts/`. |
| `04_spatial_alignment_and_coverage.ipynb` | Tracts vs GTFS footprint, service gaps, boundary/buffer issues. **Hygiene (top of notebook):** CRS consistency, shared CRS for all layers, obvious boundary fixes. **Analytic core:** tract-level **service experienced** summaries that bridge GTFS → model covariates—e.g. stops per tract, distance to network, **weighted headway / frequency aggregated to tract** (derived from `02` logic). **Export** the tract-level service summary to `artifacts/tables/` (artifact index in `context/structure.md`); pipeline `04_bayesian_model.ipynb` can consume it as an input. |
| `05_osm_pedestrian_network.ipynb` | OSM walk graph inside bbox: extent, connectivity, spot-checks for weak coverage (first/last mile). |
| `06_opportunities_and_destinations.ipynb` | **LODES** (jobs — heavier lift) plus **destinations aligned with `configs/defaults.yaml`** (`jobs`, `hospitals`, `groceries`, `schools`): pull hospitals/groceries/schools from **OSM** (and document tags/cleaning). Distribution, counts, spatial coverage. |
| `07_cross_source_sanity_joins.ipynb` | Lightweight joins across sources. **Hygiene:** repeat CRS/bounds checks if needed. **Named analytic output:** **tracts with zero (or very few) stops within X km** — directly supports transit-desert framing. Export that table to `artifacts/tables/` and index it. Optional: other crosswalks; keep full **r5py** accessibility runs in pipeline `03_accessibility_computation.ipynb` unless you add a tiny smoke test here. |

---

## Phase 2 (not in this folder)

**GTFS-Realtime / reliability** is deferred; see `context/ASSUMPTIONS.md`, decisions in `context/DECISIONS.md`, and tracking in `context/STATUS.md`. **Do not** add an empty EDA stub—add a notebook only when Phase 2 starts.

---

## Artifacts

EDA exports go to `artifacts/figures/` and `artifacts/tables/` with run IDs per `context/development_rules.md`. Document each reportable table/figure in `context/structure.md` (artifact index).

## Bbox changes (D009 / county-wide window)

Spatial EDA notebooks (`02`, `04`–`07`) must use the **same** bounding box as `configs/san_diego.yaml` (load from YAML rather than hardcoding). After expanding the bbox, **re-run 04–07** so tract overlap counts, stop coverage, OSM stats, destinations, and cross-source tables match the pipeline. Notebook `01` will reflect the new bbox in config dumps. Pipeline notebooks at `notebooks/01`–`07` read the config directly.
