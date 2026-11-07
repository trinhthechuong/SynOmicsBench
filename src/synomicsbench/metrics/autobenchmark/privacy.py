"""
Privacy risks of the four attack categories, from live attacks, saved pickles or a risk table.

Each attack category (univariate singling out, multivariate singling out, linkability,
attribute inference) is one meta-score dimension; its risk is the mean over the attack's
configurations (knowledge levels, ``n_cols`` values, secrets) of

* the residual risk ``(R_attack - R_control) / (1 - R_control)`` when the attack was run
  against an external control cohort, or
* the attack risk floored at the naive (random-guess) risk otherwise — the rule used for the
  published results (``Manuscript/FigurePrivacy/OveralScore_Bayesian.ipynb``).

The dimension value is the privacy score ``1 - risk`` (higher = better).

The older single "overall privacy score" (``1 - mean`` of the four category risks) is kept
in :func:`overall_privacy_from_attacks`, :func:`overall_privacy_from_pickles` and
:func:`overall_privacy_from_csv`.
"""

from __future__ import annotations

import os
import pickle
from typing import Dict, Sequence

import numpy as np
import pandas as pd


DEFAULT_TOOLS = ["Avatars K5", "Avatars K10", "CTGAN", "Gaussian Copula", "Synthpop", "TVAE"]

#: attack-table label -> meta-score dimension
ATTACK_DIMS = {
    "SO_uni": "Singling-out (uni)",
    "SO_multi": "Singling-out (multi)",
    "Linkability": "Linkability",
    "Inference": "Inference",
}


def _final_risk(obj) -> float:
    """Attack risk with naive-baseline replacement (risk floored at the naive baseline).

    Accepts either an anonymeter evaluator or an ``EvaluationResults`` object. If the object
    does not expose a ``baseline`` risk (e.g. an ``EvaluationResults`` from ``.results()``),
    the attack risk is returned as-is.
    """
    attack_risk = obj.risk().value
    try:
        naive_risk = obj.risk(baseline=True).value
    except TypeError:
        return float(attack_risk)
    return float(naive_risk if attack_risk <= naive_risk else attack_risk)


def _category_risk(obj) -> float:
    """Risk of one evaluation: residual risk with a control set, otherwise :func:`_final_risk`."""
    results = obj.results() if callable(getattr(obj, "results", None)) else obj
    if getattr(results, "control_rate", None) is not None:
        return float(results.risk().value)
    return _final_risk(obj)


def category_risks_from_attacks(uni: dict, multi: dict, link: dict, infer: dict) -> Dict[str, Dict[str, float]]:
    """Mean risk of each attack category per synthetic dataset.

    Args mirror the ``{dataset: [...]}`` returns of the ``metrics.privacy`` functions; failed
    inference evaluations (``{"error": ...}``) are skipped.

    Returns:
        dict: dimension name (see ``ATTACK_DIMS``) -> {dataset: mean risk}.
    """
    def _mean(items) -> float:
        vals = []
        for item in items:
            ev = item[1] if isinstance(item, tuple) else item
            if not isinstance(ev, dict):
                vals.append(_category_risk(ev))
        return float(np.mean(vals)) if vals else float("nan")

    out: Dict[str, Dict[str, float]] = {}
    for key, res in (("SO_uni", uni), ("SO_multi", multi), ("Linkability", link), ("Inference", infer)):
        out[ATTACK_DIMS[key]] = {tool: _mean(items) for tool, items in (res or {}).items()}
    return out


def category_risks_from_pickles(pickle_root: str, seed: int,
                                tools: Sequence[str] = tuple(DEFAULT_TOOLS)) -> Dict[str, Dict[str, float]]:
    """Mean risk of each attack category per method for one seed, from saved pickles.

    Same layout as :func:`overall_privacy_from_pickles`.

    Returns:
        dict: dimension name -> {method: mean risk}.
    """
    tools = list(tools)
    uni = _load_pickle(os.path.join(pickle_root, "SinglingOut", "UniSO", f"Seed_{seed}", "SOUni_Results.pkl"))
    multi = _load_pickle(os.path.join(pickle_root, "SinglingOut", "MultiSO", f"Seed_{seed}", "MultiSO_Results.pkl"))
    link = _load_pickle(os.path.join(pickle_root, "Linkability", f"Seed_{seed}", "LinkabilityResults.pkl"))
    infer = _load_pickle(os.path.join(pickle_root, "Inference", f"Seed_{seed}", "results_inferences.pkl"))
    risks = category_risks_from_attacks(
        *[{tool: items for tool, items in zip(tools, res.values())} for res in (uni, multi, link, infer)]
    )
    return risks


def category_risks_from_table(path_or_df) -> pd.DataFrame:
    """Mean risk per (method, seed, attack category) from a long risk table.

    Accepts a CSV/parquet path or a DataFrame with one row per evaluation and the columns
    ``method``/``Model``, ``seed``/``Seed``, ``attack``/``Attack`` (``SO_uni``, ``SO_multi``,
    ``Linkability``, ``Inference`` or the dimension names) and ``risk_residual``/``Risk``.

    Returns:
        pd.DataFrame: columns Model, Seed, Dimension, Risk.
    """
    if isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    elif str(path_or_df).endswith(".parquet"):
        df = pd.read_parquet(path_or_df)
    else:
        df = pd.read_csv(path_or_df)
    aliases = {"method": "Model", "seed": "Seed", "attack": "Attack", "risk_residual": "Risk"}
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})
    missing = [c for c in ("Model", "Seed", "Attack", "Risk") if c not in df.columns]
    if missing:
        raise KeyError(f"Risk table lacks the column(s) {missing}.")
    df["Dimension"] = df["Attack"].map(lambda a: ATTACK_DIMS.get(a, a))
    df["Seed"] = df["Seed"].astype(int)
    return df.groupby(["Model", "Seed", "Dimension"], as_index=False)["Risk"].mean()


def _load_pickle(path: str):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _risk_df_indexed_list(results: dict, columns: Sequence, tools: Sequence[str]) -> pd.DataFrame:
    """Build a per-tool risk table from a {tool: [evaluator, ...]} pickle (SO / linkability)."""
    rows = {}
    for tool, evaluators in results.items():
        rows[tool] = {columns[i]: _final_risk(ev) for i, ev in enumerate(evaluators)}
    df = pd.DataFrame(rows).T
    df.index = list(tools)
    df.columns = list(columns)
    return df


def _risk_df_inference(results: dict, tools: Sequence[str]) -> pd.DataFrame:
    """Build a per-tool risk table from inference results ({tool: [(feature, evaluator_or_results), ...]}).

    Skips per-feature entries that failed (stored as an ``{"error": ...}`` dict).
    """
    rows = {}
    for tool, attributes in results.items():
        rows[tool] = {feat: _final_risk(ev) for feat, ev in attributes if not isinstance(ev, dict)}
    df = pd.DataFrame(rows).T
    df.index = [t for t in tools if t in results]
    return df


def overall_privacy_from_attacks(uni: dict, multi: dict, link: dict, infer: dict,
                                 tools: Sequence[str]) -> Dict[str, float]:
    """Combine live anonymeter attack outputs into the per-method overall privacy score.

    Args mirror the ``{tool: [...]}`` returns of the ``metrics.privacy`` functions. Uses the
    same rule as the pickle/CSV paths: naive-baseline replacement, per-category mean risk,
    then ``score = 1 - mean(4 category risks)``.
    """
    tools = list(tools)

    def _cat_mean(res: dict) -> pd.Series:
        if not res:
            return pd.Series(dtype=float)
        n = len(next(iter(res.values())))
        return _risk_df_indexed_list(res, list(range(n)), tools).mean(axis=1)

    uni_r, multi_r, link_r = _cat_mean(uni), _cat_mean(multi), _cat_mean(link)
    infer_r = _risk_df_inference(infer, tools).mean(axis=1) if infer else pd.Series(dtype=float)

    scores: Dict[str, float] = {}
    for tool in tools:
        vals = [s.get(tool, np.nan) for s in (uni_r, multi_r, link_r, infer_r)]
        scores[tool] = float(1.0 - np.nanmean(vals))
    return scores


def overall_privacy_from_pickles(
    pickle_root: str,
    seed: int,
    tools: Sequence[str] = tuple(DEFAULT_TOOLS),
) -> Dict[str, float]:
    """Compute the per-method overall privacy score for one seed from saved pickles.

    Expects the manuscript layout under ``pickle_root``::

        SinglingOut/UniSO/Seed_{seed}/SOUni_Results.pkl
        SinglingOut/MultiSO/Seed_{seed}/MultiSO_Results.pkl
        Linkability/Seed_{seed}/LinkabilityResults.pkl
        Inference/Seed_{seed}/results_inferences.pkl
    """
    tools = list(tools)
    uni = _risk_df_indexed_list(
        _load_pickle(os.path.join(pickle_root, "SinglingOut", "UniSO", f"Seed_{seed}", "SOUni_Results.pkl")),
        ["25%", "50%", "75%", "100%"], tools,
    ).mean(axis=1)
    multi = _risk_df_indexed_list(
        _load_pickle(os.path.join(pickle_root, "SinglingOut", "MultiSO", f"Seed_{seed}", "MultiSO_Results.pkl")),
        [2, 3, 5, 7, 10, 20, 50], tools,
    ).mean(axis=1)
    link = _risk_df_indexed_list(
        _load_pickle(os.path.join(pickle_root, "Linkability", f"Seed_{seed}", "LinkabilityResults.pkl")),
        ["25%", "50%", "75%", "100%"], tools,
    ).mean(axis=1)
    infer = _risk_df_inference(
        _load_pickle(os.path.join(pickle_root, "Inference", f"Seed_{seed}", "results_inferences.pkl")),
        tools,
    ).mean(axis=1)

    scores: Dict[str, float] = {}
    for tool in tools:
        combined = np.array([uni[tool], multi[tool], link[tool], infer[tool]], dtype=float)
        scores[tool] = float(1.0 - np.nanmean(combined))
    return scores


def overall_privacy_from_csv(
    csv_path: str,
    seed: int,
    tools: Sequence[str] = tuple(DEFAULT_TOOLS),
) -> Dict[str, float]:
    """Read a precomputed ``overal_privacy_score_{cancer}.csv`` for one seed.

    Rows are method display names, columns are seeds. Returns {method: score}.
    """
    df = pd.read_csv(csv_path, index_col=0)
    df.columns = [str(c) for c in df.columns]
    col = str(seed)
    if col not in df.columns:
        raise KeyError(f"Seed column '{col}' not found in {csv_path} (have {list(df.columns)}).")
    return {tool: float(df.loc[tool, col]) for tool in tools if tool in df.index}
