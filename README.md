# BayesTransitEquity

**Bayesian spatial modeling of transit accessibility and equity** for urban neighborhoods. The project joins **GTFS** schedule data, **census** demographics, and **r5py**-based accessibility on a walking network, then fits **tract-level hierarchical spatial models** (PyMC) to quantify uncertainty in job access and "transit desert" risk. Results feed an interactive **Next.js** map dashboard (posterior curves, scenarios, neighbor comparison).

---

## Table of contents

1. [Problem & scope](#problem--scope)
2. [Self-assessment (rubric checklists)](#self-assessment-rubric-checklists)
3. [Quick start](#quick-start)
4. [Installation & environment](#installation--environment)
5. [Data access](#data-access)
6. [Running the analysis pipeline](#running-the-analysis-pipeline)
7. [Dashboard (`app/`)](#dashboard-app)
8. [Repository layout](#repository-layout)
9. [Expected outputs](#expected-outputs)
10. [Roadmap & limitations](#roadmap--limitations)

---

## Problem & scope

**Question:** Where is access to jobs (and related services) via transit likely insufficient, and how uncertain are those estimates once we pool information across similar neighborhoods?

**Approach:** Build tract-level accessibility covariates from GTFS + routing; combine with ACS disadvantage indicators; fit a Bayesian model with spatial structure; communicate posterior uncertainty and scenario-style contrasts on a map and in notebooks.

**What this repo is not:** A production transit agency API, a real-time GTFS-RT system, or a substitute for on-the-ground service planning. See [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md) for explicit scope and sensitivity notes.

---

## Self-assessment (rubric checklists)

Use this block for **course or proposal reviews**. *Must-Have* items are marked **MH**. Count only boxes you treat as done; adjust if your instructor defines "Must-Have" differently.

Legend: **Done** uses &#9989; when the item is satisfied and &#9744; when it is still a gap.

### Progress against proposal plan

| Done | Checklist item | MH |
|:---:|:---|:---:|
| &#9989; | Core components from proposal implemented (pipeline notebooks, `src/`, dashboard) | **MH** |
| &#9989; | Code beyond scaffolding / placeholders | **MH** |
| &#9989; | Proposal milestones reflected in repo (numbered `01`–`07` notebooks + EDA folder) | **MH** |
| &#9989; | Testing or evaluation scripts present (`scripts/*.py`, notebook diagnostics, ArviZ in `04`–`05`) | |
| &#9989; | Outputs / logs / results present (`artifacts/`, export scripts; large binaries gitignored per `.gitignore`) | |
| &#9989; | Clear forward roadmap (`configs/ASSUMPTIONS.md`, [Roadmap § below](#roadmap--limitations), `app/README.md`) | |

**Boxes checked:** **6 / 6**  
**Grade:** **A** (≥5 and all MH met)

---

### README quality & reproducibility

| Done | Checklist item | MH |
|:---:|:---|:---:|
| &#9989; | Clear problem description ([§ Problem](#problem--scope)) | **MH** |
| &#9989; | Installation instructions ([§ Installation](#installation--environment)) | **MH** |
| &#9989; | Dependency list with versions ([environment.yml](environment.yml), [requirements.txt](requirements.txt), [app/package.json](app/package.json)) | **MH** |
| &#9989; | Environment setup instructions (conda recommended; JDK note for r5py) | |
| &#9989; | Dataset access instructions ([§ Data access](#data-access)) | **MH** |
| &#9989; | Exact commands to run experiments ([§ Pipeline](#running-the-analysis-pipeline), [app/README.md](app/README.md)) | **MH** |
| &#9989; | Expected outputs described ([§ Expected outputs](#expected-outputs)) | |
| &#9989; | Directory structure explained ([§ Repository layout](#repository-layout)) | |

**Boxes checked:** **8 / 8**  
**Grade:** **A** (≥6 and all MH met)

---

### Repository organization & engineering

| Done | Checklist item | MH |
|:---:|:---|:---:|
| &#9989; | Logical directory structure | **MH** |
| &#9989; | Separation of code / data / results (`src/`, `scripts/`, `data/*`, `artifacts/`, gitignore rules) | |
| &#9989; | Modular code structure (`src/modeling/`, `src/utils/`) | **MH** |
| &#9989; | Meaningful file names (numbered pipeline, EDA README index) | |
| &#9989; | Use of `.gitignore` (raw/interim data, `node_modules`, secrets, checkpoints) | |
| &#9989; | Requirements file present ([environment.yml](environment.yml), [requirements.txt](requirements.txt)) | **MH** |

**Boxes checked:** **6 / 6**  
**Grade:** **A** (≥5 and all MH met)

---

### Contribution history & teamwork

| Done | Checklist item | MH |
|:---:|:---|:---:|
| &#9744; | Contributions from **all** team members visible in git history | **MH** |
| &#9989; | Commits distributed across multiple weeks (e.g. activity spanning project weeks) | |
| &#9744; | Consistently meaningful commit messages (improve as you polish for submission) | |
| &#9744; | Reasonable commit size distribution (avoid single bulk dump right before deadline) | |
| &#9744; | Evidence of collaboration (PRs, reviews, shared branches); use GitHub if the course requires it | |

**Boxes checked:** **1 / 5** (example for a **single-author** clone; **update this table** if your team adds authors)  
**Grade:** **C** on this axis until multi-author history and collaboration evidence exist. This is **not** a comment on code quality.

---

### Testing & validation evidence

| Done | Checklist item | MH |
|:---:|:---|:---:|
| &#9989; | Evaluation metrics implemented (model diagnostics, distances, equity summaries in notebooks + dashboard) | **MH** |
| &#9989; | Results saved or reproducible (notebooks to `artifacts/`; export scripts; frontend GeoJSON pipeline) | **MH** |
| &#9744; | Unit tests in `tests/` (pytest is listed in [requirements.txt](requirements.txt); suite not yet populated) | |
| &#9744; | Tests runnable automatically in CI (`pytest`, GitHub Actions, etc.) | |
| &#9744; | Central experiment logs / MLflow-style tracking | |

**Boxes checked:** **2 / 5**  
**Grade:** **C** on this rubric row: core **MH** items (metrics + reproducible artifacts) are covered; automation is the gap.

---

### Rubric-style checklist (copy for the syllabus)

If your grader wants literal empty/check marks, you can paste this block and fill counts by hand:

```
Progress (6): [x][x][x][x][x][x]  -> 6/6
README (8):          [x][x][x][x][x][x][x][x]  -> 8/8
Repo org (6):        [x][x][x][x][x][x]  -> 6/6
Teamwork (5):        [ ][x][ ][ ][ ] -> update when multi-author
Testing (5):         [x][x][ ][ ][ ]     -> add tests/ + CI to raise
```

---

## Quick start

```bash
# 1) Python environment (recommended)
conda env create -f environment.yml
conda activate bayestransit

# 2) Download / refresh data (see configs/san_diego.yaml)
python scripts/download_data.py --config configs/san_diego.yaml

# 3) Run pipeline notebooks in order: notebooks/01_ ... 07_ ... (Jupyter)

# 4) Optional: regenerate dashboard assets
python scripts/export_frontend.py

# 5) Dashboard
cd app && npm install && npm run dev
```

Java (JDK) may be required for **r5py** in notebook `03`; set `JAVA_HOME` if the kernel cannot find a JVM.

---

## Installation & environment

| Path | Role |
|------|------|
| [environment.yml](environment.yml) | **Preferred:** Conda, Python 3.12, conda-forge pins (NumPy 2.x-friendly). |
| [requirements.txt](requirements.txt) | Pip fallback + commentary on NumPy / PyMC wheel issues. |
| [app/package.json](app/package.json) | Next.js 15, React 18, Deck.gl 9, MapLibre, Visx. |

---

## Data access

- **Config:** [configs/san_diego.yaml](configs/san_diego.yaml) — study **bbox**, GTFS via Mobility Database id, paths for LODES, OSM, optional `.osm.pbf` for r5py.
- **Downloader:** `python scripts/download_data.py --config configs/san_diego.yaml [--sources ...]`
- **Ignored by git (typical):** `data/raw/`, `data/interim/`, large model checkpoints under `data/processed/posteriors/` — see [.gitignore](.gitignore). You **generate** these locally or in shared storage; the repo documents **how**, not multi-GB binaries.

Assumptions and known data caveats (e.g. feed freshness) are tracked in [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md).

---

## Running the analysis pipeline

**Main sequence** (strict order; each notebook builds inputs for the next):

| Step | Notebook | Focus |
|------|----------|--------|
| 01 | [notebooks/01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb) | Data inventory, exploratory joins |
| 02 | [notebooks/02_gtfs_processing.ipynb](notebooks/02_gtfs_processing.ipynb) | GTFS cleaning / features |
| 03 | [notebooks/03_accessibility_computation.ipynb](notebooks/03_accessibility_computation.ipynb) | r5py accessibility |
| 04 | [notebooks/04_bayesian_model.ipynb](notebooks/04_bayesian_model.ipynb) | PyMC model fit |
| 05 | [notebooks/05_posterior_analysis.ipynb](notebooks/05_posterior_analysis.ipynb) | Posterior summaries |
| 06 | [notebooks/06_equity_decomposition.ipynb](notebooks/06_equity_decomposition.ipynb) | Equity decomposition |
| 07 | [notebooks/07_intervention_simulation.ipynb](notebooks/07_intervention_simulation.ipynb) | Intervention-style scenarios |

**Exploratory only:** [notebooks/eda/](notebooks/eda/) — see [notebooks/eda/README.md](notebooks/eda/README.md) for order and exports.

**Helper scripts** (repo root, with env activated):

```bash
python scripts/download_data.py --config configs/san_diego.yaml
python scripts/export_frontend.py
python scripts/nb04_export_diagnostics.py --help
python scripts/extract_osm_pbf.py --help
```

---

## Dashboard (`app/`)

Interactive map and tract panel (posteriors, scenarios, **neighbor comparison** with Gaussian JSD ranking). Details: [app/README.md](app/README.md).

```bash
cd app
npm install
npm run dev    # http://localhost:3000
npm run build  # static export to app/out/
```

---

## Repository layout

| Path | Purpose |
|------|---------|
| `configs/` | YAML study config, [ASSUMPTIONS.md](configs/ASSUMPTIONS.md) |
| `notebooks/` | Pipeline `01`–`07` + `eda/` explorations |
| `src/` | Shared Python: modeling (`tract_bym`, spatial), GTFS/r5 helpers, config paths |
| `scripts/` | CLI: downloads, frontend export, diagnostics, OSM PBF extract |
| `app/` | Next.js dashboard + `public/data/` GeoJSON |
| `artifacts/` | Exported tables/figures (see [artifacts/tables/README.md](artifacts/tables/README.md)) |
| `data/` | Local processed/raw data (most **not** committed; see `.gitignore`) |

---

## Expected outputs

- **Tables / figures:** Under `artifacts/tables/` and `artifacts/figures/` with naming conventions described in [artifacts/tables/README.md](artifacts/tables/README.md).
- **Posterior checkpoints:** Notebook `04` may write NetCDF under `data/processed/posteriors/` (gitignored when large); paths depend on notebook cells and config.
- **Frontend:** `python scripts/export_frontend.py` refreshes `app/public/data/*.geojson`, `metadata.json`, `neighbors.json`, scenarios.

If a path is missing, run the preceding pipeline notebook or the downloader first.

---

## Roadmap & limitations

Documented priorities and caveats:

- **Modeling / data:** [configs/ASSUMPTIONS.md](configs/ASSUMPTIONS.md) (Phase 2 GTFS-RT, threshold sensitivity, feed freshness).
- **Dashboard MVP gaps:** [app/README.md](app/README.md) (e.g. URL hash persistence, mobile layout).
- **Testing:** Add `tests/` + CI when the course requires automated checks; pytest is already a declared dependency.

For grading: **update the [Contribution](#contribution-history--teamwork) and [Testing](#testing--validation-evidence) tables** to match your team's git history and any CI you add.

---

## License / citation

Add your course or project license and citation text here if required by your program.
