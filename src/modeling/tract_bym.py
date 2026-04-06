"""
tract_bym.py — BYM2 hierarchical spatial model for transit equity

Model:
    y_std[i] ~ Normal(mu[i], obs_scale)   or   StudentT(nu, mu[i], obs_scale)
    mu[i]    = alpha + X[i] @ beta + phi[i]
    phi[i]   = sigma * (sqrt(rho/scale) * u[i] + sqrt(1-rho) * v[i])
    u        ~ ICAR(W)          # structured spatial effect
    v        ~ Normal(0, 1)^n   # unstructured (iid) effect
    alpha    ~ Normal(0, 1)
    beta     ~ Normal(0, 0.5)^k
    rho      ~ Beta(2, 2)        # mixing; avoids boundary trapping at 0/1
    sigma    ~ Exponential(2)    # PC prior; mean=0.5 on standardised scale

Observation scale ``obs_scale`` (on the standardised *y* scale):
    - ``obs_noise="fixed"``: constant ``fixed_obs_sigma`` (default 0.05). Removes the
      free σ_obs vs σ ridge for deterministic r5py summaries (recommended).
    - ``obs_noise="estimated"``: ``sigma_obs ~ HalfNormal(estimated_obs_sigma_prior_scale)``.

Likelihood:
    - ``normal`` (default) or ``student_t`` with fixed ``student_t_nu`` (heavy tails).

y_std MUST be pre-standardised (mean=0, sd=1) by the caller.
Back-transform posteriors:  y_hat_orig = y_hat_std * y_sd + y_mean

References
----------
Riebler et al. (2016) — BYM2 parameterisation
Simpson et al. (2017) — Penalised Complexity priors
"""

from __future__ import annotations

import warnings
from typing import Literal, Sequence

import numpy as np
import pymc as pm
import pytensor.tensor as pt


# ---------------------------------------------------------------------------
# ICAR prior helper
# ---------------------------------------------------------------------------

def _build_icar_prior(W: np.ndarray, name: str = "u") -> pt.TensorVariable:
    """
    Add an ICAR structured spatial random effect to the active PyMC model.

    Uses pairwise-difference representation with a sum-to-zero soft constraint.
    The (n-1) free parameters are sampled as N(0,1); the last is set to
    -sum(free) so the vector is exactly zero-mean.

    Pairwise penalties: exp(-0.5 * sum_{i~j} (u_i - u_j)^2)
    are added via pm.Potential to give the ICAR density.

    Parameters
    ----------
    W    : (n, n) symmetric binary adjacency matrix
    name : variable name prefix in the model

    Returns
    -------
    u : (n,) Deterministic TensorVariable — zero-mean ICAR effect (unit scale)
    """
    n = W.shape[0]

    # Edge list (upper triangle only — each edge counted once)
    rows, cols = np.where(np.triu(W) > 0)

    # Free parameters: n-1; last determined by sum-to-zero
    u_free = pm.Normal(f"{name}_free", 0.0, 1.0, shape=n - 1)
    u_last = -pt.sum(u_free)
    u_raw  = pt.concatenate([u_free, pt.reshape(u_last, (1,))])

    # ICAR pairwise-difference penalty
    u_diff = u_raw[rows] - u_raw[cols]
    pm.Potential(f"{name}_icar_penalty", -0.5 * pt.sum(pt.square(u_diff)))

    return pm.Deterministic(name, u_raw, dims="tract")


# ---------------------------------------------------------------------------
# Main model builder
# ---------------------------------------------------------------------------

def build_tract_bym_normal(
    *,
    W: np.ndarray,
    scaling_factor: float,
    X: np.ndarray,
    geoids: Sequence[str],
    cov_names: Sequence[str],
    y_std: np.ndarray | None = None,
    y_log: np.ndarray | None = None,
    likelihood: Literal["normal", "student_t"] = "normal",
    obs_noise: Literal["fixed", "estimated"] = "fixed",
    fixed_obs_sigma: float = 0.05,
    estimated_obs_sigma_prior_scale: float = 0.2,
    student_t_nu: float = 4.0,
    beta_sigma: float = 0.5,
) -> pm.Model:
    """
    Build a BYM2 Normal model for standardised transit accessibility.

    Parameters
    ----------
    W              : (n, n) symmetric binary adjacency matrix
    scaling_factor : Riebler scaling factor for ICAR (from scaling_factor_sp)
    X              : (n, k) design matrix — MUST be pre-standardised (z-score)
    y_std          : (n,) response — MUST be standardised (mean=0, sd=1). Use ``y_std=``.
    y_log          : deprecated alias for ``y_std`` (emits ``DeprecationWarning``; still must be
                     standardised — raw log1p will miscalibrate priors).
    likelihood     : ``"normal"`` or ``"student_t"`` (nu = ``student_t_nu``, must be > 2).
    obs_noise      : ``"fixed"`` uses ``fixed_obs_sigma`` only (no ``sigma_obs`` RV);
                     ``"estimated"`` samples ``sigma_obs ~ HalfNormal(estimated_obs_sigma_prior_scale)``.
    fixed_obs_sigma : observation SD when ``obs_noise="fixed"`` (standardised *y* scale).
    estimated_obs_sigma_prior_scale : HalfNormal scale when ``obs_noise="estimated"``.
    student_t_nu   : degrees of freedom for Student-t likelihood (> 2).
    beta_sigma     : prior SD for beta coefficients on standardised y scale. Default 0.5;
                     set to 0.3 to regularise the spatial-confounding ridge more strongly
                     (recommended when using a composite covariate like disadvantage_z).
    geoids         : length-n sequence of GEOID strings (for coords)
    cov_names      : length-k sequence of covariate names (for coords)

    Returns
    -------
    model : pm.Model (not yet sampled)
    """
    # Accept y_log as a deprecated alias for y_std
    if y_std is None and y_log is not None:
        warnings.warn(
            "y_log= is deprecated; pass y_std= instead. "
            "Note: the response should now be pre-standardised (mean=0, sd=1).",
            DeprecationWarning,
            stacklevel=2,
        )
        y_std = y_log
    elif y_std is None:
        raise TypeError("build_tract_bym_normal() missing required argument: 'y_std'")

    if likelihood not in ("normal", "student_t"):
        raise ValueError(f"likelihood must be 'normal' or 'student_t', got {likelihood!r}")
    if obs_noise not in ("fixed", "estimated"):
        raise ValueError(f"obs_noise must be 'fixed' or 'estimated', got {obs_noise!r}")
    if obs_noise == "fixed" and fixed_obs_sigma <= 0:
        raise ValueError("fixed_obs_sigma must be positive when obs_noise='fixed'")
    if student_t_nu <= 2:
        raise ValueError("student_t_nu must be > 2 for finite variance")

    n, k = X.shape
    assert y_std.shape[0] == n,  f"y_std length {y_std.shape[0]} != n {n}"
    assert len(geoids)    == n,  f"geoids length {len(geoids)} != n {n}"
    assert len(cov_names) == k,  f"cov_names length {len(cov_names)} != k {k}"
    assert W.shape        == (n, n), f"W shape {W.shape} != ({n},{n})"
    assert scaling_factor > 0,   "scaling_factor must be positive"

    scale = float(scaling_factor)

    # Clean inputs — replace any residual non-finite values
    X_arr = np.nan_to_num(np.asarray(X, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    y_arr = np.nan_to_num(np.asarray(y_std, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)

    with pm.Model(
        coords={"tract": list(geoids), "covariate": list(cov_names)}
    ) as model:

        # ── Data containers ──────────────────────────────────────────────
        X_data = pm.Data("X_data", X_arr, dims=("tract", "covariate"))
        y_data = pm.Data("y_data", y_arr, dims="tract")

        # ── Fixed effects ─────────────────────────────────────────────────
        # Tighter priors appropriate for standardised (mean=0, sd=1) y.
        # beta_sigma is configurable: 0.5 (default) for full covariate sets;
        # 0.3 when using composites (e.g. disadvantage_z) to tighten the
        # spatial-confounding ridge and improve HMC geometry.
        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0)
        beta  = pm.Normal("beta",  mu=0.0, sigma=float(beta_sigma), dims="covariate")

        # ── Variance parameters ───────────────────────────────────────────
        # PC prior on sigma: Exponential(lam=2) → mean=0.5, P(sigma>1)≈0.13
        # This is calibrated for standardised y.
        sigma = pm.Exponential("sigma", lam=2.0)

        # Observation scale: fixed constant (recommended for near-deterministic y) or
        # estimated HalfNormal — avoids σ vs σ_obs ridge when fixed.
        if obs_noise == "fixed":
            obs_scale = pt.as_tensor_variable(float(fixed_obs_sigma))
        else:
            obs_scale = pm.HalfNormal(
                "sigma_obs",
                sigma=float(estimated_obs_sigma_prior_scale),
            )

        # ── BYM2 mixing parameter ─────────────────────────────────────────
        # Beta(2,2): symmetric, unimodal at 0.5, avoids mass near 0 and 1.
        # Prior mean = 0.5 (equal mix of spatial and iid).
        rho = pm.Beta("rho", alpha=2.0, beta=2.0)

        # ── Spatial random effects ─────────────────────────────────────────
        # iid component
        v = pm.Normal("v", 0.0, 1.0, dims="tract")

        # Structured ICAR component (unit-variance, zero-sum)
        u = _build_icar_prior(W, name="u")

        # BYM2 combination: scaled to unit variance before multiplying by sigma
        phi_raw = (
            pt.sqrt(rho / scale) * u
            + pt.sqrt(1.0 - rho) * v
        )
        phi = pm.Deterministic("phi", sigma * phi_raw, dims="tract")

        # ── Linear predictor ──────────────────────────────────────────────
        mu = pm.Deterministic(
            "mu",
            alpha + pm.math.dot(X_data, beta) + phi,
            dims="tract",
        )

        # ── Likelihood ────────────────────────────────────────────────────
        if likelihood == "normal":
            pm.Normal(
                "y_obs",
                mu=mu,
                sigma=obs_scale,
                observed=y_data,
                dims="tract",
            )
        else:
            pm.StudentT(
                "y_obs",
                nu=float(student_t_nu),
                mu=mu,
                sigma=obs_scale,
                observed=y_data,
                dims="tract",
            )

    return model


# ---------------------------------------------------------------------------
# Posterior summary helper
# ---------------------------------------------------------------------------

def posterior_summary(
    idata,
    y_mean: float,
    y_sd: float,
    geoids: Sequence[str],
) -> "pd.DataFrame":
    """
    Extract per-tract posterior summary and back-transform to original scale.

    Parameters
    ----------
    idata   : ArviZ InferenceData with posterior group
    y_mean  : mean of original y before standardisation
    y_sd    : standard deviation of original y before standardisation
    geoids  : ordered list of GEOIDs matching model coords

    Returns
    -------
    DataFrame: geoid, mu_mean, mu_sd, mu_q025, mu_q975, mu_orig_mean
    """
    import pandas as pd  # local import to avoid hard dep at module load

    post = idata.posterior
    mu_samples = post["mu"].values          # (chain, draw, n)
    mu_flat    = mu_samples.reshape(-1, mu_samples.shape[-1])

    df = pd.DataFrame(
        {
            "geoid":  list(geoids),
            "mu_mean": mu_flat.mean(axis=0),
            "mu_sd":   mu_flat.std(axis=0),
            "mu_q025": np.quantile(mu_flat, 0.025, axis=0),
            "mu_q975": np.quantile(mu_flat, 0.975, axis=0),
        }
    )
    df["mu_orig_mean"] = df["mu_mean"] * float(y_sd) + float(y_mean)
    return df
