"""One-off patch: refresh nb01/nb02 code cells (shared config, RUN_ID, GTFS fixes). Run from repo root."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

NB01_CODE = r'''from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import pandas as pd
from IPython.display import display

_repo = Path.cwd().resolve()
for _d in [_repo, *_repo.parents]:
    if (_d / "configs" / "san_diego.yaml").exists():
        if str(_d) not in sys.path:
            sys.path.insert(0, str(_d))
        break
else:
    raise FileNotFoundError("No configs/san_diego.yaml found.")

from src.utils.config import load_merged_config, pipeline_run_id
from src.utils.paths import find_repo_root

REPO_ROOT = find_repo_root()
CONFIG = load_merged_config(REPO_ROOT)
RUN_ID = pipeline_run_id()
r5cfg = CONFIG.get("r5") or {}
osm_pbf_rel = str(r5cfg.get("osm_pbf", "data/raw/osm/san_diego_study.osm.pbf")).replace("\\", "/")

dep_yyyymmdd = str(r5cfg.get("departure_date", "2025-04-15")).replace("-", "")


def file_stat(rel: Path) -> tuple[bool, int | None]:
    p = REPO_ROOT / rel
    if not p.is_file():
        return False, None
    return True, p.stat().st_size


rows: list[dict] = []
for ag in CONFIG.get("gtfs_agencies") or []:
    ag_root = REPO_ROOT / ag["raw_path"].strip().rstrip("/\\").replace("\\", "/")
    for name, sub in [("feed_info", "extracted/feed_info.txt"), ("stops", "extracted/stops.txt")]:
        abs_p = ag_root / sub
        rel_s = str(abs_p.relative_to(REPO_ROOT)).replace("\\", "/")
        ok, sz = file_stat(Path(rel_s))
        rows.append(
            {
                "component": f"gtfs:{ag['id']}:{name}",
                "path": rel_s,
                "exists": ok,
                "size_bytes": sz if ok else None,
            }
        )

census_dir = REPO_ROOT / "data" / "raw" / "census"
tiger_zips = sorted(census_dir.glob("tl_*_06_tract.zip"))
tiger_shps = sorted(census_dir.glob("tl_*_06_tract/tl_*_06_tract.shp"))
if tiger_zips:
    zr = str(tiger_zips[-1].relative_to(REPO_ROOT)).replace("\\", "/")
    ok, sz = file_stat(Path(zr))
    rows.append({"component": "census:tiger_zip", "path": zr, "exists": ok, "size_bytes": sz if ok else None})
else:
    rows.append({"component": "census:tiger_zip", "path": "data/raw/census/tl_*_06_tract.zip", "exists": False, "size_bytes": None})
if tiger_shps:
    tr = str(tiger_shps[-1].relative_to(REPO_ROOT)).replace("\\", "/")
    ok, sz = file_stat(Path(tr))
    rows.append({"component": "census:tiger_shp", "path": tr, "exists": ok, "size_bytes": sz if ok else None})
else:
    rows.append({"component": "census:tiger_shp", "path": "data/raw/census/tl_*_06_tract/tl_*_06_tract.shp", "exists": False, "size_bytes": None})

for rel, comp in [
    ("data/raw/census/acs5_2023_sd_county.json", "census:acs"),
    ("data/raw/osm/sd_walk_network.graphml", "osm:walk_graph_eda"),
]:
    ok, sz = file_stat(Path(rel))
    rows.append({"component": comp, "path": rel, "exists": ok, "size_bytes": sz if ok else None})

ok, sz = file_stat(Path(osm_pbf_rel))
rows.append({"component": "osm:r5_pbf", "path": osm_pbf_rel, "exists": ok, "size_bytes": sz if ok else None})

lodes_dir = REPO_ROOT / "data" / "raw" / "external" / "lodes"
lodes_files = sorted(lodes_dir.glob("ca_wac_*.csv.gz")) if lodes_dir.is_dir() else []
if lodes_files:
    lf = lodes_files[-1]
    rel_s = str(lf.relative_to(REPO_ROOT)).replace("\\", "/")
    rows.append({"component": "lodes:wac", "path": rel_s, "exists": True, "size_bytes": lf.stat().st_size})
else:
    rows.append({"component": "lodes:wac", "path": "data/raw/external/lodes/ca_wac_*.csv.gz", "exists": False, "size_bytes": None})

df = pd.DataFrame(rows)
art = REPO_ROOT / "artifacts" / "tables"
art.mkdir(parents=True, exist_ok=True)
p_status = art / f"pipeline__01_raw_inputs_status__{RUN_ID}.csv"
df.to_csv(p_status, index=False)

snap = pd.DataFrame(
    [
        {
            "city": CONFIG.get("city"),
            "city_label": CONFIG.get("city_label"),
            "county_fips": CONFIG.get("county_fips"),
            "bbox": str(CONFIG.get("bbox")),
            "n_gtfs_agencies": len(CONFIG.get("gtfs_agencies") or []),
            "config_merge": "defaults.yaml + san_diego.yaml (deep-merge)",
            "pipeline_run_id": RUN_ID,
            "T_cut_min": CONFIG.get("accessibility", {}).get("travel_time_threshold_min"),
            "walk_speed_kph": CONFIG.get("accessibility", {}).get("walk_speed_kph"),
            "opportunities": str(CONFIG.get("accessibility", {}).get("opportunities")),
            "r5_departure_date": r5cfg.get("departure_date"),
            "r5_osm_pbf": osm_pbf_rel,
            "model_draws": CONFIG.get("model", {}).get("draws"),
            "model_chains": CONFIG.get("model", {}).get("chains"),
            "export_parquet_compression": CONFIG.get("export", {}).get("parquet_compression"),
        }
    ]
)
p_snap = art / f"pipeline__01_config_snapshot__{RUN_ID}.csv"
snap.to_csv(p_snap, index=False)

for ag in CONFIG.get("gtfs_agencies") or []:
    aid = ag["id"]
    ag_root = REPO_ROOT / ag["raw_path"].strip().rstrip("/\\").replace("\\", "/")
    fi_path = ag_root / "extracted" / "feed_info.txt"
    if not fi_path.is_file():
        continue
    fi_df = pd.read_csv(fi_path, dtype=str)
    if fi_df.empty:
        continue
    row = fi_df.iloc[0]
    fs, fe = row.get("feed_start_date"), row.get("feed_end_date")
    if fs is None or fe is None or str(fs).strip() == "" or str(fe).strip() == "":
        continue
    try:
        dep_i = int(dep_yyyymmdd)
        s_i = int(str(fs).split(".")[0])
        e_i = int(str(fe).split(".")[0])
        if dep_i < s_i or dep_i > e_i:
            warnings.warn(
                f"Departure {dep_yyyymmdd} is outside {aid} feed_info window ({fs}–{fe}). r5py may be unreliable.",
                UserWarning,
                stacklevel=2,
            )
    except (ValueError, TypeError):
        pass

prov_dir = REPO_ROOT / "artifacts" / "logs" / "provenance"
manifests = sorted(prov_dir.glob("data_manifest_*.json"), reverse=True)
latest_manifest = manifests[0] if manifests else None
if latest_manifest:
    meta = json.loads(latest_manifest.read_text(encoding="utf-8"))
    dfm = pd.DataFrame(meta.get("sources", []))
    p_man = art / f"pipeline__01_latest_manifest_sources__{RUN_ID}.csv"
    dfm.to_csv(p_man, index=False)

missing_required = df[(~df["exists"]) & df["component"].isin(["osm:r5_pbf", "lodes:wac"])]
if not missing_required.empty:
    warnings.warn(
        f"BLOCKING: required inputs missing:\n{missing_required[['component', 'path']].to_string()}",
        RuntimeWarning,
        stacklevel=2,
    )

display(snap)
display(df)
if latest_manifest:
    display(dfm.head(20))
'''


def _lines(src: str) -> list[str]:
    lines = src.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + ([lines[-1] + "\n"] if lines else [])


def main() -> None:
    p01 = REPO / "notebooks" / "01_data_exploration.ipynb"
    nb = json.loads(p01.read_text(encoding="utf-8"))
    nb["cells"][1]["source"] = _lines(NB01_CODE)
    nb["cells"][1]["outputs"] = []
    nb["cells"][1]["execution_count"] = None
    p01.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print(f"Patched {p01}")


if __name__ == "__main__":
    main()
