# BayesTransitEquity

Bayesian spatial modeling of **transit accessibility** and **equity** at the census-tract level for a San Diego County study area. The workflow pulls **GTFS** schedules, **ACS** demographics, and **r5py** routing on a pedestrian network, then fits **PyMC** models with spatial structure. Outputs include notebooks, CSV/PNG artifacts, tract GeoJSON, and a **Next.js** map app (posterior curves, scenarios, neighbor comparison).

---

## Table of contents

1. [What you can look at without rerunning anything](#what-you-can-look-at-without-rerunning-anything)
2. [How to reproduce results end-to-end](#how-to-reproduce-results-end-to-end)
3. [Environment setup](#environment-setup)
4. [Data: where it lives and how to fetch it](#data-where-it-lives-and-how-to-fetch-it)
5. [Analysis pipeline (notebooks)](#analysis-pipeline-notebooks)
6. [Python `scripts/` (CLI helpers)](#python-scripts-cli-helpers)
7. [Python `src/` (importable modules)](#python-src-importable-modules)
8. [Dashboard `app/`](#dashboard-app)
9. [Configs](#configs)
10. [Artifacts and logs](#artifacts-and-logs)
11. [What `.gitignore` excludes](#what-gitignore-excludes)
12. [Further reading](#further-reading)

---

## What you can look at without rerunning anything

- **Paper-style tables and figures**  
  - Tables: `artifacts/tables/eda/` and `artifacts/tables/pipeline/` (see [artifacts/tables/README.md](artifacts/tables/README.md) for naming: `eda__…` vs `pipeline__…`).  
  - Figures: `artifacts/figures/` (PNG).  
  - Run logs / provenance JSON: `artifacts/logs/provenance/`.

- **Interactive map (if dashboard data is present)**  
  - The app reads from `app/public/data/` (GeoJSON, `metadata.json`, `neighbors.json`, scenario layers). If those files exist after a clone or after you run `scripts/export_frontend.py`, start the app (see [Dashboard `app/`](#dashboard-app)) and open the map in a browser.

- **Notebook outputs**  
  - Open `notebooks/01_…` through `07_…` in Jupyter and scroll saved outputs (cells may already contain plots and tables if the notebook was executed and saved).

Large raw downloads, interim files, and posterior NetCDF checkpoints are usually **not** in git; see [What `.gitignore` excludes](#what-gitignore-excludes).

---

## How to reproduce results end-to-end

From the repository root, in order:

1. **Create the Python environment** (see [Environment setup](#environment-setup)).
2. **Fetch data** (GTFS, census-related inputs, OSM as needed):  
   `python scripts/download_data.py --config configs/san_diego.yaml`  
   Use `--sources …` for partial refreshes; r5py needs an OSM **`.osm.pbf`** clip—commands and paths are documented in [configs/san_diego.yaml](configs/san_diego.yaml) and the downloader help.
3. **Run the main pipeline notebooks in sequence** (strict order):  
   `notebooks/01_data_exploration.ipynb` → `02_gtfs_processing.ipynb` → `03_accessibility_computation.ipynb` → `04_bayesian_model.ipynb` → `05_posterior_analysis.ipynb` → `06_equity_decomposition.ipynb` → `07_intervention_simulation.ipynb`.  
   Notebook `03` uses **r5py** and typically needs a **Java JDK** (`JAVA_HOME` if the JVM is not found).
4. **Optional EDA** (any order; does not replace the main pipeline): `notebooks/eda/` — index in [notebooks/eda/README.md](notebooks/eda/README.md).
5. **Regenerate frontend layers** (after processed tract GeoJSON / scenarios exist):  
   `python scripts/export_frontend.py`
6. **Run the dashboard**: `cd app && npm install && npm run dev` — see [app/README.md](app/README.md).

If a notebook fails for a missing path, compare your `data/` tree to what earlier steps produce; most failures are “run the previous notebook first” or “download missing source.”

---

## Environment setup

| File | Purpose |
|------|---------|
| [environment.yml](environment.yml) | **Recommended:** conda env `bayestransit`, Python 3.12, conda-forge stack + pip packages (`r5py`, `osmnx`, etc.). |
| [requirements.txt](requirements.txt) | Pip-oriented install and notes on NumPy / compiled wheels if you avoid conda. |
| [app/package.json](app/package.json) | Node dependencies for the Next.js dashboard. |

Create and activate the conda env:

```bash
conda env create -f environment.yml
conda activate bayestransit
```

---

## Data: where it lives and how to fetch it

- **Single study config:** [configs/san_diego.yaml](configs/san_diego.yaml) — bbox, GTFS agency ids (Mobility Database), census year, **r5** OSM PBF path, departure time for accessibility, chunk sizes.
- **Shared defaults:** [configs/defaults.yaml](configs/defaults.yaml) — global defaults merged with the city YAML.
- **Downloader:** `python scripts/download_data.py --config configs/san_diego.yaml`  
  Populates paths under `data/raw/` (and related interim paths as implemented in the script). See script docstrings and `--help` for `--sources` (e.g. `gtfs`, `osm`, `osm_pbf`).

Modeling assumptions and data caveats (feeds, thresholds, Phase 2 scope) are written up in [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md).

---

## Analysis pipeline (notebooks)

| Notebook | Role |
|----------|------|
| [notebooks/01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb) | Inventory and exploratory joins; orients you to inputs. |
| [notebooks/02_gtfs_processing.ipynb](notebooks/02_gtfs_processing.ipynb) | GTFS processing and tract-level transit features. |
| [notebooks/03_accessibility_computation.ipynb](notebooks/03_accessibility_computation.ipynb) | Accessibility via **r5py** (needs JVM + OSM PBF per config). |
| [notebooks/04_bayesian_model.ipynb](notebooks/04_bayesian_model.ipynb) | **PyMC** model fit; may write large posterior files under `data/processed/` (see `.gitignore`). |
| [notebooks/05_posterior_analysis.ipynb](notebooks/05_posterior_analysis.ipynb) | Posterior summaries, maps, exports to `artifacts/`. |
| [notebooks/06_equity_decomposition.ipynb](notebooks/06_equity_decomposition.ipynb) | Equity metrics and decomposition analyses. |
| [notebooks/07_intervention_simulation.ipynb](notebooks/07_intervention_simulation.ipynb) | Intervention / scenario-style simulation and tables for downstream use. |

**EDA folder:** [notebooks/eda/](notebooks/eda/) — exploratory-only notebooks; not a substitute for `01`–`07`.

---

## Python `scripts/` (CLI helpers)

| Script | Role |
|--------|------|
| [scripts/download_data.py](scripts/download_data.py) | Download or refresh GTFS, OSM, LODES-related inputs, optional Geofabrik PBF steps—driven by YAML config. |
| [scripts/export_frontend.py](scripts/export_frontend.py) | Build/update GeoJSON and JSON under `app/public/data/` for the map app. |
| [scripts/nb04_export_diagnostics.py](scripts/nb04_export_diagnostics.py) | Export diagnostics from notebook04 posterior artifacts (`--help` for NetCDF / run id options). |
| [scripts/extract_osm_pbf.py](scripts/extract_osm_pbf.py) | Clip a regional `.osm.pbf` to the study area for r5py (when not using the downloader path). |

Run from repo root with the conda env activated.

---

## Python `src/` (importable modules)

| Module / path | Role |
|---------------|------|
| [src/utils/config.py](src/utils/config.py) | Load and merge YAML configs. |
| [src/utils/paths.py](src/utils/paths.py) | Central path helpers for the project layout. |
| [src/utils/gtfs_r5.py](src/utils/gtfs_r5.py) | GTFS packaging / r5-related utilities used in the pipeline. |
| [src/modeling/tract_bym.py](src/modeling/tract_bym.py) | Tract-level BYM / modeling pieces used with PyMC. |
| [src/modeling/spatial.py](src/modeling/spatial.py) | Spatial weights / adjacency helpers (e.g. Queen contiguity). |

Notebooks import these modules; keep `src/` on `PYTHONPATH` by running Jupyter from the repo root (normal for this layout).

---

## Dashboard `app/`

Next.js 15 + MapLibre + Deck.gl + Visx. Map and tract side panel: baselines, scenarios, posterior plots, neighbor comparison (Gaussian surrogates + JSD ranking).

```bash
cd app
npm install
npm run dev
```

Open `http://localhost:3000` (optional: `/?geoid=…` for a tract). Production static export: `npm run build` → output under `app/out/`. Data contract and file list: [app/README.md](app/README.md).

---

## Configs

| File | Role |
|------|------|
| [configs/san_diego.yaml](configs/san_diego.yaml) | City bbox, GTFS, census, r5 OSM PBF paths, routing parameters. |
| [configs/defaults.yaml](configs/defaults.yaml) | Shared defaults merged into city config. |
| [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md) | Documented modeling and data assumptions, sensitivities, known limitations. |

---

## Artifacts and logs

| Location | Role |
|----------|------|
| `artifacts/tables/eda/` | CSV exports from EDA notebooks (`eda__*__<date>.csv`). |
| `artifacts/tables/pipeline/` | CSV exports from pipeline notebooks (`pipeline__*__…`). |
| `artifacts/figures/` | Exported PNG figures (often tied to a notebook / model id in the filename). |
| `artifacts/logs/provenance/` | JSON manifests / provenance for data and runs. |
| [artifacts/tables/README.md](artifacts/tables/README.md) | Short index of subfolders and naming. |

`artifacts/models/` is listed in `.gitignore` for heavy model binaries—use local or shared storage if you generate large files there.

---

## What `.gitignore` excludes

Typical clones will **not** contain everything needed to run `04`–`07` without downloads. Ignored or partially ignored paths include:

- `data/raw/`, `data/interim/`, `data/processed/posteriors/`
- `cache/`, `*.zip`, local `context/`, `.claude/`
- `node_modules/`, `app/.next/`
- secrets: `*.env`, `secrets.yaml`, etc.

Regenerate ignored data with `scripts/download_data.py` and the notebooks, or obtain dumps from a teammate / release if your course allows that.

---

## Further reading

- [notebooks/eda/README.md](notebooks/eda/README.md) — EDA notebook order and what to export.  
- [app/README.md](app/README.md) — dashboard data files and dev/build commands.  
- [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md) — scope, thresholds, feed freshness, Phase 2 notes.

Add a license or citation here if your program requires it.
