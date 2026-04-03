from __future__ import annotations

from typing import Any

import geopandas as gpd
import numpy as np
from scipy import sparse
from scipy.linalg import solve
from scipy.sparse.linalg import spsolve


def scaling_factor_sp(A: np.ndarray) -> float:
    """BYM2 scaling factor (Riebler et al. 2016) from a symmetric 0/1 adjacency matrix.

    Same construction as the PyMC NYC BYM example. The graph should be **connected**
    (e.g. bridge island tracts before calling).
    """
    num_neighbors = A.sum(axis=1)
    A_sp = sparse.csc_matrix(A)
    D = sparse.diags(num_neighbors, format="csc")
    Q = D - A_sp

    Q_perturbed = Q + sparse.diags(np.ones(Q.shape[0])) * max(Q.diagonal()) * np.sqrt(
        np.finfo(np.float64).eps
    )

    n = Q_perturbed.shape[0]
    b = sparse.identity(n, format="csc")
    Sigma = spsolve(Q_perturbed, b)
    ones = np.ones(n)
    W_col = Sigma @ ones
    Q_inv = Sigma - np.outer(W_col * solve(ones @ W_col, np.ones(1)), W_col.T)

    return float(np.exp(np.sum(np.log(np.diag(Q_inv))) / n))


def _connect_islands_to_nearest(
    gdf: gpd.GeoDataFrame, W: np.ndarray, island_idx: list[int]
) -> np.ndarray:
    """Add symmetric edges from each island row to its nearest tract by centroid."""
    if not island_idx:
        return W
    W = W.copy()
    centroids = gdf.geometry.centroid
    cx = centroids.x.to_numpy()
    cy = centroids.y.to_numpy()
    for i in island_idx:
        d2 = (cx - cx[i]) ** 2 + (cy - cy[i]) ** 2
        d2[i] = np.inf
        j = int(np.argmin(d2))
        W[i, j] = 1
        W[j, i] = 1
    return W


def _normalize_geoid(x: object) -> str:
    s = str(x).strip()
    if s.isdigit() and len(s) <= 11:
        return s.zfill(11)
    return s


def _id_order_to_geoids_and_geoms(
    g: gpd.GeoDataFrame, id_col: str, raw_order: list[Any]
) -> tuple[list[str], list[Any]]:
    """Map libpysal ``Weights.id_order`` to GEOID strings and geometries (row-aligned to ``W``).

    libpysal often reports ``id_order`` as **integer row indices** ``0 .. n-1`` (not FIPS).
    Those must be mapped with ``g.iloc[pos]`` — **never** ``str(pos).zfill(11)``, which
    produces bogus IDs like ``00000000000``.

    If entries are real GEOIDs (e.g. after ``idVariable``), use them to look up rows.
    """
    n = len(g)
    geoids: list[str] = []
    geoms: list[Any] = []
    col = g[id_col].astype(str).str.zfill(11)

    for i, oid in enumerate(raw_order):
        pos: int | None = None
        if isinstance(oid, (int, np.integer)) and 0 <= int(oid) < n:
            pos = int(oid)
        elif isinstance(oid, str) and oid.isdigit() and len(oid) <= 6 and int(oid) < n:
            pos = int(oid)

        if pos is not None:
            geoids.append(str(col.iloc[pos]))
            geoms.append(g.geometry.iloc[pos])
            continue

        lab = _normalize_geoid(oid)
        mask = (col == lab).to_numpy()
        if mask.any():
            j = int(np.argmax(mask))
            geoids.append(str(col.iloc[j]))
            geoms.append(g.geometry.iloc[j])
        else:
            # Last resort: assume W row i matches dataframe row i (common when id_order is broken)
            if i < n:
                geoids.append(str(col.iloc[i]))
                geoms.append(g.geometry.iloc[i])
            else:
                raise KeyError(f"id_order entry {oid!r} could not be mapped to a tract row.")

    return geoids, geoms


def adjacency_from_queen(
    tracts: gpd.GeoDataFrame,
    id_col: str = "GEOID",
    connect_islands: bool = True,
) -> tuple[np.ndarray, list[str], dict[str, Any], gpd.GeoDataFrame]:
    """Queen contiguity → symmetric 0/1 adjacency ``W`` aligned to tract order.

    Returns ``W``, ``geoids`` (same row order as ``W``), diagnostics, and a two-column
    GeoDataFrame ``GEOID`` + ``geometry`` in that order.

    **Notebook usage** (``04_bayesian_model.ipynb``)::

        tracts_gdf = gpd.GeoDataFrame(df[[\"GEOID\", \"geometry\"]], ...)
        W, geoids_sp, diag_sp, tracts_ordered = adjacency_from_queen(tracts_gdf, id_col=\"GEOID\")
        scaling_factor = scaling_factor_sp(W)
    """
    try:
        from libpysal.weights import Queen
    except ImportError as e:
        raise ImportError("Install libpysal: pip install libpysal") from e

    if id_col not in tracts.columns:
        raise KeyError(f"Missing column {id_col!r} on tract GeoDataFrame")

    g = tracts[[id_col, "geometry"]].copy()
    g[id_col] = g[id_col].astype(str).str.zfill(11)
    g = g.reset_index(drop=True)

    # Prefer passing the GEOID column so id_order may contain real FIPS (libpysal-dependent).
    try:
        wq = Queen.from_dataframe(g, idVariable=id_col)
    except TypeError:
        wq = Queen.from_dataframe(g)

    full, _meta = wq.full()
    W = (full > 0).astype(np.int64)
    W = (W + W.T > 0).astype(np.int64)
    np.fill_diagonal(W, 0)

    if W.shape[0] != len(g):
        raise ValueError(f"Weight matrix size {W.shape[0]} != number of tracts {len(g)}")

    geoids, geoms = _id_order_to_geoids_and_geoms(g, id_col, list(wq.id_order))

    t_ix_geom = gpd.GeoDataFrame(
        {"GEOID": geoids, "geometry": geoms},
        geometry="geometry",
        crs=g.crs,
    )

    island_idx = [i for i in range(len(geoids)) if W[i].sum() == 0]
    if island_idx and connect_islands:
        W = _connect_islands_to_nearest(t_ix_geom, W, island_idx)

    diag = spatial_graph_diagnostics(W)
    diag["island_indices_before_fix"] = island_idx
    diag["geoid_order"] = geoids
    diag["id_order_sample"] = list(wq.id_order)[:5]
    return W, geoids, diag, t_ix_geom


def spatial_graph_diagnostics(W: np.ndarray) -> dict[str, Any]:
    """Edge count and degree summary for a symmetric unweighted adjacency."""
    n = W.shape[0]
    deg = W.sum(axis=1)
    n_edges = int(W.sum() // 2)
    return {
        "n_nodes": n,
        "n_edges": n_edges,
        "degree_min": int(deg.min()),
        "degree_max": int(deg.max()),
        "degree_mean": float(deg.mean()),
        "n_zero_degree": int((deg == 0).sum()),
    }
