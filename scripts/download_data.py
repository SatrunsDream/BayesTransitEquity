#!/usr/bin/env python3
"""
scripts/download_data.py

Downloads all raw data sources for BayesTransitEquity.
Writes a provenance manifest to artifacts/logs/provenance/.

Usage:
    python scripts/download_data.py --config configs/san_diego.yaml
    python scripts/download_data.py --config configs/san_diego.yaml --sources gtfs census
    python scripts/download_data.py --config configs/san_diego.yaml --force
    python scripts/download_data.py --config configs/san_diego.yaml --dry-run
    python scripts/download_data.py --config configs/san_diego.yaml --refresh-mobility-catalog

Sources:
    gtfs     GTFS schedule feeds for all configured agencies
    census   Census tract shapefiles (TIGER/Line) + ACS demographic variables
    osm      OpenStreetMap pedestrian walk network (via osmnx) -> GraphML for EDA
    osm_pbf  Clip regional OSM .pbf to bbox for r5py (requires `osmium`; not in `all`)
    lodes    LEHD LODES job data (WAC file for California)
    all      gtfs + census + osm + lodes (excludes osm_pbf — large + external tool)
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

# ── Repo root resolution ───────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent


def _mobility_catalog_settings(config: dict) -> dict:
    return config.get("mobility_catalog") or {}


def ensure_mobility_feeds_csv(
    config: dict,
    *,
    dry_run: bool,
    force_refresh: bool,
) -> Path | None:
    """
    Download feeds_v2.csv to data/interim/ if missing or older than max_age_days.
    Returns path to CSV, or None on dry-run when no cache exists.
    """
    mc = _mobility_catalog_settings(config)
    url = mc.get("feeds_csv_url", "https://files.mobilitydatabase.org/feeds_v2.csv")
    rel = mc.get("cache_relative_path", "data/interim/mobility_database/feeds_v2.csv")
    max_age_days = int(mc.get("max_age_days", 7))
    path = REPO_ROOT / rel

    if dry_run:
        if path.exists():
            return path
        print("  [DRY-RUN] No cached Mobility catalog; would download feeds_v2.csv before resolving GTFS URLs")
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    need_download = force_refresh or not path.exists()
    if path.exists() and not force_refresh:
        age_sec = max(0, time.time() - path.stat().st_mtime)
        if age_sec > max_age_days * 86400:
            need_download = True

    if not need_download:
        print(f"  [SKIP] Mobility catalog cache OK ({path.relative_to(REPO_ROOT)})")
        return path

    print(f"  [DOWNLOAD] Mobility Database feeds catalog ...")
    headers = {
        "User-Agent": "BayesTransitEquity-download/1.0 (+https://github.com; data pipeline)",
    }
    tmp = path.with_suffix(path.suffix + ".part")
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, stream=True, timeout=300, headers=headers)
            resp.raise_for_status()
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (5 << 20) < (1 << 16):
                        print(f"\r    {downloaded:,} bytes ...", end="", flush=True)
            print(f"\r    [ok] Saved catalog {downloaded:,} bytes  -> {path.relative_to(REPO_ROOT)}")
            tmp.replace(path)
            return path
        except Exception as e:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            if attempt < max_attempts:
                wait = 2 ** (attempt - 1)
                print(f"\n    [retry {attempt}/{max_attempts}] {e} - sleeping {wait}s")
                time.sleep(wait)
            else:
                print(f"    [FAIL] Mobility catalog download failed: {e}")
                if path.exists():
                    print(f"    Using stale cache at {path.relative_to(REPO_ROOT)}")
                    return path
                return None
    return None


def resolve_gtfs_urls_from_mobility_catalog(
    mobility_ids: set[str],
    csv_path: Path,
) -> dict[str, dict[str, str]]:
    """Map mobility feed id (e.g. mdb-14) -> {latest, direct} URL strings."""
    out: dict[str, dict[str, str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = (row.get("id") or "").strip()
            if rid not in mobility_ids:
                continue
            out[rid] = {
                "latest": (row.get("urls.latest") or "").strip(),
                "direct": (row.get("urls.direct_download") or "").strip(),
            }
            if len(out) == len(mobility_ids):
                break
    return out


def pick_gtfs_download_url(agency: dict, resolved: dict[str, str] | None) -> tuple[str, str]:
    """
    Prefer Mobility urls.latest (stable mirror), then urls.direct_download, then config download_url.
    Returns (url, provenance_label).
    """
    if resolved:
        latest = (resolved.get("latest") or "").strip()
        direct = (resolved.get("direct") or "").strip()
        if latest:
            return latest, "mobility_catalog.urls.latest"
        if direct:
            return direct, "mobility_catalog.urls.direct_download"
    fallback = (agency.get("download_url") or "").strip()
    if not fallback:
        aid = agency.get("id", "?")
        raise ValueError(
            f"GTFS agency {aid!r}: no download_url and no catalog URL (set mobility_db_id + run catalog fetch)"
        )
    return fallback, "config.download_url"


def load_configs(city_config_path: str) -> dict:
    """Load and merge defaults.yaml with city-specific config."""
    defaults_path = REPO_ROOT / "configs" / "defaults.yaml"
    with open(defaults_path) as f:
        config = yaml.safe_load(f)
    with open(REPO_ROOT / city_config_path) as f:
        city = yaml.safe_load(f)
    # City config overrides defaults
    config.update(city)
    return config


# ── Utilities ──────────────────────────────────────────────────────────────────

def md5(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(
    url: str,
    dest: Path,
    label: str,
    dry_run: bool = False,
    force: bool = False,
    *,
    timeout: float | tuple[float, float | None] = 120,
) -> dict:
    """
    Download a file from url to dest.
    Skips if dest exists and force=False (freeze logic).
    Returns a provenance entry dict.
    """
    if dest.exists() and not force:
        print(f"  [SKIP] {label} already exists at {dest.relative_to(REPO_ROOT)}")
        return {
            "label": label,
            "url": url,
            "dest": str(dest.relative_to(REPO_ROOT)),
            "status": "skipped_existing",
            "md5": md5(dest),
            "size_bytes": dest.stat().st_size,
            "downloaded_at": None,
        }

    if dry_run:
        print(f"  [DRY-RUN] Would download {label} from {url}")
        return {"label": label, "url": url, "status": "dry_run"}

    print(f"  [DOWNLOAD] {label} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "BayesTransitEquity-download/1.0 (+https://github.com; data pipeline)",
    }
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        try:
            resp = requests.get(url, stream=True, timeout=timeout, headers=headers)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r    {pct:.1f}% ({downloaded:,} / {total:,} bytes)", end="", flush=True)
            print()
            file_hash = md5(dest)
            size = dest.stat().st_size
            ts = datetime.now(timezone.utc).isoformat()
            print(f"    [ok] Saved {size:,} bytes  MD5={file_hash[:8]}...  to {dest.relative_to(REPO_ROOT)}")
            return {
                "label": label,
                "url": url,
                "dest": str(dest.relative_to(REPO_ROOT)),
                "status": "downloaded",
                "md5": file_hash,
                "size_bytes": size,
                "downloaded_at": ts,
            }
        except Exception as e:
            if attempt < max_attempts:
                wait = 2 ** (attempt - 1)
                print(f"\n    [retry {attempt}/{max_attempts}] {e} - sleeping {wait}s")
                time.sleep(wait)
            else:
                print(f"    [FAIL] FAILED: {e}")
                return {"label": label, "url": url, "status": "failed", "error": str(e)}


def extract_zip(zip_path: Path, extract_dir: Path, label: str):
    """Extract a zip archive and report contents."""
    print(f"  [EXTRACT] {label} ...")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        z.extractall(extract_dir)
        print(f"    [ok] Extracted {len(names)} files to {extract_dir.relative_to(REPO_ROOT)}")
    return names


# ── Source downloaders ─────────────────────────────────────────────────────────

def download_gtfs(
    config: dict,
    dry_run: bool,
    force: bool,
    *,
    refresh_mobility_catalog: bool = False,
) -> list:
    """Download GTFS schedule feeds for all configured agencies."""
    print("\n--- GTFS Feeds ---")
    entries = []
    agencies = config.get("gtfs_agencies", [])
    mobility_ids = {
        (a.get("mobility_db_id") or "").strip()
        for a in agencies
        if (a.get("mobility_db_id") or "").strip()
    }
    url_by_id: dict[str, dict[str, str]] = {}
    catalog_path: Path | None = None
    if mobility_ids:
        catalog_path = ensure_mobility_feeds_csv(
            config, dry_run=dry_run, force_refresh=refresh_mobility_catalog
        )
        if catalog_path and catalog_path.exists():
            url_by_id = resolve_gtfs_urls_from_mobility_catalog(mobility_ids, catalog_path)
            missing = mobility_ids - set(url_by_id.keys())
            if missing:
                print(f"  [WARN] Mobility catalog has no rows for: {sorted(missing)}; using config download_url")
        elif not dry_run:
            print("  [WARN] Mobility catalog unavailable; using config download_url for all GTFS agencies")

    for agency in agencies:
        agency_id = agency["id"]
        mid = (agency.get("mobility_db_id") or "").strip()
        resolved_row = url_by_id.get(mid) if mid else None
        try:
            url, url_source = pick_gtfs_download_url(agency, resolved_row)
        except ValueError as e:
            print(f"  [FAIL] {e}")
            entries.append(
                {
                    "label": f"GTFS/{agency_id}",
                    "status": "failed",
                    "error": str(e),
                    "agency_id": agency_id,
                    "agency_name": agency.get("name", agency_id),
                    "source_type": "gtfs_schedule",
                }
            )
            continue

        print(f"  GTFS/{agency_id} URL ({url_source}): {url[:88]}{'...' if len(url) > 88 else ''}")
        raw_dir = REPO_ROOT / agency["raw_path"]
        zip_path = raw_dir / "google_transit.zip"

        entry = download_file(url, zip_path, f"GTFS/{agency_id}", dry_run=dry_run, force=force)
        entry["agency_id"] = agency_id
        entry["agency_name"] = agency.get("name", agency_id)
        entry["source_type"] = "gtfs_schedule"
        entry["gtfs_download_url_source"] = url_source
        entry["mobility_db_id"] = mid or None

        # Extract zip if download succeeded or file exists
        if not dry_run and zip_path.exists():
            extract_dir = raw_dir / "extracted"
            files = extract_zip(zip_path, extract_dir, f"GTFS/{agency_id}")
            entry["extracted_files"] = files

            # Try to read feed_info.txt for feed version / validity dates
            feed_info_path = extract_dir / "feed_info.txt"
            if feed_info_path.exists():
                with open(feed_info_path) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        entry["feed_version"] = row.get("feed_version", "")
                        entry["feed_start_date"] = row.get("feed_start_date", "")
                        entry["feed_end_date"] = row.get("feed_end_date", "")
                        break
                print(f"    Feed version: {entry.get('feed_version', 'N/A')}  "
                      f"Valid: {entry.get('feed_start_date', '?')} -> {entry.get('feed_end_date', '?')}")

        entries.append(entry)
    return entries


def download_census(config: dict, dry_run: bool, force: bool) -> list:
    """Download Census TIGER/Line tract shapefiles and ACS demographics."""
    print("\n--- Census Data ---")
    entries = []
    state_fips = config["state_fips"]
    county_fips = config["county_fips"]
    acs_year = config.get("census", {}).get("acs_year", 2023)

    # ── TIGER/Line tract shapefile (state-level, then filter by county in EDA) ──
    tiger_url = (
        f"https://www2.census.gov/geo/tiger/TIGER{acs_year}/TRACT/"
        f"tl_{acs_year}_{state_fips}_tract.zip"
    )
    tiger_dest = REPO_ROOT / "data/raw/census" / f"tl_{acs_year}_{state_fips}_tract.zip"
    entry = download_file(tiger_url, tiger_dest, f"TIGER/Line Tracts CA {acs_year}",
                          dry_run=dry_run, force=force)
    entry["source_type"] = "tiger_tract_shapefile"
    entry["state_fips"] = state_fips
    entry["acs_year"] = acs_year

    if not dry_run and tiger_dest.exists():
        extract_dir = REPO_ROOT / "data/raw/census" / f"tl_{acs_year}_{state_fips}_tract"
        extract_zip(tiger_dest, extract_dir, "TIGER/Line Tracts")

    entries.append(entry)

    # ── ACS 5-year estimates via Census API ────────────────────────────────────
    # Estimate variables (E) + their Margin of Error counterparts (M) — explicit for clarity
    all_vars = [
        "NAME",
        "B01003_001E", "B01003_001M",   # Total population
        "B08201_002E", "B08201_002M",   # No-vehicle households
        "B19013_001E", "B19013_001M",   # Median household income
        "B17001_002E", "B17001_002M",   # Below poverty level
        "B18101_001E", "B18101_001M",   # Total (disability base)
        "B03002_001E", "B03002_001M",   # Total (race/ethnicity base)
        "B03002_003E", "B03002_003M",   # Non-Hispanic White alone
        "B03002_012E", "B03002_012M",   # Hispanic or Latino
        "B03002_004E", "B03002_004M",   # Black or African American alone
    ]

    api_url = (
        f"https://api.census.gov/data/{acs_year}/acs/acs5"
        f"?get={','.join(all_vars)}"
        f"&for=tract:*"
        f"&in=state:{state_fips}%20county:{county_fips}"
    )

    acs_dest = REPO_ROOT / "data/raw/census" / f"acs5_{acs_year}_sd_county.json"
    acs_entry = download_file(api_url, acs_dest, f"ACS {acs_year} 5yr SD County",
                              dry_run=dry_run, force=force)
    acs_entry["source_type"] = "acs_5yr_api"
    acs_entry["variables"] = all_vars
    acs_entry["acs_year"] = acs_year
    acs_entry["state_fips"] = state_fips
    acs_entry["county_fips"] = county_fips

    if not dry_run and acs_dest.exists():
        # Quick validation — check it's valid JSON with rows
        try:
            with open(acs_dest) as f:
                data = json.load(f)
            n_tracts = len(data) - 1  # subtract header row
            print(f"    [ok] ACS data: {n_tracts} tracts")
            acs_entry["n_tracts"] = n_tracts
        except Exception as e:
            print(f"    [FAIL] ACS JSON validation failed: {e}")

    entries.append(acs_entry)
    return entries


def _configure_osmnx(config: dict) -> None:
    """Tune osmnx/Overpass for large walk-network downloads (queue + long queries)."""
    import osmnx as ox

    osm = config.get("osm") or {}
    # Overpass QL [timeout:N] must be an integer — floats (e.g. 900.0) yield HTTP 400.
    timeout = int(osm.get("requests_timeout_seconds", 900))
    ox.settings.requests_timeout = timeout
    if url := osm.get("overpass_url"):
        ox.settings.overpass_url = str(url).rstrip("/")
    if "overpass_rate_limit" in osm:
        ox.settings.overpass_rate_limit = bool(osm["overpass_rate_limit"])
    # So users see "Pausing … before POST" and Overpass retries instead of a silent hang.
    ox.settings.log_console = True


def download_osm(config: dict, dry_run: bool, force: bool) -> list:
    """Download OSM pedestrian walk network for the configured bounding box."""
    print("\n--- OSM Pedestrian Network ---")
    entries = []
    osm_dest = REPO_ROOT / "data/raw/osm" / "sd_walk_network.graphml"

    if osm_dest.exists() and not force:
        print(f"  [SKIP] OSM network already exists at {osm_dest.relative_to(REPO_ROOT)}")
        entry = {
            "label": "OSM Walk Network",
            "source_type": "osm_pedestrian_network",
            "dest": str(osm_dest.relative_to(REPO_ROOT)),
            "status": "skipped_existing",
            "md5": md5(osm_dest),
            "size_bytes": osm_dest.stat().st_size,
            "downloaded_at": None,
        }
        entries.append(entry)
        return entries

    if dry_run:
        print("  [DRY-RUN] Would download OSM walk network via osmnx")
        entries.append({"label": "OSM Walk Network", "status": "dry_run"})
        return entries

    try:
        import osmnx as ox

        _configure_osmnx(config)
        bbox = config["bbox"]  # [min_lon, min_lat, max_lon, max_lat]
        # osmnx 2.x graph_from_bbox expects (left, bottom, right, top) = (min_lon, min_lat, max_lon, max_lat).
        # Do NOT pass (north, south, east, west) — that builds an invalid polygon and truncation leaves ~0 nodes.
        min_lon, min_lat, max_lon, max_lat = bbox

        print(
            f"  Fetching walk network for bbox "
            f"lon [{min_lon}, {max_lon}] lat [{min_lat}, {max_lat}] ..."
        )
        print(
            "  (Overpass is shared: expect queue pauses of several minutes and a long POST. "
            "osmnx INFO lines should appear below; if it fails, try osm.overpass_url mirror in configs/defaults.yaml.)"
        )
        G = ox.graph_from_bbox(
            bbox=(min_lon, min_lat, max_lon, max_lat),
            network_type="walk",
            retain_all=False,
        )
        nodes, edges = len(G.nodes), len(G.edges)
        print(f"    Graph: {nodes:,} nodes, {edges:,} edges")

        osm_dest.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(G, osm_dest)
        ts = datetime.now(timezone.utc).isoformat()
        file_hash = md5(osm_dest)
        size = osm_dest.stat().st_size
        print(f"    [ok] Saved {size:,} bytes  MD5={file_hash[:8]}...  to {osm_dest.relative_to(REPO_ROOT)}")

        entries.append({
            "label": "OSM Walk Network",
            "source_type": "osm_pedestrian_network",
            "tool": "osmnx",
            "bbox": bbox,
            "network_type": "walk",
            "n_nodes": nodes,
            "n_edges": edges,
            "dest": str(osm_dest.relative_to(REPO_ROOT)),
            "status": "downloaded",
            "md5": file_hash,
            "size_bytes": size,
            "downloaded_at": ts,
            "note": "OSM has no versioning. Timestamp is the only provenance for reproducibility.",
        })
    except ImportError:
        print("  [FAIL] osmnx not installed. Run: pip install osmnx")
        entries.append({"label": "OSM Walk Network", "status": "failed", "error": "osmnx not installed"})
    except Exception as e:
        print(f"  [FAIL] OSM download failed: {e}")
        entries.append({"label": "OSM Walk Network", "status": "failed", "error": str(e)})

    return entries


def download_lodes(config: dict, dry_run: bool, force: bool) -> list:
    """Download LEHD LODES WAC (workplace area characteristics) for California."""
    print("\n--- LODES Job Data ---")
    entries = []
    state_abbr = "ca"
    lodes_year = 2021  # Most recent stable LODES8 year
    url = (
        f"https://lehd.ces.census.gov/data/lodes/LODES8/{state_abbr}/wac/"
        f"{state_abbr}_wac_S000_JT00_{lodes_year}.csv.gz"
    )
    dest = REPO_ROOT / "data/raw" / "external" / "lodes" / f"{state_abbr}_wac_{lodes_year}.csv.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)

    entry = download_file(url, dest, f"LODES WAC CA {lodes_year}", dry_run=dry_run, force=force)
    entry["source_type"] = "lodes_wac"
    entry["lodes_version"] = "LODES8"
    entry["year"] = lodes_year
    entry["note"] = "State-wide CA file. Filter to SD county (county_fips=073) during EDA."
    entries.append(entry)
    return entries


GEOFABRIK_CALIFORNIA_PBF_URL = (
    "https://download.geofabrik.de/north-america/us/california-latest.osm.pbf"
)


def download_osm_pbf_for_r5(
    config: dict,
    dry_run: bool,
    force: bool,
    *,
    download_geofabrik_ca: bool,
) -> list:
    """
    Build `r5.osm_pbf` by clipping a regional extract (default: Geofabrik California) to `bbox`.
    Requires the `osmium` CLI (https://osmcode.org/osmium-tool/).
    Not included in `--sources all` (large download + external tool).
    """
    print("\n--- R5 OSM PBF (clip for r5py) ---")
    entries: list = []
    r5 = config.get("r5") or {}
    out_rel = str(r5.get("osm_pbf", "data/raw/osm/san_diego_study.osm.pbf")).replace("\\", "/")
    out = REPO_ROOT / out_rel
    src_rel = str(r5.get("geofabrik_source_pbf", "data/interim/osm/california-latest.osm.pbf")).replace(
        "\\", "/"
    )
    src = REPO_ROOT / src_rel

    bbox = config.get("bbox")
    if not bbox or len(bbox) != 4:
        print("  [FAIL] Missing bbox in config (need [min_lon, min_lat, max_lon, max_lat]).")
        entries.append(
            {
                "label": "R5 OSM PBF",
                "status": "failed",
                "error": "bbox missing",
            }
        )
        return entries

    if out.exists() and not force:
        print(f"  [SKIP] R5 PBF already exists at {out.relative_to(REPO_ROOT)}")
        entries.append(
            {
                "label": "R5 OSM PBF",
                "source_type": "osm_pbf_r5",
                "dest": str(out.relative_to(REPO_ROOT)),
                "status": "skipped_existing",
                "md5": md5(out),
                "size_bytes": out.stat().st_size,
            }
        )
        return entries

    if dry_run:
        print(f"  [DRY-RUN] Would clip regional PBF -> {out.relative_to(REPO_ROOT)}")
        entries.append({"label": "R5 OSM PBF", "status": "dry_run"})
        return entries

    if not src.is_file():
        if download_geofabrik_ca:
            print(f"  [DOWNLOAD] Geofabrik California PBF (~1.1 GB) -> {src.relative_to(REPO_ROOT)} ...")
            ent = download_file(
                GEOFABRIK_CALIFORNIA_PBF_URL,
                src,
                "Geofabrik California OSM PBF",
                dry_run=False,
                force=force,
                timeout=(60.0, None),
            )
            entries.append(ent)
            if ent.get("status") == "failed":
                return entries
        else:
            print(f"  [FAIL] Regional PBF not found: {src}")
            print("  Options:")
            print(f"    1) Download manually: {GEOFABRIK_CALIFORNIA_PBF_URL}")
            print(f"       Save as {src.relative_to(REPO_ROOT)} (or set r5.geofabrik_source_pbf)")
            print("    2) Re-run with --download-geofabrik-ca (streams ~1.1 GB)")
            print("    3) Run: python scripts/extract_osm_pbf.py --input <path-to-regional.osm.pbf>")
            entries.append(
                {
                    "label": "R5 OSM PBF",
                    "status": "failed",
                    "error": "regional PBF missing",
                }
            )
            return entries

    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_arg = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    out.parent.mkdir(parents=True, exist_ok=True)

    def _find_osmium() -> str | None:
        """
        Return a subprocess-safe osmium command string, or None if not found.

        On Windows, Conda installs the binary as 'osmium.EXE' (uppercase).
        osmium's own argument parser only strips lowercase '.exe' from argv[0],
        so passing the full path causes 'Unknown command or option osmium.EXE'.
        Fix: prefer the bare name "osmium" when it is on PATH (argv[0]="osmium"),
        or normalise the Conda path extension to lowercase before passing it.
        """
        import platform

        is_win = platform.system() == "Windows"

        # 1. Explicit env override
        env_exe = os.environ.get("OSMIUM_EXE", "").strip()
        if env_exe and Path(env_exe).is_file():
            p = Path(env_exe)
            if is_win:
                return str(p.parent / (p.stem + p.suffix.lower()))
            return str(p)

        # 2. Already on PATH — use bare name on Windows so argv[0]="osmium"
        if shutil.which("osmium"):
            return "osmium" if is_win else shutil.which("osmium")

        # 3. Conda prefix locations (common on Windows where Library\bin may not
        #    be in PATH for subprocess calls)
        conda_prefix = os.environ.get("CONDA_PREFIX", "").strip()
        if conda_prefix and is_win:
            for rel in (
                "Library/bin/osmium.exe",
                "Library/bin/osmium",
                "Scripts/osmium.exe",
                "bin/osmium",
            ):
                candidate = Path(conda_prefix) / rel
                if candidate.is_file():
                    # Normalise extension to lowercase so osmium parses argv[0] correctly
                    return str(candidate.parent / (candidate.stem + candidate.suffix.lower()))

        # 4. Generic fallback
        for name in ("osmium", "osmium-tool"):
            w = shutil.which(name)
            if w:
                return w

        return None

    osmium = _find_osmium()
    if osmium:
        cmd = [osmium, "extract", "-b", bbox_arg, str(src), "-o", str(out)]
        print(f"  [CLIP] {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  [FAIL] osmium extract failed: {e}")
            entries.append(
                {
                    "label": "R5 OSM PBF",
                    "status": "failed",
                    "error": str(e),
                }
            )
            return entries
        tool_used = "osmium"
    else:
        # Windows doesn't have `osmium` installed; try WSL (common on Windows dev setups).
        if shutil.which("wsl") is None:
            print("  [FAIL] `osmium` not on PATH, and `wsl` not available.")
            print("         Install osmium-tool on Windows, or install it inside WSL and re-run.")
            entries.append(
                {
                    "label": "R5 OSM PBF",
                    "status": "failed",
                    "error": "osmium not found (no WSL fallback)",
                }
            )
            return entries

        def _win_to_wsl_path(p: Path) -> str:
            # Example: C:\Users\me\path -> /mnt/c/Users/me/path
            pp = p.resolve()
            drive = pp.drive.rstrip(":").lower()
            rest = pp.as_posix().split(":", 1)[1].lstrip("/")
            return f"/mnt/{drive}/{rest}"

        wsl_src = _win_to_wsl_path(src)
        wsl_out = _win_to_wsl_path(out)
        wsl_cmd = ["wsl", "--", "osmium", "extract", "-b", bbox_arg, wsl_src, "-o", wsl_out]
        print(f"  [CLIP via WSL] {' '.join(wsl_cmd)}")
        try:
            subprocess.run(wsl_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  [FAIL] WSL `osmium extract` failed: {e}")
            print("         In WSL, install osmium-tool and re-run:")
            print("           sudo apt-get update && sudo apt-get install -y osmium-tool")
            entries.append(
                {
                    "label": "R5 OSM PBF",
                    "status": "failed",
                    "error": str(e),
                    "tool_used": "osmium-wsl",
                }
            )
            return entries
        tool_used = "osmium-wsl"

    ts = datetime.now(timezone.utc).isoformat()
    print(f"    [ok] {out.stat().st_size:,} bytes -> {out.relative_to(REPO_ROOT)}")
    entries.append(
        {
            "label": "R5 OSM PBF",
            "source_type": "osm_pbf_r5",
            "tool": tool_used,
            "bbox": bbox_arg,
            "source_pbf": str(src.relative_to(REPO_ROOT)),
            "dest": str(out.relative_to(REPO_ROOT)),
            "status": "downloaded",
            "md5": md5(out),
            "size_bytes": out.stat().st_size,
            "downloaded_at": ts,
        }
    )
    return entries


# ── Manifest writer ────────────────────────────────────────────────────────────

def write_manifest(all_entries: list, config: dict) -> Path:
    """Write provenance manifest to artifacts/logs/provenance/."""
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%d_%H%M")
    manifest = {
        "generated_at": ts.isoformat(),
        "city": config.get("city", "unknown"),
        "data_freeze_date": ts.strftime("%Y-%m-%d"),
        "sources": all_entries,
    }

    provenance_dir = REPO_ROOT / "artifacts/logs/provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    out_path = provenance_dir / f"data_manifest_{config.get('city', 'unknown')}_{ts_str}.json"

    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[ok] Provenance manifest written to {out_path.relative_to(REPO_ROOT)}")
    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download raw data for BayesTransitEquity.")
    parser.add_argument(
        "--config", default="configs/san_diego.yaml",
        help="Path to city config yaml (relative to repo root). Default: configs/san_diego.yaml"
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=["gtfs", "census", "osm", "osm_pbf", "lodes", "all"],
        default=["all"],
        help="Which data sources to download. Default: all (excludes osm_pbf)"
    )
    parser.add_argument(
        "--download-geofabrik-ca",
        action="store_true",
        help="With --sources osm_pbf: download Geofabrik California (~1.1 GB) if missing",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if files already exist (overrides freeze logic)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be downloaded without actually downloading"
    )
    parser.add_argument(
        "--refresh-mobility-catalog",
        action="store_true",
        help="Re-download feeds_v2.csv even if cache is fresh (GTFS URL resolution)",
    )
    args = parser.parse_args()

    sources = set(args.sources)
    if "all" in sources:
        sources = {"gtfs", "census", "osm", "lodes"}

    config = load_configs(args.config)
    city = config.get("city_label", config.get("city", "unknown"))

    print("=" * 70)
    print("BayesTransitEquity - Data Download")
    print(f"City    : {city}")
    print(f"Config  : {args.config}")
    print(f"Sources : {', '.join(sorted(sources))}")
    print(f"Force   : {args.force}")
    print(f"Dry run : {args.dry_run}")
    print(f"Refresh Mobility catalog : {args.refresh_mobility_catalog}")
    print("=" * 70)

    all_entries = []

    if "gtfs" in sources:
        all_entries += download_gtfs(
            config,
            dry_run=args.dry_run,
            force=args.force,
            refresh_mobility_catalog=args.refresh_mobility_catalog,
        )

    if "census" in sources:
        all_entries += download_census(config, dry_run=args.dry_run, force=args.force)

    if "osm" in sources:
        all_entries += download_osm(config, dry_run=args.dry_run, force=args.force)

    if "lodes" in sources:
        all_entries += download_lodes(config, dry_run=args.dry_run, force=args.force)

    if "osm_pbf" in sources:
        all_entries += download_osm_pbf_for_r5(
            config,
            dry_run=args.dry_run,
            force=args.force,
            download_geofabrik_ca=args.download_geofabrik_ca,
        )

    if not args.dry_run:
        manifest_path = write_manifest(all_entries, config)

    # Summary
    print("\n--- Summary ---")
    statuses = {}
    for e in all_entries:
        s = e.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    for status, count in sorted(statuses.items()):
        icon = "[ok]" if status in ("downloaded", "skipped_existing") else "[x]"
        print(f"  {icon}  {status}: {count}")

    failed = [e for e in all_entries if e.get("status") == "failed"]
    if failed:
        print("\n  Failed sources:")
        for e in failed:
            print(f"    - {e['label']}: {e.get('error', 'unknown error')}")
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
