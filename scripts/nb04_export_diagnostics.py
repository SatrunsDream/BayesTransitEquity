#!/usr/bin/env python3
"""
Export publication-grade MCMC diagnostics for notebook 04 (BYM2 tract model).

Aligns with project goals (PROJECT_BRIEF / PAPER.md): traceable run bundles, R-hat & ESS
reporting, and visuals recommended in modern Bayesian workflow (Vehtari et al. on R-hat/ESS;
ArviZ rank plots as primary chain-mixing check).

Typical use (after nb04 saves InferenceData to NetCDF):

    python scripts/nb04_export_diagnostics.py --repo-root . --run-id 2026-04-03

Or auto-pick latest posterior checkpoint:

    python scripts/nb04_export_diagnostics.py --repo-root . --latest-idata

Outputs under artifacts/ (tables + figures) and does not modify the NetCDF.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


def _try_git_sha(repo_root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _package_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("pymc", "arviz", "numpy", "pandas", "pytensor"):
        try:
            m = __import__(name)
            out[name] = getattr(m, "__version__", "?")
        except ImportError:
            out[name] = "not_installed"
    return out


def _load_config(repo_root: Path) -> dict[str, Any]:
    defaults_path = repo_root / "configs" / "defaults.yaml"
    city_path = repo_root / "configs" / "san_diego.yaml"
    with open(defaults_path, encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}
    with open(city_path, encoding="utf-8") as f:
        city = yaml.safe_load(f) or {}
    merged = dict(base)
    for k, v in city.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


def _find_latest_idata(posterior_dir: Path) -> tuple[str, Path]:
    paths = sorted(posterior_dir.glob("*_idata.nc"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        raise FileNotFoundError(f"No *_idata.nc under {posterior_dir}")
    p = paths[0]
    rid = p.name.replace("_idata.nc", "")
    return rid, p


def diagnostic_var_names(idata: az.InferenceData) -> list[str]:
    """Scalar / vector parameters for summary and plots (exclude mu, phi, high-dim latent fields)."""
    post = idata.posterior
    names: list[str] = []
    for v in ("alpha", "rho", "sigma"):
        if v in post:
            names.append(v)
    if "sigma_obs" in post:
        names.append("sigma_obs")
    if "beta" in post:
        names.append("beta")
    return names


def _count_divergences(idata: az.InferenceData) -> int:
    try:
        div = idata.sample_stats["diverging"]
        return int(div.sum().values.item())
    except (KeyError, AttributeError, ValueError):
        return -1


def _sampling_dimensions(idata: az.InferenceData) -> tuple[int, int]:
    post = idata.posterior
    if "chain" in post.dims and "draw" in post.dims:
        return int(post.sizes["chain"]), int(post.sizes["draw"])
    return 0, 0


def write_sampling_meta(
    idata: az.InferenceData,
    path: Path,
    *,
    run_id: str,
    idata_path_display: str,
    extra: dict[str, Any] | None = None,
) -> pd.DataFrame:
    n_chains, n_draws = _sampling_dimensions(idata)
    div = _count_divergences(idata)
    row: dict[str, Any] = {
        "run_id": run_id,
        "idata_path": idata_path_display,
        "n_chains": n_chains,
        "n_draws_per_chain": n_draws,
        "divergences_total": div,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        bfmi = np.asarray(az.bfmi(idata), dtype=float)
        row["bfmi_min"] = float(np.min(bfmi))
        row["bfmi_mean"] = float(np.mean(bfmi))
        row["bfmi_max"] = float(np.max(bfmi))
    except Exception:
        row["bfmi_min"] = np.nan
        row["bfmi_mean"] = np.nan
        row["bfmi_max"] = np.nan

    try:
        t = idata.sample_stats.get("tree_size")
        if t is not None:
            row["tree_size_mean"] = float(np.mean(t.values))
    except Exception:
        pass

    if extra:
        row.update(extra)
    df = pd.DataFrame([row])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def _rel_under_repo(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_parameter_table(
    idata: az.InferenceData,
    path: Path,
    var_names: list[str],
) -> pd.DataFrame:
    """ArviZ summary (rank-normalized R-hat by default); no divergences column on every row."""
    # kind="all" includes ess_bulk / ess_tail / r_hat (rank-normalized by default in ArviZ ≥0.11).
    tab = az.summary(idata, var_names=var_names, round_to=4, kind="all")
    out = tab.reset_index()
    out = out.rename(columns={out.columns[0]: "parameter"})
    drop = [c for c in out.columns if "divergen" in c.lower()]
    if drop:
        out = out.drop(columns=drop)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


def convergence_assessment(param_df: pd.DataFrame, n_chains: int) -> dict[str, Any]:
    """Heuristic checks vs common reporting targets (Vehtari / ArviZ docs)."""
    ess = param_df["ess_bulk"].astype(float)
    rhat = param_df["r_hat"].astype(float)
    ess_rule = 100 * max(n_chains, 1)
    return {
        "n_parameters_rows": int(len(param_df)),
        "min_ess_bulk": float(ess.min()),
        "min_ess_tail": float(param_df["ess_tail"].astype(float).min()),
        "max_r_hat": float(rhat.max()),
        "n_r_hat_above_1_01": int((rhat > 1.01).sum()),
        "n_r_hat_above_1_05": int((rhat > 1.05).sum()),
        "n_ess_bulk_below_400": int((ess < 400).sum()),
        "n_ess_bulk_below_100xchains": int((ess < ess_rule).sum()),
        "target_r_hat": 1.01,
        "target_ess_bulk_rule_of_thumb": max(400, ess_rule),
        "pass_r_hat_all_le_1_01": bool((rhat <= 1.01).all()),
        "pass_ess_bulk_all_ge_400": bool((ess >= 400).all()),
    }


def write_run_manifest(
    path: Path,
    *,
    repo_root: Path,
    run_id: str,
    idata_path: Path,
    config: dict[str, Any],
    assessment: dict[str, Any],
    var_names: list[str],
) -> None:
    model_cfg = config.get("model", {})
    acc_cfg = config.get("accessibility", {})
    manifest = {
        "run_id": run_id,
        "idata_nc": _rel_under_repo(repo_root, idata_path),
        "purpose": "BayesTransitEquity nb04 BYM2 — reproducibility bundle",
        "paper_alignment": {
            "targets": "R-hat <= 1.01, adequate bulk ESS (see assessment); rank plots + energy plot in figures/",
            "references": "Vehtari et al. rank-normalized R-hat; ArviZ MCMC diagnostics chapter",
        },
        "model_config_snapshot": model_cfg,
        "accessibility_snapshot": {
            "travel_time_threshold_min": acc_cfg.get("travel_time_threshold_min"),
        },
        "diagnostic_var_names": var_names,
        "convergence_assessment": assessment,
        "environment": {
            "packages": _package_versions(),
            "git_sha": _try_git_sha(repo_root),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)


def write_recommendations(path: Path, assessment: dict[str, Any]) -> None:
    lines = [
        "# nb04 MCMC — automated recommendations",
        f"- max R-hat (tracked parameters): {assessment['max_r_hat']:.4f} (target <= {assessment['target_r_hat']})",
        f"- min bulk ESS: {assessment['min_ess_bulk']:.1f} (target >= {assessment['target_ess_bulk_rule_of_thumb']:.0f} rule-of-thumb)",
        f"- parameters with R-hat > 1.01: {assessment['n_r_hat_above_1_01']}",
        f"- parameters with bulk ESS < 400: {assessment['n_ess_bulk_below_400']}",
        "",
        "If fixed effects (alpha, beta) fail thresholds while sigma/rho pass:",
        "  - Increase `model.draws` (e.g. 4000–8000) and/or `model.tune`.",
        "  - Slightly increase `model.fixed_obs_sigma` (e.g. 0.06–0.10) as a sensitivity run.",
        "  - Try `model.likelihood: student_t` for robustness (same obs_noise mode).",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_diagnostics_figures(
    idata: az.InferenceData,
    fig_dir: Path,
    run_id: str,
    var_names: list[str],
) -> list[Path]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Rank plots (preferred mixing check vs trace alone)
    try:
        ax = az.plot_rank(idata, var_names=var_names)
        if isinstance(ax, np.ndarray):
            fig = ax.ravel()[0].figure
        else:
            fig = ax.figure
        p = fig_dir / f"pipeline__04_rank_plot__{run_id}.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(p)
    except Exception as e:
        print(f"Warning: plot_rank failed: {e}", file=sys.stderr)

    try:
        ax = az.plot_trace(idata, var_names=var_names, figsize=(12, 10))
        if isinstance(ax, np.ndarray):
            fig = ax.ravel()[0].figure
        else:
            fig = ax.figure
        p = fig_dir / f"pipeline__04_trace_plot__{run_id}.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(p)
    except Exception as e:
        print(f"Warning: plot_trace failed: {e}", file=sys.stderr)

    try:
        ax = az.plot_energy(idata, figsize=(8, 4))
        fig = ax.figure
        p = fig_dir / f"pipeline__04_energy_plot__{run_id}.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(p)
    except Exception as e:
        print(f"Warning: plot_energy failed: {e}", file=sys.stderr)

    # Local ESS vs rank-based ESS (bulk) — highlights which parameters need more samples
    try:
        ax = az.plot_ess(
            idata,
            var_names=var_names,
            kind="local",
            figsize=(10, 6),
        )
        if isinstance(ax, np.ndarray):
            fig = ax.ravel()[0].figure
        else:
            fig = ax.figure
        p = fig_dir / f"pipeline__04_ess_local__{run_id}.png"
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(p)
    except Exception as e:
        print(f"Warning: plot_ess(local) failed: {e}", file=sys.stderr)

    return written


def optional_equity_bridge(
    repo_root: Path,
    run_id: str,
    tables_dir: Path,
) -> Path | None:
    """Merge deterministic nb03 Spearman with nb04 equity table when both exist."""
    acc_glob = list((repo_root / "artifacts" / "tables").glob(f"pipeline__03_accessibility_summary__{run_id}.csv"))
    eq_glob = list((repo_root / "artifacts" / "tables").glob(f"pipeline__04_equity_spearman__{run_id}.csv"))
    if not acc_glob or not eq_glob:
        return None
    acc = pd.read_csv(acc_glob[0])
    eq = pd.read_csv(eq_glob[0])
    sub = acc[acc["key"] == "spearman_jobs_disadvantage_z"]
    det_val = float(sub["value"].iloc[0]) if len(sub) else np.nan
    rows = [
        {"metric": "spearman_jobs_vs_disadvantage_z_deterministic_nb03", "value": det_val, "source": str(acc_glob[0].name)},
    ]
    for _, r in eq.iterrows():
        v = str(r["variable"])
        metric = v if v.startswith("posterior_") else f"posterior_{v}"
        rows.append(
            {
                "metric": metric,
                "value": float(r["spearman_rho"]),
                "p_value": float(r["p_value"]),
                "source": eq_glob[0].name,
            }
        )
    out = pd.DataFrame(rows)
    path = tables_dir / f"pipeline__04_equity_bridge__{run_id}.csv"
    out.to_csv(path, index=False)
    return path


def main() -> int:
    p = argparse.ArgumentParser(description="Export nb04 MCMC diagnostics bundle.")
    p.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root (contains configs/, data/, artifacts/)")
    p.add_argument("--run-id", type=str, default=None, help="Run id matching data/processed/posteriors/{run_id}_idata.nc")
    p.add_argument("--latest-idata", action="store_true", help="Use most recently modified *_idata.nc under posteriors/")
    p.add_argument("--idata", type=Path, default=None, help="Explicit path to InferenceData NetCDF (run id from stem if omitted)")
    p.add_argument("--no-figures", action="store_true", help="Skip PNG exports")
    p.add_argument("--no-equity-bridge", action="store_true", help="Skip optional nb03+nb04 equity merge")
    args = p.parse_args()

    repo_root = args.repo_root.resolve()
    posterior_dir = repo_root / "data" / "processed" / "posteriors"
    tables_dir = repo_root / "artifacts" / "tables"
    fig_dir = repo_root / "artifacts" / "figures"

    if args.idata is not None:
        idata_path = args.idata.resolve()
        stem = idata_path.stem
        run_id = args.run_id or (stem[: -len("_idata")] if stem.endswith("_idata") else stem)
    elif args.latest_idata:
        run_id, idata_path = _find_latest_idata(posterior_dir)
    elif args.run_id:
        run_id = args.run_id
        idata_path = posterior_dir / f"{run_id}_idata.nc"
    else:
        p.error("Provide one of: --run-id, --latest-idata, or --idata")

    if not idata_path.is_file():
        print(f"Error: idata not found: {idata_path}", file=sys.stderr)
        return 1

    print(f"Loading {idata_path}")
    idata = az.from_netcdf(idata_path)

    config = _load_config(repo_root)
    var_names = diagnostic_var_names(idata)
    if not var_names:
        print("Error: no recognized parameters in idata.posterior", file=sys.stderr)
        return 1

    diag_path = tables_dir / f"pipeline__04_model_diagnostics__{run_id}.csv"
    meta_path = tables_dir / f"pipeline__04_sampling_meta__{run_id}.csv"
    manifest_path = tables_dir / f"pipeline__04_run_manifest__{run_id}.json"
    reco_path = tables_dir / f"pipeline__04_mcmc_recommendations__{run_id}.md"

    n_chains, n_draws = _sampling_dimensions(idata)
    param_df = write_parameter_table(idata, diag_path, var_names)
    assessment = convergence_assessment(param_df, n_chains)
    write_sampling_meta(
        idata,
        meta_path,
        run_id=run_id,
        idata_path_display=_rel_under_repo(repo_root, idata_path),
        extra={
            "min_ess_bulk_tracked": assessment["min_ess_bulk"],
            "max_r_hat_tracked": assessment["max_r_hat"],
            "pass_r_hat_1_01": assessment["pass_r_hat_all_le_1_01"],
            "pass_ess_400": assessment["pass_ess_bulk_all_ge_400"],
        },
    )
    write_run_manifest(
        manifest_path,
        repo_root=repo_root,
        run_id=run_id,
        idata_path=idata_path,
        config=config,
        assessment=assessment,
        var_names=var_names,
    )
    write_recommendations(reco_path, assessment)

    if not args.no_figures:
        paths = plot_diagnostics_figures(idata, fig_dir, run_id, var_names)
        for fp in paths:
            print("Wrote", fp.relative_to(repo_root))

    if not args.no_equity_bridge:
        br = optional_equity_bridge(repo_root, run_id, tables_dir)
        if br is not None:
            print("Wrote", br.relative_to(repo_root))

    print("Wrote", diag_path.relative_to(repo_root))
    print("Wrote", meta_path.relative_to(repo_root))
    print("Wrote", manifest_path.relative_to(repo_root))
    print("Wrote", reco_path.relative_to(repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
