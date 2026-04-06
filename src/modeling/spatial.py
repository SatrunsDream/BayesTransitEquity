"""
spatial.py — spatial weight matrix utilities for BayesTransitEquity

Provides:
  adjacency_from_queen()   — Queen-contiguity W matrix + diagnostics
  scaling_factor_sp()      — Riebler (2016) BYM2 scaling factor
  _connect_islands_to_nearest() — join isolated tracts to graph
  spatial_graph_diagnostics()   — summary stats for adjacency graph
"""

from __future__ import annotations

import warnings
from typing import Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import scipy.sparse as sp

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _id_order_to_geoids_and_geoms(
    g: gpd.GeoDataFrame,
    id_col: str,
    raw_order: list,
) -> Tuple[list, list]:
    """
    Map libpysal id_order (may be int row-positions OR string GEOIDs) to
    real GEOID strings and geometries.

    libpysal Queen.from_dataframe() returns id_order as the *values* of the
    index if the GeoDataFrame has a string index, OR as integer row-positions
    0..n-1 when the index is default RangeIndex.  We need to handle both.
    """
    n = len(g)
    col = g[id_col].astype(str).str.zfill(11)
    geoids: list = []
    geoms: list = []

    for oid in raw_order:
        pos = None
        # Integer or short numeric string → treat as row position
        if isinstance(oid, (int, np.integer)) and 0 <= int(oid) < n:
            pos = int(oid)
        elif (
            isinstance(oid, str)
            and oid.isdigit()
            and len(oid) <= 6
            and int(oid) < n
        ):
            pos = int(oid)

        if pos is not None:
            geoids.append(str(col.iloc[pos]))
            geoms.append(g.geometry.iloc[pos])
        else:
            # Assume it's already a real GEOID or index label
            geoids.append(str(oid).zfill(11))
            # Locate by id_col value
            match = g[g[id_col].astype(str).str.zfill(11) == str(oid).zfill(11)]
            if len(match) == 1:
                geoms.append(match.geometry.iloc[0])
            else:
                geoms.append(None)

    return geoids, geoms


def _connect_islands_to_nearest(
    g: gpd.GeoDataFrame,
    id_col: str,
    neighbors: dict,
) -> dict:
    """
    For any tract with no neighbours (island), add a bilateral edge to the
    nearest tract by centroid distance.  Returns updated neighbours dict.
    """
    geoids = g[id_col].astype(str).str.zfill(11).tolist()
    centroids = g.geometry.centroid
    idx_map = {gid: i for i, gid in enumerate(geoids)}

    islands = [gid for gid in geoids if len(neighbors.get(gid, [])) == 0]
    if not islands:
        return neighbors

    cx = centroids.x.values
    cy = centroids.y.values

    for gid in islands:
        i = idx_map[gid]
        dists = np.sqrt((cx - cx[i]) ** 2 + (cy - cy[i]) ** 2)
        dists[i] = np.inf  # exclude self
        j = int(np.argmin(dists))
        nbr_gid = geoids[j]
        neighbors.setdefault(gid, set()).add(nbr_gid)
        neighbors.setdefault(nbr_gid, set()).add(gid)

    return neighbors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def spatial_graph_diagnostics(W: np.ndarray, geoids: list) -> dict:
    """
    Return a dict of summary statistics for the adjacency matrix W.
    """
    n = W.shape[0]
    degrees = W.sum(axis=1)
    n_edges = int(degrees.sum()) // 2
    islands = int((degrees == 0).sum())
    return {
        "n_tracts": n,
        "n_edges": n_edges,
        "mean_degree": float(degrees.mean()),
        "min_degree": int(degrees.min()),
        "max_degree": int(degrees.max()),
        "n_islands": islands,
        "is_symmetric": bool(np.allclose(W, W.T)),
    }


def scaling_factor_sp(W: np.ndarray) -> float:
    """
    Compute the Riebler (2016) geometric mean variance scaling factor for BYM2.

    This is the geometric mean of the marginal variances of the ICAR precision
    matrix Q = D - W, where D = diag(row sums of W).

    Parameters
    ----------
    W : (n, n) adjacency matrix (symmetric, binary or row-sums)

    Returns
    -------
    float : scaling factor τ_s  (typically close to 1 for well-connected graphs)
    """
    n = W.shape[0]
    D = np.diag(W.sum(axis=1))
    Q = D - W

    # Q is singular (rank n-1); add tiny ridge for numerical stability
    Q_ridge = Q + 1e-6 * np.eye(n)

    try:
        Q_inv = np.linalg.inv(Q_ridge)
    except np.linalg.LinAlgError:
        warnings.warn("scaling_factor_sp: Q inversion failed; returning 1.0")
        return 1.0

    # Geometric mean of diagonal (marginal variances)
    diag_vals = np.diag(Q_inv)
    diag_vals = np.maximum(diag_vals, 1e-12)  # guard log(0)
    scale = float(np.exp(np.mean(np.log(diag_vals))))
    return scale


def adjacency_from_queen(
    tracts: gpd.GeoDataFrame,
    id_col: str = "GEOID",
    connect_islands: bool = True,
) -> Tuple[np.ndarray, list, dict, gpd.GeoDataFrame]:
    """
    Build a symmetric binary adjacency matrix W from Queen contiguity.

    Parameters
    ----------
    tracts         : GeoDataFrame with census tract polygons
    id_col         : column name holding the GEOID (11-digit string)
    connect_islands: if True, isolated tracts are connected to nearest centroid

    Returns
    -------
    W              : (n, n) numpy float64 adjacency matrix
    geoids         : list[str] of GEOIDs in row/column order
    diagnostics    : dict from spatial_graph_diagnostics()
    tracts_ordered : GeoDataFrame reindexed to match W row order
    """
    try:
        from libpysal.weights import Queen
    except ImportError as e:
        raise ImportError("libpysal is required: pip install libpysal") from e

    # Build Queen weights
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        q = Queen.from_dataframe(tracts, silence_warnings=True)

    # Resolve id_order → GEOIDs
    raw_order = list(q.id_order)
    geoids, _ = _id_order_to_geoids_and_geoms(tracts, id_col, raw_order)

    # Build neighbours dict keyed by GEOID
    # q.neighbors maps id_order values → list of id_order values
    id2geoid = {raw: gid for raw, gid in zip(raw_order, geoids)}
    neighbors: dict = {}
    for raw_i, raw_nbrs in q.neighbors.items():
        gid_i = id2geoid[raw_i]
        neighbors[gid_i] = set(id2geoid[r] for r in raw_nbrs)

    # Connect islands if requested
    if connect_islands:
        neighbors = _connect_islands_to_nearest(tracts, id_col, neighbors)

    # Build W matrix in geoids order
    n = len(geoids)
    g2i = {g: i for i, g in enumerate(geoids)}
    W = np.zeros((n, n), dtype=np.float64)
    for gid_i, nbr_set in neighbors.items():
        if gid_i not in g2i:
            continue
        i = g2i[gid_i]
        for gid_j in nbr_set:
            if gid_j not in g2i:
                continue
            j = g2i[gid_j]
            W[i, j] = 1.0
            W[j, i] = 1.0

    # Reorder tracts GeoDataFrame to match W
    col = tracts[id_col].astype(str).str.zfill(11)
    geoid_to_row = {g: idx for idx, g in zip(tracts.index, col)}
    ordered_idx = [geoid_to_row[g] for g in geoids if g in geoid_to_row]
    tracts_ordered = tracts.loc[ordered_idx].reset_index(drop=True)

    diag = spatial_graph_diagnostics(W, geoids)
    return W, geoids, diag, tracts_ordered
