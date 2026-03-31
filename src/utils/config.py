from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import yaml


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
    """Stable id shared across pipeline notebooks 01–07: PIPELINE_RUN_ID, else calendar date."""
    v = os.environ.get("PIPELINE_RUN_ID", "").strip()
    if v:
        return v
    return date.today().isoformat()
