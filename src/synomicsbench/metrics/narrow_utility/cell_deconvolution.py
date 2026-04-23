"""
Aitchison distance for compositional cell-type deconvolution data.

Provides functions to compute the Aitchison distance between immune cell
composition profiles estimated by CIBERSORTx (or similar tools) on
original and synthetic datasets.

The Aitchison distance is computed in Centered Log-Ratio (CLR) space
after multiplicative replacement of zeros and geometric mean centering.
"""

from __future__ import annotations

from typing import List
from skbio.stats.composition import clr, multi_replace
from scipy.spatial.distance import euclidean
import numpy as np
import pandas as pd

def geometric_center(X: np.ndarray) -> np.ndarray:
    """Compute the compositional center (geometric mean) for each component.

    Args:
        X: 2-D array of shape (n_samples, n_parts).

    Returns:
        1-D array of length n_parts representing the geometric mean per part.
    """
    return np.exp(np.mean(np.log(X), axis=0))


# ---------------------------------------------------------------------------
# Aitchison distance and score
# ---------------------------------------------------------------------------

def aitchison_distance(
    df_orig: pd.DataFrame,
    df_syn: pd.DataFrame,
    cell_types: List[str],
) -> float:
    """Compute the Aitchison distance between two cell-type composition datasets.

    The distance is defined as the Euclidean distance between the CLR-
    transformed compositional centers of the original and synthetic datasets.

    Args:
        df_orig: Original CIBERSORTx results (rows = samples, columns include
            the cell-type columns).
        df_syn: Synthetic CIBERSORTx results with the same cell-type columns.
        cell_types: List of column names for the cell types to compare.

    Returns:
        Aitchison distance (non-negative float).
    """
    data_orig = df_orig[cell_types].values.astype(float)
    data_syn = df_syn[cell_types].values.astype(float)

    # Replace zeros via multiplicative strategy
    data_orig_filled = multi_replace(data_orig)
    data_syn_filled = multi_replace(data_syn)

    # Compute compositional centers
    center_orig = geometric_center(data_orig_filled)
    center_syn = geometric_center(data_syn_filled)

    # CLR transform the centers
    clr_orig = clr(center_orig.reshape(1, -1)).flatten()
    clr_syn = clr(center_syn.reshape(1, -1)).flatten()

    # Euclidean distance in CLR space
    return euclidean(clr_orig, clr_syn)


def aitchison_score(distance: float) -> float:
    """Convert Aitchison distance to a similarity score via exp(-d).

    Higher values indicate better agreement.  A distance of 0 yields a
    score of 1.0.

    Args:
        distance: Non-negative Aitchison distance.

    Returns:
        Score in (0, 1].
    """
    return float(np.exp(-distance))
