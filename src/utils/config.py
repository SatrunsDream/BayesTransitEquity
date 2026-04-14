from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import yaml


# Human-readable artifact stems for BYM2 runs (use with PIPELINE_RUN_ID / PIPELINE_POSTERIOR_STEM).
# Prefer these over calendar dates so outputs describe the estimand.
RUN_FIT_RAW_ZSCORE_X = "fit_raw_zscore_x"
"""BYM2 on z-scored raw **X** (``PIPELINE_NO_SPATIAL_PLUS=1``) — paper **primary** (D011)."""

RUN_FIT_SPATIAL_PLUS_X = "fit_spatial_plus_x"
"""BYM2 on **Spatial+** residualized **X** (eigen removal) — **sensitivity** estimand (D011)."""

# Map old date-based run folders / filenames (optional migration).
LEGACY_BYM2_RUN_ID_TO_SEMANTIC = {
    "2026-04-05": RUN_FIT_RAW_ZSCORE_X,
    "2026-04-06": RUN_FIT_SPATIAL_PLUS_X,
}


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_merged_config(repo_root: Path) -> dict:
    with open(repo_root / "configs" / "defaults.yaml", encoding="utf-8") as f:
        defaults = yaml.safe_load(f)
    with open(repo_root / "configs" / "san_diego.yaml", encoding="utf-8") as f:
        city = yaml.safe_load(f)
    return deep_merge(defaults, city)


def pipeline_run_id() -> str:
    """Single run id for artifact names across notebooks (PIPELINE_RUN_ID env, else UTC minute)."""
    v = os.environ.get("PIPELINE_RUN_ID", "").strip()
    if v:
        return v
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")


def artifact_run_id() -> str:
    """Stable id for pipeline artifacts: ``PIPELINE_RUN_ID`` if set, else calendar date (``YYYY-MM-DD``).

    For reproducible BYM2 fits, set ``PIPELINE_RUN_ID`` to :data:`RUN_FIT_RAW_ZSCORE_X` or
    :data:`RUN_FIT_SPATIAL_PLUS_X` (see notebooks 04–05 pin cells) instead of relying on dates.
    """
    v = os.environ.get("PIPELINE_RUN_ID", "").strip()
    if v:
        return v
    return date.today().isoformat()


def legacy_stems_for_semantic(semantic: str) -> list[str]:
    """Date-style run IDs in :data:`LEGACY_BYM2_RUN_ID_TO_SEMANTIC` that map to *semantic*."""
    return sorted(k for k, v in LEGACY_BYM2_RUN_ID_TO_SEMANTIC.items() if v == semantic)


def netcdf_file_is_readable(path: Path) -> bool:
    """True if *path* exists and passes a quick HDF5 open (catches truncated/corrupt NetCDF4)."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size < 512:
            return False
    except OSError:
        return False
    try:
        import h5py
    except ImportError:
        return True
    try:
        with h5py.File(path, "r") as f:
            f.keys()
        return True
    except OSError:
        return False


def resolve_posterior_idata_nc(
    repo_root: Path,
    run_id: str,
    *,
    env_key: str = "PIPELINE_IDATA_NC",
) -> Path:
    """Resolve a readable ``*_idata.nc`` for *run_id*.

    Order: env *env_key*, sidecar ``pipeline__04_idata_nc__{run_id}.txt``,
    ``{run_id}_idata.nc``, ``{run_id}_idata_recovered.nc``, legacy date stems from
    :data:`LEGACY_BYM2_RUN_ID_TO_SEMANTIC`, ``artifacts/models`` fallbacks, then newest
    glob ``*{run_id}*idata*.nc`` under posteriors. Skips files that fail
    :func:`netcdf_file_is_readable` so a good backup can be chosen over a corrupt primary.
    """
    post = repo_root / "data" / "processed" / "posteriors"
    pipe_tbl = repo_root / "artifacts" / "tables" / "pipeline"

    def first_readable(paths: list[Path]) -> Path | None:
        for p in paths:
            if netcdf_file_is_readable(p):
                return p.resolve()
        return None

    env = os.environ.get(env_key, "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = repo_root / p
        got = first_readable([p])
        if got is not None:
            return got

    candidates: list[Path] = []
    sidecar = pipe_tbl / f"pipeline__04_idata_nc__{run_id}.txt"
    if sidecar.is_file():
        line = sidecar.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        sp = Path(line)
        if not sp.is_absolute():
            sp = repo_root / sp
        candidates.append(sp)

    candidates.append(post / f"{run_id}_idata.nc")
    candidates.append(post / f"{run_id}_idata_recovered.nc")
    for stem in legacy_stems_for_semantic(run_id):
        candidates.append(post / f"{stem}_idata.nc")

    candidates.extend(
        [
            repo_root / "artifacts" / "models" / f"{run_id}_idata.nc",
            repo_root / "artifacts" / "models" / "pipeline" / f"{run_id}_idata.nc",
        ]
    )

    seen: set[str] = set()
    uniq: list[Path] = []
    for p in candidates:
        k = p.as_posix()
        if k not in seen:
            seen.add(k)
            uniq.append(p)

    got = first_readable(uniq)
    if got is not None:
        return got

    if post.is_dir():
        glob_hits = sorted(
            (p for p in post.glob(f"*{run_id}*idata*.nc") if p.is_file()),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        got = first_readable(glob_hits)
        if got is not None:
            return got

    raise FileNotFoundError(
        f"No readable idata NetCDF for run_id={run_id!r}. Checked env {env_key}, {sidecar.name}, "
        f"{run_id}_idata.nc, {run_id}_idata_recovered.nc, legacy date stems, and glob under {post}. "
        "Restore from backup or re-run notebooks/04_bayesian_model.ipynb."
    )
