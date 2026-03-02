from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import numpy as np
import pandas as pd


def _get_logger(logger: Optional[logging.Logger] = None) -> logging.Logger:
    """
    Return a logger instance for this module.

    Args:
        logger (Optional[logging.Logger]): Existing logger to use.

    Returns:
        logging.Logger: Logger instance.
    """
    return logger if logger is not None else logging.getLogger(__name__)


def _normalize_term(term: Any, case_sensitive: bool = False) -> Optional[str]:
    """
    Normalize a gene/pathway term into a comparable string key.

    Args:
        term (Any): Term value (e.g., pathway name, gene symbol).
        case_sensitive (bool): If False, convert to lower-case.

    Returns:
        Optional[str]: Normalized term, or None if term is missing/invalid.
    """
    if term is None or pd.isna(term):
        return None
    s = str(term).strip()
    if s == "":
        return None
    return s if case_sensitive else s.lower()


def _parse_weight(weight: Any, default_weight: float) -> float:
    """
    Parse a weight value into a non-negative float.

    Args:
        weight (Any): Weight value to parse.
        default_weight (float): Default used when weight is missing.

    Returns:
        float: Parsed non-negative weight.

    Raises:
        ValueError: If the weight cannot be parsed to float.
        ValueError: If the parsed weight is negative.
    """
    if weight is None or pd.isna(weight):
        w = float(default_weight)
    else:
        try:
            w = float(weight)
        except Exception as e:
            raise ValueError(f"Weight is not numeric: {weight}") from e

    if w < 0:
        raise ValueError(f"Weight must be non-negative. Got {w}.")
    return w


def to_weight_map(
    items: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    case_sensitive: bool = False,
    default_weight: float = 1.0,
    agg: str = "sum",
) -> Dict[str, float]:
    """
    Convert weighted/unweighted term collections into a normalized weight map.

    Args:
        items (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Input items (mapping, list of terms, or list of pairs).
        case_sensitive (bool): If False, normalize terms to lower-case.
        default_weight (float): Weight assigned for unweighted terms or missing weights.
        agg (str): Aggregation for duplicate terms ("sum" or "max").

    Returns:
        Dict[str, float]: Dict mapping normalized term -> weight.

    Raises:
        ValueError: If agg is not supported.
        ValueError: If weights are invalid (non-numeric or negative).
    """
    if items is None:
        return {}

    if agg not in {"sum", "max"}:
        raise ValueError("agg must be one of {'sum', 'max'}")

    out: Dict[str, float] = {}

    def _update(k: str, w: float) -> None:
        if k not in out:
            out[k] = w
        elif agg == "sum":
            out[k] += w
        else:
            out[k] = max(out[k], w)

    if isinstance(items, Mapping):
        for term, weight in items.items():
            k = _normalize_term(term, case_sensitive=case_sensitive)
            if k is None:
                continue
            w = _parse_weight(weight, default_weight=default_weight)
            _update(k, w)
        return out

    for x in items:
        if x is None or pd.isna(x):
            continue
        if isinstance(x, (tuple, list)) and len(x) == 2:
            term, weight = x[0], x[1]
            k = _normalize_term(term, case_sensitive=case_sensitive)
            if k is None:
                continue
            w = _parse_weight(weight, default_weight=default_weight)
            _update(k, w)
        else:
            k = _normalize_term(x, case_sensitive=case_sensitive)
            if k is None:
                continue
            w = _parse_weight(None, default_weight=default_weight)
            _update(k, w)

    return out


def weighted_jaccard_components(
    a: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    b: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    case_sensitive: bool = False,
    default_weight: float = 1.0,
    agg: str = "sum",
) -> Tuple[float, float, float]:
    """
    Compute weighted Jaccard similarity and its numerator/denominator.

    Args:
        a (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Original terms/weights.
        b (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Synthetic terms/weights.
        case_sensitive (bool): If False, normalize terms to lower-case.
        default_weight (float): Weight assigned for unweighted terms or missing weights.
        agg (str): Aggregation for duplicate terms ("sum" or "max").

    Returns:
        Tuple[float, float, float]: (weighted_jaccard, min_sum, max_sum).

    Raises:
        ValueError: If weights are invalid (non-numeric or negative).
    """
    wa = to_weight_map(a, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)
    wb = to_weight_map(b, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)

    keys = set(wa) | set(wb)
    if not keys:
        return 1.0, 0.0, 0.0

    min_sum = float(sum(min(wa.get(k, 0.0), wb.get(k, 0.0)) for k in keys))
    max_sum = float(sum(max(wa.get(k, 0.0), wb.get(k, 0.0)) for k in keys))

    if max_sum == 0.0:
        return 1.0, min_sum, max_sum

    return float(min_sum / max_sum), min_sum, max_sum


def combined_sfs_score(
    wji: float,
    p_perm: float,
    n_permutations: Optional[int] = None,
    p_floor: float = 1e-300,
) -> float:
    """
    Compute SFS = WJI * (-log10(p_perm)) with stable edge-case handling.

    Args:
        wji (float): Weighted Jaccard index in [0, 1].
        p_perm (float): Permutation p-value in (0, 1].
        n_permutations (Optional[int]): If provided, clamp p_perm to at least 1/(n_permutations+1).
        p_floor (float): Minimum p-value to avoid -log10(0).

    Returns:
        float: Combined SFS score.

    Raises:
        ValueError: If inputs are not finite.
    """
    if not np.isfinite(wji):
        raise ValueError(f"wji must be finite. Got {wji}")
    if not np.isfinite(p_perm):
        raise ValueError(f"p_perm must be finite. Got {p_perm}")

    p = float(p_perm)

    if n_permutations is not None and n_permutations >= 1:
        p = max(p, 1.0 / (float(n_permutations) + 1.0))

    p = max(p, float(p_floor))
    return float(wji) * (-math.log10(p))


def permutation_test_weighted_jaccard(
    original: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    synthetic: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    n_permutations: int = 1000,
    seed: Optional[int] = 0,
    case_sensitive: bool = False,
    default_weight: float = 1.0,
    agg: str = "sum",
    alternative: str = "greater",
    verbose: int = 0,
    logger: Optional[logging.Logger] = None,
    log_every: int = 250,
) -> Dict[str, Any]:
    """
    Permutation test for weighted Jaccard similarity.

    Args:
        original (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Original terms/weights.
        synthetic (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Synthetic terms/weights.
        n_permutations (int): Number of permutations.
        seed (Optional[int]): Random seed for reproducibility.
        case_sensitive (bool): If False, normalize terms to lower-case.
        default_weight (float): Weight assigned for unweighted terms or missing weights.
        agg (str): Aggregation for duplicate terms ("sum" or "max").
        alternative (str): "greater", "less", or "two-sided".
        verbose (int): Verbosity level (0=silent, 1=summary, 2=progress).
        logger (Optional[logging.Logger]): Logger instance to use.
        log_every (int): Log progress every N permutations when verbose >= 2.

    Returns:
        Dict[str, Any]: Dict containing observed WJI, p_perm, and null summary stats.

    Raises:
        ValueError: If n_permutations < 1.
        ValueError: If alternative is invalid.
    """
    if n_permutations < 1:
        raise ValueError("n_permutations must be >= 1")

    if alternative not in {"greater", "less", "two-sided"}:
        raise ValueError("alternative must be one of {'greater', 'less', 'two-sided'}")

    log = _get_logger(logger)

    wa = to_weight_map(original, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)
    wb = to_weight_map(synthetic, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)

    obs, _, _ = weighted_jaccard_components(wa, wb, case_sensitive=True, default_weight=default_weight, agg=agg)

    b_keys = list(wb.keys())
    b_weights = np.array([wb[k] for k in b_keys], dtype=float)

    rng = np.random.default_rng(seed)
    null_vals = np.empty(n_permutations, dtype=float)

    if verbose >= 1:
        log.info(
            "Permutation test WJI: |A|=%d |B|=%d n_perm=%d seed=%s alternative=%s obs=%.6f",
            len(wa),
            len(wb),
            n_permutations,
            str(seed),
            alternative,
            obs,
        )

    for i in range(n_permutations):
        if verbose >= 2 and (i + 1) % int(log_every) == 0:
            log.info("Permutation progress: %d/%d", i + 1, n_permutations)

        perm_w = rng.permutation(b_weights)
        wb_perm = {k: float(w) for k, w in zip(b_keys, perm_w)}
        null_vals[i], _, _ = weighted_jaccard_components(
            wa, wb_perm, case_sensitive=True, default_weight=default_weight, agg=agg
        )

    if alternative == "greater":
        p_perm = (float(np.sum(null_vals >= obs)) + 1.0) / (n_permutations + 1.0)
    elif alternative == "less":
        p_perm = (float(np.sum(null_vals <= obs)) + 1.0) / (n_permutations + 1.0)
    else:
        center = float(np.mean(null_vals))
        dist_obs = abs(obs - center)
        dist_null = np.abs(null_vals - center)
        p_perm = (float(np.sum(dist_null >= dist_obs)) + 1.0) / (n_permutations + 1.0)

    if verbose >= 1:
        log.info("Permutation test done: p_perm=%.6g null_mean=%.6f null_std=%.6f", p_perm, np.mean(null_vals), np.std(null_vals))

    return {
        "observed": float(obs),
        "p_perm": float(p_perm),
        "null_mean": float(np.mean(null_vals)),
        "null_std": float(np.std(null_vals, ddof=1)) if n_permutations > 1 else float("nan"),
    }


def compute_weighted_jaccard_indices(
    original_pathways: Optional[Union[Mapping[Any, Any], Iterable[Any]]],
    synth_pathways_dict: Dict[str, Optional[Union[Mapping[Any, Any], Iterable[Any]]]],
    case_sensitive: bool = False,
    default_weight: float = 1.0,
    agg: str = "sum",
    n_permutations: int = 0,
    seed: Optional[int] = 0,
    alternative: str = "greater",
    verbose: int = 0,
    logger: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Compute WJI, permutation p-values, and SFS scores per dataset.

    Args:
        original_pathways (Optional[Union[Mapping[Any, Any], Iterable[Any]]]): Original terms/weights.
        synth_pathways_dict (Dict[str, Optional[Union[Mapping[Any, Any], Iterable[Any]]]]): Dataset -> terms/weights.
        case_sensitive (bool): If False, normalize terms to lower-case.
        default_weight (float): Weight assigned for unweighted terms or missing weights.
        agg (str): Aggregation for duplicate terms ("sum" or "max").
        n_permutations (int): If > 0, run permutation test and compute p_perm and SFS.
        seed (Optional[int]): Random seed.
        alternative (str): "greater", "less", or "two-sided".
        verbose (int): Verbosity level (0=silent, 1=summary, 2=more logs).
        logger (Optional[logging.Logger]): Logger instance to use.

    Returns:
        pd.DataFrame: Summary table with WJI, p_perm, and SFS.

    Raises:
        ValueError: If synth_pathways_dict is not a dict.
    """
    log = _get_logger(logger)

    if not isinstance(synth_pathways_dict, dict):
        raise ValueError("synth_pathways_dict must be a dict mapping dataset name -> pathways/weights")

    wa = to_weight_map(original_pathways, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)

    rows: List[Dict[str, Any]] = []
    for ds_name, synth_items in synth_pathways_dict.items():
        wb = to_weight_map(synth_items, case_sensitive=case_sensitive, default_weight=default_weight, agg=agg)

        wji, min_sum, max_sum = weighted_jaccard_components(
            wa, wb, case_sensitive=True, default_weight=default_weight, agg=agg
        )

        if verbose >= 1:
            log.info(
                "Dataset=%s |A|=%d |B|=%d WJI=%.6f min_sum=%.3f max_sum=%.3f",
                ds_name,
                len(wa),
                len(wb),
                wji,
                min_sum,
                max_sum,
            )

        row: Dict[str, Any] = {
            "Dataset": ds_name,
            "Original_terms": len(wa),
            "Synthetic_terms": len(wb),
            "MinSum": float(min_sum),
            "MaxSum": float(max_sum),
            "WJI": float(wji),
            "p_perm": float("nan"),
            "SFS": float("nan"),
        }

        if n_permutations and n_permutations > 0:
            perm = permutation_test_weighted_jaccard(
                wa,
                wb,
                n_permutations=n_permutations,
                seed=seed,
                case_sensitive=True,
                default_weight=default_weight,
                agg=agg,
                alternative=alternative,
                verbose=verbose,
                logger=logger,
            )
            p_perm = float(perm["p_perm"])
            row["p_perm"] = p_perm
            row["SFS"] = combined_sfs_score(wji=wji, p_perm=p_perm, n_permutations=n_permutations)

        rows.append(row)

    df = pd.DataFrame(
        rows,
        columns=["Dataset", "Original_terms", "Synthetic_terms", "MinSum", "MaxSum", "WJI", "p_perm", "SFS"],
    )

    if verbose >= 1:
        log.info("Done. Computed metrics for %d datasets.", df.shape[0])

    return df