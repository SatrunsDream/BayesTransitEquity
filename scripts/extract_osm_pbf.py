#!/usr/bin/env python3
"""
Clip a regional OSM .pbf (e.g. Geofabrik California) to the study bbox for r5py.

Requires the osmium CLI: https://osmcode.org/osmium-tool/

Example:
  python scripts/extract_osm_pbf.py --input data/interim/osm/california-latest.osm.pbf

Or set r5.geofabrik_source_pbf in configs/san_diego.yaml and run with no --input.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.utils.config import load_merged_config  # noqa: E402
from src.utils.paths import find_osmium_executable  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Clip regional OSM PBF to study bbox (r5py).")
    parser.add_argument("--config", default="configs/san_diego.yaml", help="City config (merged with defaults).")
    parser.add_argument(
        "--input",
        help="Path to regional .osm.pbf (default: r5.geofabrik_source_pbf in config).",
    )
    parser.add_argument("--output", help="Override r5.osm_pbf output path from config.")
    args = parser.parse_args()

    cfg = load_merged_config(REPO_ROOT)
    r5 = cfg.get("r5") or {}
    out = Path(args.output) if args.output else REPO_ROOT / str(
        r5.get("osm_pbf", "data/raw/osm/san_diego_study.osm.pbf")
    ).replace("\\", "/")

    inp = args.input or r5.get("geofabrik_source_pbf")
    if not inp:
        print(
            "ERROR: No input PBF. Set `r5.geofabrik_source_pbf` in configs/san_diego.yaml "
            "or pass --input <path>.\n"
            "One-time download: https://download.geofabrik.de/north-america/us/california-latest.osm.pbf (~1.1 GB)"
        )
        sys.exit(1)

    inp = Path(inp)
    if not inp.is_absolute():
        inp = REPO_ROOT / inp

    if not inp.is_file():
        print(f"ERROR: Input PBF not found: {inp}")
        print("Download Geofabrik California once, or run:")
        print("  python scripts/download_data.py --config configs/san_diego.yaml --sources osm_pbf --download-geofabrik-ca")
        sys.exit(1)

    def _win_to_wsl_path(p: Path) -> str:
        """Convert `C:\\Users\\...` → `/mnt/c/Users/...` for WSL subprocess calls."""
        pp = p.resolve()
        drive = pp.drive.rstrip(":").lower()  # e.g. "C"
        rest = pp.as_posix().split(":", 1)[1].lstrip("/")  # e.g. "Users/..."
        return f"/mnt/{drive}/{rest}"

    exe = find_osmium_executable()

    bbox = cfg.get("bbox")
    if not bbox or len(bbox) != 4:
        print("ERROR: bbox missing or invalid in merged config.")
        sys.exit(1)
    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_arg = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    out.parent.mkdir(parents=True, exist_ok=True)
    if exe:
        cmd = [exe, "extract", "-b", bbox_arg, str(inp), "-o", str(out)]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True)
    else:
        use_wsl = os.environ.get("BAYESTRANSIT_OSMIUM_USE_WSL", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not use_wsl:
            print(
                "ERROR: `osmium` not found.\n"
                "  conda: `conda activate <env>` (so CONDA_PREFIX is set), or set OSMIUM_EXE to\n"
                "  the full path to osmium.exe (often %CONDA_PREFIX%\\Library\\bin\\osmium.exe).\n"
                "  Optional WSL: set BAYESTRANSIT_OSMIUM_USE_WSL=1 and install osmium-tool in WSL.",
            )
            sys.exit(1)

        if shutil.which("wsl") is None:
            print("ERROR: BAYESTRANSIT_OSMIUM_USE_WSL=1 but `wsl` not on PATH.")
            sys.exit(1)

        wsl_inp = _win_to_wsl_path(inp)
        wsl_out = _win_to_wsl_path(out)
        inner = (
            f"osmium extract -b {shlex.quote(bbox_arg)} "
            f"{shlex.quote(wsl_inp)} -o {shlex.quote(wsl_out)}"
        )
        wsl_cmd = ["wsl", "--", "sh", "-lc", inner]
        print("Running via WSL: wsl -- sh -lc", repr(inner))
        try:
            subprocess.run(wsl_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(
                "\nERROR: WSL `osmium` failed. Install inside WSL, then re-run:\n"
                "  sudo apt-get update && sudo apt-get install -y osmium-tool\n",
                file=sys.stderr,
            )
            raise e
    try:
        rel = out.relative_to(REPO_ROOT)
    except ValueError:
        rel = out
    print(f"[ok] Wrote {rel}")


if __name__ == "__main__":
    main()
