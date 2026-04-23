from numba import njit, prange
import numpy as np

# ----------------------------
# Numba kernels (module-level)
# ----------------------------

@njit
def _build_masks_and_maps(n_features: int, categorical_indices: np.ndarray, numerical_indices: np.ndarray):
    """
    Build fast lookup structures for feature types.

    Returns:
        tuple: (is_cat, is_num, num_pos, cat_pos)
    """
    is_cat = np.zeros(n_features, dtype=np.uint8)
    is_num = np.zeros(n_features, dtype=np.uint8)
    num_pos = np.full(n_features, -1, dtype=np.int64)
    cat_pos = np.full(n_features, -1, dtype=np.int64)

    for k in range(categorical_indices.shape[0]):
        idx = int(categorical_indices[k])
        if idx < 0 or idx >= n_features:
            raise ValueError("categorical index out of bounds.")
        is_cat[idx] = 1
        cat_pos[idx] = k

    for k in range(numerical_indices.shape[0]):
        idx = int(numerical_indices[k])
        if idx < 0 or idx >= n_features:
            raise ValueError("numerical index out of bounds.")
        is_num[idx] = 1
        num_pos[idx] = k

    return is_cat, is_num, num_pos, cat_pos


@njit
def _float_to_int_labels_with_nan(col: np.ndarray) -> np.ndarray:
    """
    Convert a float64 column of categorical values into int64 labels with a dedicated
    missing category. NaNs are mapped to -1 (missing label). Non-NaNs are cast to int64.
    """
    n = col.shape[0]
    out = np.empty(n, dtype=np.int64)
    for i in range(n):
        v = col[i]
        if np.isnan(v):
            out[i] = -1
        else:
            out[i] = int(v)
    return out


@njit
def _discretize_column_numba(col: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """
    Discretize a numerical column into n_bins (labels in [0, n_bins-1]); returns -1 for NaNs.
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    n = col.shape[0]
    out = np.empty(n, dtype=np.int64)

    # Compute min/max ignoring NaNs
    cmin = np.inf
    cmax = -np.inf
    valid_count = 0
    for i in range(n):
        v = col[i]
        if not np.isnan(v):
            valid_count += 1
            if v < cmin:
                cmin = v
            if v > cmax:
                cmax = v

    # If no valid values or constant column
    if valid_count == 0 or cmin == cmax:
        for i in range(n):
            v = col[i]
            if np.isnan(v):
                out[i] = -1
            else:
                out[i] = 0
        return out

    # Build edges (numba-friendly linspace)
    edges = np.empty(n_bins + 1, dtype=np.float64)
    diff = cmax - cmin
    for k in range(n_bins + 1):
        edges[k] = cmin + diff * (k / n_bins)

    # Assign bins
    for i in range(n):
        v = col[i]
        if np.isnan(v):
            out[i] = -1
        else:
            if v == cmax:
                out[i] = n_bins - 1
            else:
                bi = 0
                for k in range(n_bins):
                    if v >= edges[k] and v < edges[k + 1]:
                        bi = k
                        break
                out[i] = bi
    return out


@njit
def _discretize_all_numericals(data: np.ndarray, numerical_indices: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """
    Discretize all numerical columns once.
    """
    n_samples = data.shape[0]
    n_num = numerical_indices.shape[0]
    out = np.empty((n_samples, n_num), dtype=np.int64)
    for p in range(n_num):
        j = int(numerical_indices[p])
        out[:, p] = _discretize_column_numba(data[:, j], n_bins)
    return out


@njit
def _convert_all_categoricals(data: np.ndarray, categorical_indices: np.ndarray) -> np.ndarray:
    """
    Convert all categorical columns (float64) to int64 labels with -1 for NaNs.
    """
    n_samples = data.shape[0]
    n_cat = categorical_indices.shape[0]
    out = np.empty((n_samples, n_cat), dtype=np.int64)
    for p in range(n_cat):
        j = int(categorical_indices[p])
        out[:, p] = _float_to_int_labels_with_nan(data[:, j])
    return out


@njit
def _pearson_ignore_nan(x: np.ndarray, y: np.ndarray) -> float:
    """
    Pearson correlation dropping pairs with NaN. Returns 0.0 if insufficient data or zero variance.
    """
    n = x.shape[0]
    n_valid = 0
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0

    for i in range(n):
        xi = x[i]
        yi = y[i]
        if not (np.isnan(xi) or np.isnan(yi)):
            n_valid += 1
            sx += xi
            sy += yi
            sxx += xi * xi
            syy += yi * yi
            sxy += xi * yi

    if n_valid < 2:
        return 0.0

    nx = float(n_valid)
    cov = sxy - (sx * sy) / nx
    vx = sxx - (sx * sx) / nx
    vy = syy - (sy * sy) / nx

    if vx <= 0.0 or vy <= 0.0:
        return 0.0

    corr = cov / np.sqrt(vx * vy)
    if corr > 1.0:
        corr = 1.0
    elif corr < -1.0:
        corr = -1.0
    return corr


@njit
def _rankdata_average(col: np.ndarray) -> np.ndarray:
    """
    Compute average ranks for a 1D array (Spearman ranks). Ties get the average rank. Ranks start at 1.
    """
    n = col.shape[0]
    ranks = np.empty(n, dtype=np.float64)
    order = np.argsort(col)
    i = 0
    while i < n:
        start = i
        v = col[order[i]]
        i += 1
        while i < n and col[order[i]] == v:
            i += 1
        end = i - 1
        avg_rank = 0.5 * (start + end) + 1.0
        for k in range(start, end + 1):
            ranks[order[k]] = avg_rank
    return ranks


@njit
def _spearman_ignore_nan(x: np.ndarray, y: np.ndarray) -> float:
    """
    Spearman correlation dropping pairs with NaN. Returns 0.0 if insufficient data or zero variance.
    """
    n = x.shape[0]
    # First pass: count valid
    n_valid = 0
    for i in range(n):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            n_valid += 1

    if n_valid < 2:
        return 0.0

    # Collect valid pairs
    xv = np.empty(n_valid, dtype=np.float64)
    yv = np.empty(n_valid, dtype=np.float64)
    t = 0
    for i in range(n):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            xv[t] = x[i]
            yv[t] = y[i]
            t += 1

    # Rank and correlate
    rx = _rankdata_average(xv)
    ry = _rankdata_average(yv)

    return _pearson_ignore_nan(rx, ry)


@njit
def _compute_dense_labels_for_column(labels: np.ndarray):
    """
    Convert a 1D int64 label column (with -1 for missing) to dense labels 0..k-1.
    Returns (dense_labels int32, n_unique int64).
    """
    n = labels.shape[0]
    # copy and sort
    tmp = np.empty(n, dtype=np.int64)
    for i in range(n):
        tmp[i] = labels[i]
    tmp.sort()
    if n == 0:
        return np.empty(0, dtype=np.int32), np.int64(0)

    uniq = np.empty(n, dtype=np.int64)
    m = 0
    last = tmp[0]
    uniq[m] = last
    m += 1
    for i in range(1, n):
        if tmp[i] != last:
            last = tmp[i]
            uniq[m] = last
            m += 1

    dense = np.empty(n, dtype=np.int32)
    for i in range(n):
        v = labels[i]
        # binary search in uniq[0:m]
        lo = 0
        hi = m
        while lo < hi:
            mid = (lo + hi) // 2
            if uniq[mid] < v:
                lo = mid + 1
            else:
                hi = mid
        dense[i] = lo
    return dense, np.int64(m)


@njit
def _precompute_dense_mappings(cat_lab: np.ndarray, disc_num: np.ndarray):
    """
    From int64 labels with -1, produce dense int32 labels per column and sizes.
    """
    n_samples, n_cat = cat_lab.shape
    _, n_num = disc_num.shape

    dense_cat_lab = np.empty((n_samples, n_cat), dtype=np.int32)
    cat_sizes = np.empty(n_cat, dtype=np.int32)
    for p in range(n_cat):
        col = cat_lab[:, p]
        dense_col, m = _compute_dense_labels_for_column(col)
        for i in range(n_samples):
            dense_cat_lab[i, p] = dense_col[i]
        cat_sizes[p] = np.int32(m)

    dense_disc_num = np.empty((n_samples, n_num), dtype=np.int32)
    num_sizes = np.empty(n_num, dtype=np.int32)
    for p in range(n_num):
        col = disc_num[:, p]
        dense_col, m = _compute_dense_labels_for_column(col)
        for i in range(n_samples):
            dense_disc_num[i, p] = dense_col[i]
        num_sizes[p] = np.int32(m)

    return dense_cat_lab, cat_sizes, dense_disc_num, num_sizes


@njit
def cramers_v_bincount_numba(x: np.ndarray, y: np.ndarray, nx: int, ny: int) -> float:
    """
    Fast Cramér's V using bincount on combined indices. x in [0..nx-1], y in [0..ny-1].
    """
    n = x.shape[0]
    if nx <= 1 or ny <= 1:
        return 0.0

    # combined index: idx = x + nx * y
    combined = np.empty(n, dtype=np.int64)
    for i in range(n):
        combined[i] = int(x[i]) + int(nx) * int(y[i])

    counts = np.bincount(combined, minlength=int(nx) * int(ny)).astype(np.float64)

    # row and column sums
    row_sums = np.zeros(nx, dtype=np.float64)
    col_sums = np.zeros(ny, dtype=np.float64)
    total = 0.0
    # counts are laid out with x varying fastest
    idx = 0
    for j in range(ny):
        col_sum = 0.0
        for i in range(nx):
            c = counts[idx]
            row_sums[i] += c
            col_sum += c
            total += c
            idx += 1
        col_sums[j] = col_sum

    if total <= 0.0:
        return 0.0

    # chi^2
    chi2 = 0.0
    idx = 0
    for j in range(ny):
        for i in range(nx):
            e = (row_sums[i] * col_sums[j]) / total
            if e > 0.0:
                diff = counts[idx] - e
                chi2 += (diff * diff) / e
            idx += 1

    phi2 = chi2 / total
    denom = nx - 1
    if ny - 1 < denom:
        denom = ny - 1
    if denom <= 0:
        return 0.0

    v = np.sqrt(phi2 / denom)
    if v > 1.0:
        v = 1.0
    elif v < 0.0:
        v = 0.0
    return v


# ----------------------------
# BLAS-accelerated numeric blocks (Python/NumPy)
# ----------------------------

def _rankdata_average_numpy(x: np.ndarray) -> np.ndarray:
    """
    Average ranks (1-based) with ties assigned average rank, no NaNs allowed.
    """
    n = x.shape[0]
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        start = i
        v = x[order[i]]
        i += 1
        while i < n and x[order[i]] == v:
            i += 1
        end = i - 1
        avg_rank = 0.5 * (start + end) + 1.0
        ranks[order[start:end+1]] = avg_rank
    return ranks


def _prepare_numeric_matrices(X: np.ndarray, num_idx: np.ndarray, method: str):
    """
    Build Z (values/ranks, NaNs->0), Z2, and M (mask 0/1) for numeric features.
    """
    N = X.shape[0]
    Fn = num_idx.shape[0]
    Z = np.zeros((N, Fn), dtype=np.float64)
    M = np.zeros((N, Fn), dtype=np.float64)
    if method == "spearman":
        for p, j in enumerate(num_idx):
            col = X[:, j]
            mask = ~np.isnan(col)
            M[mask, p] = 1.0
            if mask.any():
                ranks = _rankdata_average_numpy(col[mask].astype(np.float64, copy=False))
                Z[mask, p] = ranks
    else:
        for p, j in enumerate(num_idx):
            col = X[:, j]
            mask = ~np.isnan(col)
            M[mask, p] = 1.0
            Z[mask, p] = col[mask]
    Z2 = Z * Z
    return Z, Z2, M


def _pearson_block_from_summaries(Za, Z2a, Ma, Zb, Z2b, Mb):
    """
    Compute correlation block for two numeric blocks (A,B) using pairwise-deletion formulas.
    Returns corr_block (Fa x Fb).
    """
    # Summaries via GEMM
    Sxy = Za.T @ Zb            # Fa x Fb
    Nvv = Ma.T @ Mb            # Fa x Fb
    Sx = Za.T @ Mb             # Fa x Fb
    Sy = (Zb.T @ Ma).T         # Fa x Fb
    Sxx = (Z2a.T @ Mb)         # Fa x Fb
    Syy = (Z2b.T @ Ma).T       # Fa x Fb

    with np.errstate(invalid="ignore", divide="ignore"):
        cov = Sxy - (Sx * Sy) / Nvv
        varx = Sxx - (Sx * Sx) / Nvv
        vary = Syy - (Sy * Sy) / Nvv
        denom = np.sqrt(varx * vary)
        corr = cov / denom

    invalid = (Nvv < 2) | (varx <= 0.0) | (vary <= 0.0) | ~np.isfinite(corr)
    if np.any(invalid):
        corr = corr.copy()
        corr[invalid] = 0.0

    np.clip(corr, -1.0, 1.0, out=corr)
    return corr


def _compute_numeric_numeric_blas(
    X: np.ndarray,
    numerical_indices: np.ndarray,
    method: str,
    block_cols: int = 512
):
    """
    Compute the numeric-numeric correlation submatrix using BLAS-backed block GEMMs.
    """
    Fn = numerical_indices.shape[0]
    if Fn == 0:
        return None

    Z, Z2, M = _prepare_numeric_matrices(X, numerical_indices, method)
    corr_nn = np.empty((Fn, Fn), dtype=np.float64)

    # Block over columns
    for a in range(0, Fn, block_cols):
        a_end = min(Fn, a + block_cols)
        Za = Z[:, a:a_end]
        Z2a = Z2[:, a:a_end]
        Ma = M[:, a:a_end]
        # Diagonal block
        corr_block = _pearson_block_from_summaries(Za, Z2a, Ma, Za, Z2a, Ma)
        corr_nn[a:a_end, a:a_end] = corr_block
        # Upper blocks
        for b in range(a_end, Fn, block_cols):
            b_end = min(Fn, b + block_cols)
            Zb = Z[:, b:b_end]
            Z2b = Z2[:, b:b_end]
            Mb = M[:, b:b_end]
            corr_block = _pearson_block_from_summaries(Za, Z2a, Ma, Zb, Z2b, Mb)
            corr_nn[a:a_end, b:b_end] = corr_block
            corr_nn[b:b_end, a:a_end] = corr_block.T

    # Diagonal to 1.0 when variance > 0
    diag_idx = np.diag_indices(Fn)
    corr_nn[diag_idx] = 1.0

    return corr_nn


@njit(parallel=True)
def _fill_categorical_pairs_only(
    corr_matrix: np.ndarray,
    is_cat: np.ndarray,
    is_num: np.ndarray,
    cat_pos: np.ndarray,
    num_pos: np.ndarray,
    dense_cat_lab: np.ndarray,
    cat_sizes: np.ndarray,
    dense_disc_num: np.ndarray,
    num_sizes: np.ndarray,
):
    """
    Fill only pairs where at least one variable is categorical using precomputed dense labels.
    Numerical-numerical entries already prefilled are left untouched.
    """
    n_features = is_cat.shape[0]
    for i in prange(n_features):
        for j in range(i + 1, n_features):
            # cat-cat
            if is_cat[i] == 1 and is_cat[j] == 1:
                pi = cat_pos[i]
                pj = cat_pos[j]
                if pi >= 0 and pj >= 0:
                    corr = cramers_v_bincount_numba(
                        dense_cat_lab[:, pi], dense_cat_lab[:, pj],
                        int(cat_sizes[pi]), int(cat_sizes[pj])
                    )
                else:
                    corr = np.nan
            # cat-num
            elif is_cat[i] == 1 and is_num[j] == 1:
                pi = cat_pos[i]
                pj = num_pos[j]
                if pi >= 0 and pj >= 0:
                    corr = cramers_v_bincount_numba(
                        dense_cat_lab[:, pi], dense_disc_num[:, pj],
                        int(cat_sizes[pi]), int(num_sizes[pj])
                    )
                else:
                    corr = np.nan
            elif is_num[i] == 1 and is_cat[j] == 1:
                pi = num_pos[i]
                pj = cat_pos[j]
                if pi >= 0 and pj >= 0:
                    corr = cramers_v_bincount_numba(
                        dense_disc_num[:, pi], dense_cat_lab[:, pj],
                        int(num_sizes[pi]), int(cat_sizes[pj])
                    )
                else:
                    corr = np.nan
            else:
                continue  # numeric-numeric, prefilled elsewhere

            if corr > 1.0:
                corr = 1.0
            elif corr < -1.0:
                corr = -1.0
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr


@njit(parallel=True)
def _memory_efficient_squareform(distance_matrix: np.ndarray) -> np.ndarray:
    """
    Convert a square distance matrix to its condensed form using memory-efficient storage.
    """
    n = distance_matrix.shape[0]
    condensed_size = n * (n - 1) // 2
    condensed = np.zeros(condensed_size, dtype=np.float64)
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            condensed[idx] = distance_matrix[i, j]
            idx += 1
    return condensed


# ----------------------------
# Python class orchestrator
# ----------------------------

class MixedCorrelation:
    """
    Compute mixed-type correlation matrices combining BLAS/vectorized numeric-numeric and
    Numba-accelerated categorical interactions.

    Missing handling:
      - Numerical: pairwise deletion (drop rows with NaN in either column) for Pearson/Spearman.
      - Categorical (including discretized numeric for Cramér's V): missing is its own category.

    Parameters
    ----------
    categorical_indices : array-like of int
        Column indices treated as categorical.
    numerical_indices : array-like of int
        Column indices treated as numerical.
    method : {'pearson','spearman'}, default 'pearson'
        Correlation for numeric-numeric pairs.
    n_bins : int, default 10
        Number of bins for discretizing numerical columns when paired with categorical.
    engine : {'auto','numba','blas'}, default 'auto'
        - 'blas': use block GEMM path for numeric-numeric (fast for many features).
        - 'numba': compute everything in Numba loops.
        - 'auto': choose 'blas' when many numeric features, else 'numba'.
    block_cols : int, default 512
        Block width for BLAS engine.
    """

    def __init__(
        self,
        categorical_indices,
        numerical_indices,
        method: str = "pearson",
        n_bins: int = 10,
        engine: str = "auto",
        block_cols: int = 512
    ):
        self.categorical_indices = np.array(categorical_indices, dtype=np.int64)
        self.numerical_indices = np.array(numerical_indices, dtype=np.int64)
        if self.categorical_indices.size > 0:
            self.categorical_indices = np.sort(self.categorical_indices)
        if self.numerical_indices.size > 0:
            self.numerical_indices = np.sort(self.numerical_indices)

        self.method = method.lower()
        self.n_bins = int(n_bins)
        self.engine = engine.lower()
        self.block_cols = int(block_cols)

        if self.method not in ("pearson", "spearman"):
            raise ValueError("method must be one of {'pearson', 'spearman'}")
        if self.engine not in ("auto", "numba", "blas"):
            raise ValueError("engine must be one of {'auto','numba','blas'}")

    def _validate_indices(self, n_features: int):
        if np.any(self.categorical_indices < 0) or np.any(self.categorical_indices >= n_features):
            raise ValueError("categorical index out of bounds.")
        if np.any(self.numerical_indices < 0) or np.any(self.numerical_indices >= n_features):
            raise ValueError("numerical index out of bounds.")
        if self.categorical_indices.size and self.numerical_indices.size:
            if np.intersect1d(self.categorical_indices, self.numerical_indices).size > 0:
                raise ValueError("Overlap between categorical and numerical indices.")

    def compute(self, data):
        """
        Compute the mixed-type correlation matrix on the provided data.

        Returns
        -------
        corr : np.ndarray of shape (n_features, n_features)
        """
        # Convert to contiguous NumPy array
        if hasattr(data, "values"):
            X = np.ascontiguousarray(data.values, dtype=np.float64)
        else:
            X = np.ascontiguousarray(data, dtype=np.float64)
        if X.ndim != 2:
            raise ValueError("data must be 2D")

        n_samples, n_features = X.shape
        self._validate_indices(n_features)

        # Choose engine
        engine = self.engine
        if engine == "auto":
            Fn = int(self.numerical_indices.size)
            # Aggressive switch to BLAS for many numerical features
            engine = "blas" if Fn >= 256 else "numba"

        if engine == "numba":
            # Full Numba path (still benefits from bincount-based Cramér's V)
            # Build masks and precompute dense labels once
            is_cat, is_num, num_pos, cat_pos = _build_masks_and_maps(n_features, self.categorical_indices, self.numerical_indices)
            disc_num = _discretize_all_numericals(X, self.numerical_indices, self.n_bins)
            cat_lab = _convert_all_categoricals(X, self.categorical_indices)
            dense_cat_lab, cat_sizes, dense_disc_num, num_sizes = _precompute_dense_mappings(cat_lab, disc_num)

            corr = np.zeros((n_features, n_features), dtype=np.float64)

            # numeric-numeric via pairwise numba loops
            for i in range(n_features):
                corr[i, i] = 1.0

            # numeric-numeric
            for a in range(self.numerical_indices.shape[0]):
                ia = int(self.numerical_indices[a])
                for b in range(a, self.numerical_indices.shape[0]):
                    ib = int(self.numerical_indices[b])
                    if ia == ib:
                        c = 1.0
                    else:
                        if self.method == "pearson":
                            c = _pearson_ignore_nan(X[:, ia], X[:, ib])
                        else:
                            c = _spearman_ignore_nan(X[:, ia], X[:, ib])
                    if c > 1.0:
                        c = 1.0
                    elif c < -1.0:
                        c = -1.0
                    corr[ia, ib] = c
                    corr[ib, ia] = c

            # categorical-involving pairs
            _fill_categorical_pairs_only(
                corr_matrix=corr,
                is_cat=is_cat,
                is_num=is_num,
                cat_pos=cat_pos,
                num_pos=num_pos,
                dense_cat_lab=dense_cat_lab,
                cat_sizes=cat_sizes,
                dense_disc_num=dense_disc_num,
                num_sizes=num_sizes,
            )
            return corr

        # BLAS engine: numeric-numeric via GEMM; categorical via Numba
        corr = np.zeros((n_features, n_features), dtype=np.float64)

        # 1) numeric-numeric submatrix
        corr_nn = _compute_numeric_numeric_blas(X, self.numerical_indices, self.method, self.block_cols)
        if corr_nn is not None:
            idx = self.numerical_indices
            corr[np.ix_(idx, idx)] = corr_nn

        # 2) categorical interactions
        if self.categorical_indices.size > 0:
            disc_num = _discretize_all_numericals(X, self.numerical_indices, self.n_bins)
            cat_lab = _convert_all_categoricals(X, self.categorical_indices)
            dense_cat_lab, cat_sizes, dense_disc_num, num_sizes = _precompute_dense_mappings(cat_lab, disc_num)
            is_cat, is_num, num_pos, cat_pos = _build_masks_and_maps(n_features, self.categorical_indices, self.numerical_indices)
            _fill_categorical_pairs_only(
                corr_matrix=corr,
                is_cat=is_cat,
                is_num=is_num,
                cat_pos=cat_pos,
                num_pos=num_pos,
                dense_cat_lab=dense_cat_lab,
                cat_sizes=cat_sizes,
                dense_disc_num=dense_disc_num,
                num_sizes=num_sizes,
            )

        # 3) Diagonal
        diag = np.arange(n_features)
        corr[diag, diag] = 1.0

        np.clip(corr, -1.0, 1.0, out=corr)
        return corr

    @staticmethod
    def get_squareform(distance_matrix: np.array):
        return _memory_efficient_squareform(distance_matrix)

    def set_method(self, method: str):
        m = method.lower()
        if m not in ("pearson", "spearman"):
            raise ValueError("method must be one of {'pearson', 'spearman'}")
        self.method = m


@njit(parallel=True)
def spearman_correlation_matrix_numba(X):
    """
    Spearman correlation matrix (dropping NaN pairs), Numba-parallel.
    """
    n_samples, n_features = X.shape
    corr_matrix = np.empty((n_features, n_features), dtype=np.float32)

    for i in prange(n_features):
        for j in range(i, n_features):
            if i == j:
                corr = 1.0
            else:
                corr = _spearman_ignore_nan(X[:, i], X[:, j])
            if corr > 1.0:
                corr = 1.0
            elif corr < -1.0:
                corr = -1.0
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr  # symmetric

    return corr_matrix


@njit(parallel=True)
def pearson_correlation_matrix_numba(X):
    """
    Pearson correlation matrix (dropping NaN pairs), Numba-parallel.
    """
    n_samples, n_features = X.shape
    corr_matrix = np.empty((n_features, n_features), dtype=np.float32)

    for i in prange(n_features):
        for j in range(i, n_features):
            if i == j:
                corr = 1.0
            else:
                corr = _pearson_ignore_nan(X[:, i], X[:, j])
            if corr > 1.0:
                corr = 1.0
            elif corr < -1.0:
                corr = -1.0

            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr  # symmetric

    return corr_matrix