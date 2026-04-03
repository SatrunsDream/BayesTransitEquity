from __future__ import annotations

import warnings

import numpy as np
import pymc as pm
import pytensor.tensor as pt


def build_tract_bym_normal(
    *,
    W: np.ndarray,
    scaling_factor: float,
    X: np.ndarray,
    y_log: np.ndarray,
    geoids: list[str],
    cov_names: list[str],
) -> pm.Model:
    """Gaussian likelihood on ``y_log`` with BYM2 random effects (PyMC NYC BYM style).

    Linear predictor: ``mu = alpha + X @ beta + sigma * (sqrt(1-rho)*theta + sqrt(rho/s)*phi)``.

    ``phi`` is ICAR on ``W``; ``theta_i ~ N(0,1)``; ``sigma`` scales the combined effect.

    Non-finite values in ``X`` are set to **0** (z-score mean) before ``pm.Data``; in ``y_log`` to **0**
    (= ``log1p(0)``). PyMC ``Data`` cannot store NaN.
    """
    n, k = X.shape
    if len(geoids) != n or y_log.shape[0] != n:
        raise ValueError("Shape mismatch between X, y_log, and geoids")
    if W.shape != (n, n):
        raise ValueError("W must be N x N")
    if k != len(cov_names):
        raise ValueError("cov_names length must match X.shape[1]")

    # pm.Data does not allow NaN/inf; z-scored covariates → 0 imputes "at cohort mean".
    X_arr = np.asarray(X, dtype=np.float64)
    y_arr = np.asarray(y_log, dtype=np.float64)
    x_bad = ~np.isfinite(X_arr)
    y_bad = ~np.isfinite(y_arr)
    if np.any(x_bad):
        n_x = int(np.sum(x_bad))
        warnings.warn(
            f"Design matrix X has {n_x} non-finite entries; imputing 0 (z-scale mean).",
            UserWarning,
            stacklevel=2,
        )
        X_arr = np.nan_to_num(X_arr, nan=0.0, posinf=0.0, neginf=0.0)
    if np.any(y_bad):
        n_y = int(np.sum(y_bad))
        warnings.warn(
            f"Response y_log has {n_y} non-finite entries; imputing log1p(0)==0.",
            UserWarning,
            stacklevel=2,
        )
        y_arr = np.nan_to_num(y_arr, nan=0.0, posinf=0.0, neginf=0.0)

    coords = {"tract": geoids, "cov": cov_names}
    with pm.Model(coords=coords) as model:
        X_data = pm.Data("X", X_arr)
        alpha = pm.Normal("alpha", 0.0, 2.0)
        beta = pm.Normal("beta", 0.0, 1.0, shape=k, dims="cov")
        theta = pm.Normal("theta", 0.0, 1.0, dims="tract")
        phi = pm.ICAR("phi", W=W, dims="tract")
        rho = pm.Beta("rho", 0.5, 0.5)
        sigma = pm.HalfNormal("sigma", 1.0)
        mixture = pm.Deterministic(
            "mixture",
            pt.sqrt(1.0 - rho) * theta + pt.sqrt(rho / scaling_factor) * phi,
            dims="tract",
        )
        mu = pm.Deterministic(
            "mu",
            alpha + pt.dot(X_data, beta) + sigma * mixture,
            dims="tract",
        )
        sigma_obs = pm.HalfNormal("sigma_obs", 0.5)
        pm.Normal("y_obs", mu=mu, sigma=sigma_obs, observed=y_arr, dims="tract")
    return model
