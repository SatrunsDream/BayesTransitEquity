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
