"""
Privacy dimension via reuse of saved anonymeter evaluator pickles.

The privacy attacks (anonymeter) are stochastic, so re-running them would not
reproduce the manuscript numbers. Instead we reuse the saved evaluator pickles
(singling-out univariate/multivariate, linkability, inference), extract the risk
of each with the same naive-baseline replacement rule used in
``Manuscript/FigurePrivacy/OveralScore_Bayesian.ipynb``, and combine them into
the per-method overall privacy score::

    overall_risk  = mean(uni_SO, multi_SO, linkability, inference)   # per method
    privacy_score = 1 - overall_risk

A robust fallback reads the already-aggregated ``overal_privacy_score_{cancer}.csv``
(rows = method display names, columns = seeds), which is the canonical artifact
that file itself was produced from.
"""

from __future__ import annotations

import os
import pickle
from typing import Dict, Sequence

import numpy as np
import pandas as pd


DEFAULT_TOOLS = ["Avatars K5", "Avatars K10", "CTGAN", "Gaussian Copula", "Synthpop", "TVAE"]


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
