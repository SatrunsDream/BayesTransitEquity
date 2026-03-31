"""Generate notebooks/03_accessibility_computation.ipynb from embedded cell sources."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "notebooks" / "03_accessibility_computation.ipynb"

META = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {
        "codemirror_mode": {"name": "ipython", "version": 3},
        "file_extension": ".py",
        "mimetype": "text/x-python",
        "name": "python",
        "nbconvert_exporter": "python",
        "pygments_lexer": "ipython3",
        "version": "3.11.0",
    },
}


def cell_md(text: str, cid: str) -> dict:
    return {"cell_type": "markdown", "id": cid, "metadata": {}, "source": text}


def cell_code(lines: list[str], cid: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cid,
        "metadata": {},
        "outputs": [],
        "source": "\n".join(lines),
    }


MD0 = """# 03 — Accessibility computation (pipeline)

**r5py** (Java; pin `r5py` in `requirements.txt`) needs:

1. **OSM `.osm.pbf`** — `r5.osm_pbf` in `configs/san_diego.yaml`
2. **`data/processed/gtfs/sd_merged_bbox.zip`** from notebook **02**

**Config:** `defaults.yaml` + `san_diego.yaml` are **deep-merged** (nested `accessibility:` preserved).

**Routing:** For each OD chunk, **transit+walk** and **walk-only** matrices are combined with **elementwise minimum** travel time (so purely walkable trips count when transit is unavailable).

**Opportunities** (see `accessibility.opportunities` in `defaults.yaml`): jobs (LODES), groceries / hospitals / schools (latest EDA OSM CSVs). **Self–self OD pairs** are excluded from “reachable elsewhere” job sums; **jobs located in the origin tract** are added separately (`jobs_in_origin_tract`).

**Thresholds:** Jobs (and POI counts) at **30 / 45 / 60** min after one OD run.

**Outputs:** Parquet under `data/processed/accessibility/`, figures under `artifacts/figures/`, `pipeline__03_*.csv`, checkpoints under `data/interim/accessibility_od/`.

**Previous:** [`02_gtfs_processing.ipynb`](02_gtfs_processing.ipynb) · **Next:** [`04_bayesian_model.ipynb`](04_bayesian_model.ipynb)
"""

C1 = r'''from __future__ import annotations

import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from IPython.display import Markdown, display


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def find_repo_root() -> Path:
    start = Path.cwd().resolve()
    for d in [start, *start.parents]:
        if (d / "configs" / "san_diego.yaml").exists():
            return d
    raise FileNotFoundError("Could not find configs/san_diego.yaml.")


REPO_ROOT = find_repo_root()
with open(REPO_ROOT / "configs" / "defaults.yaml", encoding="utf-8") as f:
    _defaults = yaml.safe_load(f)
with open(REPO_ROOT / "configs" / "san_diego.yaml", encoding="utf-8") as f:
    _city = yaml.safe_load(f)
CONFIG = deep_merge(_defaults, _city)

bbox = CONFIG["bbox"]
min_lon, min_lat, max_lon, max_lat = bbox
census_cfg = CONFIG.get("census", {})
state_fips = str(census_cfg.get("state_fips", CONFIG.get("state_fips", "06"))).zfill(2)
county_fips = str(census_cfg.get("county_fips", CONFIG.get("county_fips", "073"))).zfill(3)
acc = CONFIG.get("accessibility", {})
T_PRIMARY = int(acc.get("travel_time_threshold_min", 45))
THRESHOLDS_MIN = sorted(set([30, 45, 60] + [T_PRIMARY]))
walk_kph = float(acc.get("walk_speed_kph", 4.8))
win_start = acc.get("departure_window_start", "07:00")
win_end = acc.get("departure_window_end", "09:00")


def _hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


dep_win_min = max(5, _hhmm_to_minutes(win_end) - _hhmm_to_minutes(win_start))

r5cfg = CONFIG.get("r5") or {}
OSM_PBF = REPO_ROOT / r5cfg.get("osm_pbf", "data/raw/osm/san_diego_study.osm.pbf")
GTFS_ZIP = REPO_ROOT / "data" / "processed" / "gtfs" / "sd_merged_bbox.zip"
TODAY = date.today().isoformat()
OUT_ACC = REPO_ROOT / "data" / "processed" / "accessibility"
OUT_ACC.mkdir(parents=True, exist_ok=True)
ART_TAB = REPO_ROOT / "artifacts" / "tables"
ART_FIG = REPO_ROOT / "artifacts" / "figures"
ART_TAB.mkdir(parents=True, exist_ok=True)
ART_FIG.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR = REPO_ROOT / "data" / "interim" / "accessibility_od" / TODAY
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

if not OSM_PBF.is_file():
    raise FileNotFoundError(
        f"Missing OSM PBF for r5py: {OSM_PBF}\n"
        "Set `r5.osm_pbf` in configs/san_diego.yaml."
    )
if not GTFS_ZIP.is_file():
    raise FileNotFoundError(f"Run notebook 02 first — expected {GTFS_ZIP}")

dep_date = datetime.strptime(str(r5cfg.get("departure_date", "2025-04-15")), "%Y-%m-%d").date()
hh, mm = str(r5cfg.get("departure_hhmm", "07:30")).split(":")
DEPARTURE = datetime(dep_date.year, dep_date.month, dep_date.day, int(hh), int(mm))
DEPARTURE_WINDOW = timedelta(minutes=dep_win_min)
_max_cut = max(THRESHOLDS_MIN)
MAX_TRIP = timedelta(minutes=int(_max_cut + max(60, _max_cut * 0.5)))
MAX_WALK_ONLY = timedelta(minutes=90)

feed_info_csvs = sorted(ART_TAB.glob("eda__gtfs_feed_info__*.csv"))
if feed_info_csvs:
    fi = pd.read_csv(feed_info_csvs[-1])
    dep_ts = pd.Timestamp(dep_date)
    for _, row in fi.iterrows():
        raw_s, raw_e = row.get("feed_start_date"), row.get("feed_end_date")
        if pd.isna(raw_s) or pd.isna(raw_e) or str(raw_s) == "" or str(raw_e) == "":
            continue
        try:
            start = pd.to_datetime(str(raw_s).split(".")[0], format="%Y%m%d", errors="coerce")
            end = pd.to_datetime(str(raw_e).split(".")[0], format="%Y%m%d", errors="coerce")
        except Exception:
            continue
        if pd.isna(start) or pd.isna(end):
            continue
        ag = row.get("agency_id", row.get("agency_name", "?"))
        if not (start.normalize() <= dep_ts.normalize() <= end.normalize()):
            warnings.warn(
                f"Departure {dep_date} is outside {ag} feed validity "
                f"({start.date()} – {end.date()}). Travel times may be unreliable.",
                RuntimeWarning,
                stacklevel=2,
            )

display(
    Markdown(
        f"**OSM PBF:** `{OSM_PBF.relative_to(REPO_ROOT)}`  \n"
        f"**GTFS:** `{GTFS_ZIP.relative_to(REPO_ROOT)}`  \n"
        f"**Thresholds (min):** {THRESHOLDS_MIN} · **MAX_TRIP** {MAX_TRIP} · **walk-only cap** {MAX_WALK_ONLY}"
    )
)
display(Markdown(f"**Departure** {DEPARTURE.isoformat()} · **window** {DEPARTURE_WINDOW}"))
'''

C2 = r'''import re
import warnings

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

# TIGER tracts (prefer newest year: sort by embedded tl_YYYY in path)
census_root = REPO_ROOT / "data" / "raw" / "census"
tiger_candidates = sorted(census_root.glob("tl_*_06_tract/tl_*_06_tract.shp"))
if not tiger_candidates:
    raise FileNotFoundError("No TIGER tract shapefile under data/raw/census/ (tl_*_06_tract)")


def _tiger_year(p) -> int:
    m = re.search(r"tl_(\d{4})_06_tract", p.as_posix())
    return int(m.group(1)) if m else 0


tiger_shp = max(tiger_candidates, key=_tiger_year)

tracts = gpd.read_file(tiger_shp)
tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)
# COUNTYFP/STATEFP can be int, float, or str — compare as integers
state_fips_i = int(state_fips)
county_fips_i = int(county_fips)
tracts["_sf"] = pd.to_numeric(tracts["STATEFP"], errors="coerce").astype("Int64")
tracts["_cf"] = pd.to_numeric(tracts["COUNTYFP"], errors="coerce").astype("Int64")
tracts_sd = tracts[(tracts["_sf"] == state_fips_i) & (tracts["_cf"] == county_fips_i)].copy()
tracts_sd = tracts_sd.drop(columns=["_sf", "_cf"], errors="ignore")

if tracts_sd.empty:
    raise ValueError(
        f"No tracts after STATEFP={state_fips} COUNTYFP={county_fips} filter. "
        "Check TIGER vintage and config census FIPS."
    )

study_poly = box(min_lon, min_lat, max_lon, max_lat)
tracts_wgs = tracts_sd.to_crs(4326)
tracts_ix = tracts_wgs[tracts_wgs.geometry.intersects(study_poly)].copy()
tracts_ix["geometry"] = tracts_ix.geometry.representative_point()
tract_pts = gpd.GeoDataFrame(tracts_ix[["GEOID", "geometry"]], crs="EPSG:4326")
tract_pts["id"] = tract_pts["GEOID"].astype(str)

n_tracts = len(tract_pts)
# San Diego County has 737 tracts; expanded bbox typically intersects ~726 (EDA).
if n_tracts > 737:
    raise ValueError(f"Tract count {n_tracts} > 737 — check FIPS filters / duplicate geometries.")
if n_tracts < 400:
    warnings.warn(
        f"Only {n_tracts} tract centroids intersect bbox — expected roughly 500–730 for "
        "the expanded D009 window; verify `bbox` in configs/san_diego.yaml.",
        UserWarning,
        stacklevel=2,
    )

display(Markdown(f"### Origins/destinations: **{n_tracts}** tracts (TIGER `{tiger_shp.relative_to(REPO_ROOT)}`)"))
tract_pts.head()
'''

C3 = r'''# LODES WAC — jobs by workplace tract
lodes_dir = REPO_ROOT / "data" / "raw" / "external" / "lodes"
lodes_files = sorted(lodes_dir.glob("ca_wac_*.csv.gz"))
if not lodes_files:
    raise FileNotFoundError(
        f"No LODES WAC gzip matching ca_wac_*.csv.gz in {lodes_dir}"
    )
lodes_path = lodes_files[-1]
wac = pd.read_csv(lodes_path, usecols=["w_geocode", "C000"], dtype={"w_geocode": str}, compression="gzip")
prefix = state_fips + county_fips
wac = wac[wac["w_geocode"].str.startswith(prefix)]
wac["tract_geoid"] = wac["w_geocode"].str[:11].str.zfill(11)
jobs_by_tract = wac.groupby("tract_geoid", as_index=False)["C000"].sum().rename(columns={"C000": "jobs_total"})
jobs_origin = jobs_by_tract.rename(columns={"tract_geoid": "GEOID", "jobs_total": "jobs_in_origin_tract"})
display(Markdown(f"**LODES** `{lodes_path.name}` → **{len(jobs_by_tract)}** tracts with jobs"))
jobs_by_tract.head()
'''

C4 = r'''import numpy as np
from r5py import TransportNetwork, TravelTimeMatrix
from tqdm.auto import tqdm


def _tt_col(df: pd.DataFrame) -> str:
    if "travel_time" in df.columns:
        return "travel_time"
    if "travel_time_p50" in df.columns:
        return "travel_time_p50"
    raise AssertionError(f"No travel_time column. Got: {df.columns.tolist()}")


def _merge_transit_walk_min(df_t: pd.DataFrame, df_w: pd.DataFrame) -> pd.DataFrame:
    ct, cw = _tt_col(df_t), _tt_col(df_w)
    a = df_t[["from_id", "to_id", ct]].rename(columns={ct: "tt_transit"})
    b = df_w[["from_id", "to_id", cw]].rename(columns={cw: "tt_walk"})
    m = a.merge(b, on=["from_id", "to_id"], how="outer")
    t1 = pd.to_numeric(m["tt_transit"], errors="coerce")
    t2 = pd.to_numeric(m["tt_walk"], errors="coerce")
    m["travel_time"] = np.fmin(t1.fillna(np.inf), t2.fillna(np.inf))
    mask_both_nan = t1.isna() & t2.isna()
    m.loc[mask_both_nan, "travel_time"] = np.nan
    m.loc[m["travel_time"] == np.inf, "travel_time"] = np.nan
    return m[["from_id", "to_id", "travel_time"]]


def run_od_chunked(
    transport_network,
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    *,
    desc: str,
    file_tag: str,
) -> pd.DataFrame:
    parts = []
    n = len(origins)
    for i in tqdm(range(0, n, ORIGIN_CHUNK), desc=desc):
        ck = CHECKPOINT_DIR / f"{file_tag}_chunk_{i:05d}.parquet"
        if ck.is_file():
            parts.append(pd.read_parquet(ck))
            continue
        sub = origins.iloc[i : i + ORIGIN_CHUNK]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ttm_tr = TravelTimeMatrix(
                transport_network,
                origins=sub,
                destinations=destinations,
                departure=DEPARTURE,
                departure_time_window=DEPARTURE_WINDOW,
                transport_modes=["TRANSIT"],
                access_modes=["WALK"],
                egress_modes=["WALK"],
                max_time=MAX_TRIP,
                speed_walking=walk_kph,
                snap_to_network=True,
            )
            ttm_wk = TravelTimeMatrix(
                transport_network,
                origins=sub,
                destinations=destinations,
                departure=DEPARTURE,
                departure_time_window=DEPARTURE_WINDOW,
                transport_modes=["WALK"],
                max_time=MAX_WALK_ONLY,
                speed_walking=walk_kph,
                snap_to_network=True,
            )
        df_t = pd.DataFrame(ttm_tr).copy()
        df_w = pd.DataFrame(ttm_wk).copy()
        for dfx in (df_t, df_w):
            if "geometry" in dfx.columns:
                dfx.drop(columns=["geometry"], inplace=True)
        merged = _merge_transit_walk_min(df_t, df_w)
        merged.to_parquet(ck, index=False)
        parts.append(merged)
    return pd.concat(parts, ignore_index=True)


transport_network = TransportNetwork(OSM_PBF, [GTFS_ZIP])
ORIGIN_CHUNK = int(r5cfg.get("origin_chunk_size", 35))
origins = tract_pts.reset_index(drop=True)
destinations = tract_pts.copy()

od_tract = run_od_chunked(
    transport_network,
    origins,
    destinations,
    desc="Tract OD (min transit vs walk)",
    file_tag="tract_od_min",
)
od_tract["from_id"] = od_tract["from_id"].astype(str).str.zfill(11)
od_tract["to_id"] = od_tract["to_id"].astype(str).str.zfill(11)
tt_col = _tt_col(od_tract)
assert tt_col in od_tract.columns

od_path = OUT_ACC / f"tract_tract_od_traveltime__{TODAY}.parquet"
od_tract.to_parquet(od_path, index=False)
display(Markdown(f"Saved `{od_path.relative_to(REPO_ROOT)}`  rows={len(od_tract)}"))
'''

C5 = r'''# Jobs accessibility: exclude self OD; add origin-tract jobs; 30/45/60 (and primary) minutes
od_j = od_tract.merge(
    jobs_by_tract,
    left_on="to_id",
    right_on="tract_geoid",
    how="left",
)
od_j["jobs_total"] = od_j["jobs_total"].fillna(0.0)
od_ext = od_j[od_j["from_id"] != od_j["to_id"]].copy()
ttm = pd.to_numeric(od_ext[tt_col], errors="coerce")
for t in THRESHOLDS_MIN:
    od_ext[f"reachable_jobs_{t}min"] = ((ttm <= t) & ttm.notna()).astype(float) * od_ext["jobs_total"]

agg_cols = {f"reachable_jobs_{t}min": "sum" for t in THRESHOLDS_MIN}
access_other = od_ext.groupby("from_id", as_index=False).agg(agg_cols)
access_other = access_other.rename(columns={"from_id": "GEOID"})
access_jobs = access_other.merge(jobs_origin, on="GEOID", how="left")
access_jobs["jobs_in_origin_tract"] = access_jobs["jobs_in_origin_tract"].fillna(0.0)

for t in THRESHOLDS_MIN:
    access_jobs[f"jobs_C000_{t}min"] = access_jobs[f"reachable_jobs_{t}min"].fillna(0.0) + access_jobs[
        "jobs_in_origin_tract"
    ]

jobs_path = OUT_ACC / f"tract_jobs_accessibility__{TODAY}.parquet"
access_jobs.to_parquet(jobs_path, index=False)
display(Markdown(f"Saved `{jobs_path.relative_to(REPO_ROOT)}`"))
access_jobs.head()
'''

C6 = r'''# POI matrices (groceries, hospitals, schools) — stable poi_id; usecols; checkpoints (uses `run_od_chunked` from above)


def load_poi_gdf(glob_pat: str, prefix: str) -> gpd.GeoDataFrame:
    files = sorted(ART_TAB.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"No artifact matching {glob_pat} under {ART_TAB}")
    gdf = pd.read_csv(files[-1], usecols=["element", "id", "lon", "lat"])
    osm_id = gdf["id"].astype(str)
    gdf = gdf.assign(poi_id=prefix + gdf["element"].astype(str) + "_" + osm_id)
    poi = gpd.GeoDataFrame(gdf, geometry=gpd.points_from_xy(gdf["lon"], gdf["lat"]), crs="EPSG:4326")
    poi["id"] = poi["poi_id"]
    return poi[["id", "geometry"]]


def poi_counts_wide(od_poi: pd.DataFrame, name: str) -> pd.DataFrame:
    od_poi = od_poi.copy()
    od_poi["from_id"] = od_poi["from_id"].astype(str).str.zfill(11)
    ttm = pd.to_numeric(od_poi["travel_time"], errors="coerce")
    parts = []
    for t in THRESHOLDS_MIN:
        mask = (ttm <= t) & ttm.notna()
        cnt = od_poi.loc[mask].groupby("from_id").size().rename(f"{name}_count_{t}min")
        parts.append(cnt)
    if not parts:
        base = tract_pts[["GEOID"]].copy()
        base["GEOID"] = base["GEOID"].astype(str).str.zfill(11)
        for t in THRESHOLDS_MIN:
            base[f"{name}_count_{t}min"] = 0
        return base
    wide = pd.concat(parts, axis=1).fillna(0).astype(int)
    if wide.empty:
        base = tract_pts[["GEOID"]].copy()
        base["GEOID"] = base["GEOID"].astype(str).str.zfill(11)
        for t in THRESHOLDS_MIN:
            base[f"{name}_count_{t}min"] = 0
        return base
    wide = wide.reset_index().rename(columns={"from_id": "GEOID"})
    base = tract_pts[["GEOID"]].copy()
    base["GEOID"] = base["GEOID"].astype(str).str.zfill(11)
    merged = base.merge(wide, on="GEOID", how="left")
    for t in THRESHOLDS_MIN:
        c = f"{name}_count_{t}min"
        merged[c] = merged[c].fillna(0).astype(int)
    return merged


poi_specs = [
    ("eda__osm_destinations_groceries__*.csv", "g_", "groceries", "POI groceries"),
    ("eda__osm_destinations_hospitals__*.csv", "h_", "hospitals", "POI hospitals"),
    ("eda__osm_destinations_schools__*.csv", "s_", "schools", "POI schools"),
]
poi_tables: dict[str, pd.DataFrame] = {}

for glob_pat, pfx, short, desc in poi_specs:
    poi_dest = load_poi_gdf(glob_pat, pfx)
    od_p = run_od_chunked(
        transport_network,
        origins,
        poi_dest,
        desc=desc,
        file_tag=f"poi_{short}",
    )
    od_p["from_id"] = od_p["from_id"].astype(str).str.zfill(11)
    od_p["to_id"] = od_p["to_id"].astype(str)
    ppath = OUT_ACC / f"tract_poi_{short}_od__{TODAY}.parquet"
    od_p.to_parquet(ppath, index=False)
    poi_tables[short] = poi_counts_wide(od_p, short)
    display(Markdown(f"**{short}** → `{ppath.relative_to(REPO_ROOT)}`  rows={len(od_p)}"))

poi_bundle = poi_tables["groceries"]
for k in ("hospitals", "schools"):
    poi_bundle = poi_bundle.merge(poi_tables[k], on="GEOID", how="outer")
poi_path = OUT_ACC / f"tract_poi_counts__{TODAY}.parquet"
poi_bundle.to_parquet(poi_path, index=False)
display(Markdown(f"Saved `{poi_path.relative_to(REPO_ROOT)}`"))
poi_bundle.head()
'''

C7 = r'''# Bundle tract attributes + choropleth + equity diagnostic + pipeline summary
import matplotlib.pyplot as plt

out = access_jobs.merge(poi_bundle, on="GEOID", how="outer")
bundle_path = OUT_ACC / f"tract_accessibility_bundle__{TODAY}.parquet"
out.to_parquet(bundle_path, index=False)

tracts_map = tracts_ix.merge(out, on="GEOID", how="left")
col_plot = f"jobs_C000_{T_PRIMARY}min"
fig, ax = plt.subplots(figsize=(10, 10))
tracts_map.plot(
    column=col_plot,
    cmap="YlOrRd",
    legend=True,
    ax=ax,
    missing_kwds={"color": "lightgrey"},
)
ax.set_axis_off()
ax.set_title(f"Jobs reachable within {T_PRIMARY} min (tract origins; self+other)")
fig_path = ART_FIG / f"pipeline__03_accessibility_choropleth__{TODAY}.png"
fig.savefig(fig_path, dpi=150, bbox_inches="tight")
plt.close(fig)
display(Markdown(f"Figure → `{fig_path.relative_to(REPO_ROOT)}`"))

acs_files = sorted(ART_TAB.glob("eda__acs_sd_tract_attributes__*.csv"))
rho = float("nan")
if acs_files:
    acs = pd.read_csv(acs_files[-1], usecols=lambda c: c in ("GEOID", "disadvantage_z"))
    acs["GEOID"] = acs["GEOID"].astype(str).str.zfill(11)
    diag = out.merge(acs, on="GEOID", how="left")
    pair = diag[[col_plot, "disadvantage_z"]].dropna()
    if len(pair) > 2:
        rho = pair.corr(method="spearman").iloc[0, 1]
    zero_jobs = int((out[col_plot].fillna(0) == 0).sum())
    med_jobs = float(out[col_plot].median())
    display(
        Markdown(
            f"""
**Equity diagnostic (Spearman)**  
`{col_plot}` vs `disadvantage_z`: **ρ = {rho:.3f}**  
*(negative = accessibility anti-poor despite supply being pro-poor; positive = density advantage holds)*  
Tracts with 0 reachable jobs (incl. origin jobs): **{zero_jobs}** of {len(out)}  
Median jobs reachable: **{med_jobs:,.0f}**  
"""
        )
    )
else:
    display(Markdown("_No `eda__acs_sd_tract_attributes__*.csv` found — skip Spearman._"))

summary = pd.DataFrame(
    [
        {"key": "repo_root", "value": str(REPO_ROOT)},
        {"key": "od_tract_parquet", "value": str(od_path.relative_to(REPO_ROOT))},
        {"key": "jobs_parquet", "value": str(jobs_path.relative_to(REPO_ROOT))},
        {"key": "poi_bundle_parquet", "value": str(poi_path.relative_to(REPO_ROOT))},
        {"key": "bundle_parquet", "value": str(bundle_path.relative_to(REPO_ROOT))},
        {"key": "figure", "value": str(fig_path.relative_to(REPO_ROOT))},
        {"key": "tracts", "value": len(tract_pts)},
        {"key": "spearman_jobs_disadvantage_z", "value": rho},
        {"key": "thresholds_min", "value": str(THRESHOLDS_MIN)},
    ]
)
sum_path = ART_TAB / f"pipeline__03_accessibility_summary__{TODAY}.csv"
summary.to_csv(sum_path, index=False)
display(Markdown(f"Summary → `{sum_path.relative_to(REPO_ROOT)}`"))
summary
'''

NB = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": META,
    "cells": [
        cell_md(MD0, "md0"),
        cell_code(C1.split("\n"), "c1"),
        cell_code(C2.split("\n"), "c2"),
        cell_code(C3.split("\n"), "c3"),
        cell_code(C4.split("\n"), "c4"),
        cell_code(C5.split("\n"), "c5"),
        cell_code(C6.split("\n"), "c6"),
        cell_code(C7.split("\n"), "c7"),
    ],
}


def main() -> None:
    # Jupyter expects source as list of lines with \\n
    for cell in NB["cells"]:
        if cell["cell_type"] == "code":
            src = cell["source"]
            if isinstance(src, str):
                lines = src.split("\n")
            else:
                lines = src
            cell["source"] = [ln + "\n" for ln in lines[:-1]] + ([lines[-1] + "\n"] if lines else [])
        else:
            src = cell["source"]
            if isinstance(src, str):
                lines = src.split("\n")
            else:
                lines = src
            cell["source"] = [ln + "\n" for ln in lines[:-1]] + ([lines[-1] + "\n"] if lines else [])
    OUT.write_text(json.dumps(NB, indent=1), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
