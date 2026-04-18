"""
export_frontend.py
==================
Generates the static data files consumed by the Deck.gl / Next.js dashboard.

Run once (from repo root, with the pipeline conda env active):
    python scripts/export_frontend.py

Outputs (written to app/public/data/):
    baseline.geojson              â€” already produced by nb07; just copied here
    scenarios/bayesian_top20.geojson
    scenarios/det_top20.geojson
    neighbors.json                â€” queen-contiguity adjacency list {geoid: [geoid,...]}
    metadata.json                 â€” thresholds, county summary, intervention stats
"""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# â”€â”€ Paths â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def find_repo_root() -> Path:
    start = Path(__file__).resolve().parent
    for d in [start, *start.parents]:
        if (d / "configs" / "san_diego.yaml").exists():
            return d
    raise FileNotFoundError("Could not find configs/san_diego.yaml")


REPO_ROOT = find_repo_root()
sys.path.insert(0, str(REPO_ROOT))

GEOJSON_DIR  = REPO_ROOT / "data" / "processed" / "geojson"
APP_DATA_DIR = REPO_ROOT / "app" / "public" / "data"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
(APP_DATA_DIR / "scenarios").mkdir(exist_ok=True)


# â”€â”€ 1. Copy GeoJSON files â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

print("Copying GeoJSON files â€¦")

src_files = {
    GEOJSON_DIR / "sd_tracts_equity_baseline.geojson":
        APP_DATA_DIR / "baseline.geojson",
    GEOJSON_DIR / "scenarios" / "freq_double_bayesian_top20.geojson":
        APP_DATA_DIR / "scenarios" / "bayesian_top20.geojson",
    GEOJSON_DIR / "scenarios" / "freq_double_det_top20.geojson":
        APP_DATA_DIR / "scenarios" / "det_top20.geojson",
}

for src, dst in src_files.items():
    if not src.exists():
        print(f"  WARNING: {src} not found â€” skipping")
        continue
    shutil.copy2(src, dst)
    size_mb = dst.stat().st_size / 1e6
    print(f"  {dst.name}  ({size_mb:.1f} MB)")


# â”€â”€ 1b. Enrich baseline.geojson with ACS disadvantage (for dashboard filters) â”€

baseline_path = APP_DATA_DIR / "baseline.geojson"
if baseline_path.is_file():
    print("\nEnriching baseline.geojson with disadvantage_z + disadv_quartile â€¦")
    with open(baseline_path, encoding="utf-8") as f:
        bl = json.load(f)
    acs_glob = sorted(
        REPO_ROOT.glob("artifacts/**/eda__acs_sd_tract_attributes__*.csv"),
        reverse=True,
    )
    if acs_glob:
        acs = pd.read_csv(acs_glob[0], dtype={"GEOID": str})
        acs["GEOID"] = acs["GEOID"].str.strip().str.zfill(11)
        model_geoids = {feat["properties"]["geoid"] for feat in bl["features"]}
        sub = acs[acs["GEOID"].isin(model_geoids)][["GEOID", "disadvantage_z"]].drop_duplicates(
            "GEOID"
        )
        if len(sub) > 0:
            sub = sub.copy()
            sub["disadv_quartile"] = pd.qcut(
                sub["disadvantage_z"].rank(method="first"),
                4,
                labels=[1, 2, 3, 4],
            ).astype(int)
            zmap = dict(zip(sub["GEOID"], sub["disadvantage_z"]))
            qmap = dict(zip(sub["GEOID"], sub["disadv_quartile"]))
            for feat in bl["features"]:
                gid = feat["properties"]["geoid"]
                if gid in zmap:
                    feat["properties"]["disadvantage_z"] = round(float(zmap[gid]), 4)
                    feat["properties"]["disadv_quartile"] = int(qmap[gid])
                else:
                    feat["properties"]["disadvantage_z"] = None
                    feat["properties"]["disadv_quartile"] = None
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(bl, f)
        print(f"  Updated {len(bl['features'])} features from {acs_glob[0].name}")
    else:
        print("  WARNING: no eda__acs_sd_tract_attributes__*.csv â€” skip enrichment")


# â”€â”€ 2. Build neighbors.json â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

print("\nBuilding neighbors.json â€¦")

# Load spatial.py directly â€” avoids src.modeling.__init__ â†’ pymc import in thin envs
_spatial_path = REPO_ROOT / "src" / "modeling" / "spatial.py"
_spec = importlib.util.spec_from_file_location("bayes_spatial_export", _spatial_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_spatial_path}")
_spatial = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spatial)
adjacency_from_queen = _spatial.adjacency_from_queen

# Load TIGER tract shapefile
tiger_dir = REPO_ROOT / "data" / "raw" / "census"
shp_candidates = list(tiger_dir.rglob("*.shp"))
if not shp_candidates:
    raise FileNotFoundError(f"No shapefile found under {tiger_dir}")

tracts_raw = gpd.read_file(shp_candidates[0])

# Keep only the 720 tracts that made it into the model
with open(baseline_path, encoding="utf-8") as f:
    bl = json.load(f)
model_geoids = {feat["properties"]["geoid"] for feat in bl["features"]}

tracts_gdf = tracts_raw[tracts_raw["GEOID"].isin(model_geoids)].copy()
tracts_gdf["GEOID"] = tracts_gdf["GEOID"].astype(str).str.zfill(11)
tracts_gdf = tracts_gdf.to_crs(epsg=4326)


def _neighbors_geopandas_touches(gdf_wgs84: gpd.GeoDataFrame, id_col: str) -> dict[str, list[str]]:
    """Queen-style adjacency without libpysal (shared boundary / vertex)."""
    g = gdf_wgs84.to_crs(3310)[[id_col, "geometry"]].copy()
    g[id_col] = g[id_col].astype(str).str.zfill(11)
    g["_i"] = np.arange(len(g), dtype=np.int32)
    left = g.rename(columns={id_col: "gid_a"})
    right = g.rename(columns={id_col: "gid_b", "_i": "_j"})
    pairs = gpd.sjoin(
        left[["_i", "gid_a", "geometry"]],
        right[["_j", "gid_b", "geometry"]],
        predicate="touches",
        how="inner",
    )
    pairs = pairs[pairs["_i"] != pairs["_j"]]
    raw: dict[str, set[str]] = {}
    for _, row in pairs.iterrows():
        a, b = str(row["gid_a"]), str(row["gid_b"])
        raw.setdefault(a, set()).add(b)
        raw.setdefault(b, set()).add(a)
    return {k: sorted(v) for k, v in raw.items()}


print(f"  Building adjacency for {len(tracts_gdf)} tracts â€¦")
neighbors: dict[str, list[str]] = {}
try:
    W, geoids_ord, diagnostics, _ = adjacency_from_queen(tracts_gdf, id_col="GEOID")
    for i, geoid in enumerate(geoids_ord):
        gid = str(geoid).zfill(11)
        neighbor_idxs = list(W.neighbors[i])
        neighbors[gid] = [str(geoids_ord[j]).zfill(11) for j in neighbor_idxs]
except (ImportError, ModuleNotFoundError):
    print("  libpysal unavailable â€” GeoPandas touches fallback â€¦")
    neighbors = _neighbors_geopandas_touches(tracts_gdf, "GEOID")

for gid in model_geoids:
    neighbors.setdefault(gid, [])

out_path = APP_DATA_DIR / "neighbors.json"
with open(out_path, "w") as f:
    json.dump(neighbors, f, separators=(",", ":"))
print(f"  Written: {out_path.name}  ({out_path.stat().st_size / 1024:.0f} KB)")


# â”€â”€ 3. Build metadata.json â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

print("\nBuilding metadata.json â€¦")

# Load posterior summary to derive any remaining stats
post_dir  = REPO_ROOT / "data" / "processed" / "posteriors"
RID       = "fit_raw_zscore_x"
summary   = pd.read_parquet(post_dir / f"{RID}_posterior_summary.parquet")

Q25_JOBS       = 4470
Q25_LOG1P      = math.log1p(Q25_JOBS)

# Load intervention targets to embed GEOIDs
tables_dir = REPO_ROOT / "artifacts" / "tables" / "pipeline"
targets_csv = tables_dir / f"pipeline__07_intervention_targets__{RID}.csv"
if not targets_csv.exists():
    # fallback path (nb07 may have put it without pipeline/ subfolder)
    targets_csv = REPO_ROOT / "artifacts" / "tables" / f"pipeline__07_intervention_targets__{RID}.csv"

if targets_csv.exists():
    tdf = pd.read_csv(targets_csv, dtype={"GEOID": str})
    col_id = "GEOID" if "GEOID" in tdf.columns else "geoid"
    method_col = "method" if "method" in tdf.columns else "scenario"

    def _z(g: str) -> str:
        s = str(g).strip()
        return s.zfill(11) if s.isdigit() else s

    bayesian_geoids = [
        _z(g) for g in tdf.loc[tdf[method_col] == "bayesian", col_id].tolist()
    ]
    det_geoids = [
        _z(g) for g in tdf.loc[tdf[method_col] == "deterministic", col_id].tolist()
    ]
else:
    print("  WARNING: targets CSV not found â€” deriving from baseline GeoJSON")
    feats = sorted(
        bl["features"],
        key=lambda f: f["properties"].get("exceedance_prob", 0),
        reverse=True,
    )
    bayesian_geoids = [f["properties"]["geoid"] for f in feats[:20]]
    feats2 = sorted(
        bl["features"],
        key=lambda f: f["properties"].get("posterior_mean_jobs", 999999),
    )
    det_geoids = [f["properties"]["geoid"] for f in feats2[:20]]

# wasserstein by quartile (from nb06 table if available)
wq_csv = (
    REPO_ROOT / "artifacts" / "tables" / "pipeline"
    / f"pipeline__06_wasserstein_by_disadv_quartile__{RID}.csv"
)
if not wq_csv.is_file():
    wq_csv = REPO_ROOT / "artifacts" / "tables" / f"pipeline__06_wasserstein_by_disadv_quartile__{RID}.csv"
if wq_csv.exists():
    wq = pd.read_csv(wq_csv)
    col_q = "disadv_quartile" if "disadv_quartile" in wq.columns else "quartile"
    col_m = "wasserstein_mean" if "wasserstein_mean" in wq.columns else "mean"
    q1_rows = wq[wq[col_q].astype(str).str.startswith("Q1")]
    q4_rows = wq[wq[col_q].astype(str).str.startswith("Q4")]
    q1_mean = float(q1_rows[col_m].values[0]) if len(q1_rows) else 31512.0
    q4_mean = float(q4_rows[col_m].values[0]) if len(q4_rows) else 24237.0
else:
    q1_mean, q4_mean = 31512.0, 24237.0

metadata = {
    "run_id":    RID,
    "generated": "2026-04-17",
    "county":    "San Diego County",
    "n_tracts":  720,

    # Thresholds / model scale
    "q25_threshold_jobs":   Q25_JOBS,
    "q25_threshold_log1p":  round(Q25_LOG1P, 6),

    # Color-scale config (domain on posterior_mean log1p scale)
    "color_scale": {
        "exceedance_prob": {
            "domain": [0, 0.5, 1.0],
            "colors": ["#3B82F6", "#F59E0B", "#EF4444"],
        },
        "posterior_mean": {
            "domain_min": 4.0,
            "domain_max": 12.0,
            "colors": ["#7e22ce", "#f59e0b"],
        },
        "wasserstein_dist": {
            "domain_min": 0,
            "domain_max": 90000,
            "colors": ["#e0e7ff", "#4c1d95"],
        },
    },

    # County-wide summary
    "county_summary": {
        "spearman_equity":    0.4699,
        "n_probable_deserts": 178,
        "n_ambiguous":        35,
        "hook_geoid":         "06073013317",
        "composite_deficit_n": 120,
        "wasserstein_q1_mean": round(q1_mean),
        "wasserstein_q4_mean": round(q4_mean),
        "wasserstein_county_mean": round(
            float(summary["wasserstein_dist"].mean()) if "wasserstein_dist" in summary.columns
            else 29800
        ),
    },

    # Intervention summary
    "intervention": {
        "scenario_a": {
            "id":            "bayesian_top20",
            "label":         "Bayesian Targeting",
            "description":   "20 highest-exceedance tracts identified by Bayesian model",
            "n_targets":     20,
            "n_crossings":   12,
            "pct_pop_served": 1.99,
        },
        "scenario_b": {
            "id":            "det_top20",
            "label":         "Deterministic Targeting",
            "description":   "20 lowest-deterministic-jobs tracts (conventional approach)",
            "n_targets":     20,
            "n_crossings":   8,
            "pct_pop_served": 1.09,
        },
        "efficiency_ratio":    1.5,
        "bayesian_target_geoids": bayesian_geoids,
        "det_target_geoids":      det_geoids,
    },
}

out_path = APP_DATA_DIR / "metadata.json"
with open(out_path, "w") as f:
    json.dump(metadata, f, indent=2)
print(f"  Written: {out_path.name}  ({out_path.stat().st_size / 1024:.0f} KB)")


# --- Done --------------------------------------------------------------------

print("\nOK  export_frontend.py complete.")
print(f"   Output directory: {APP_DATA_DIR}")
print(f"   Files: {', '.join(p.name for p in APP_DATA_DIR.rglob('*') if p.is_file())}")
