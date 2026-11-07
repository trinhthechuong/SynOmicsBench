"""
Tidy risk tables from the privacy attack results.

Every attack function of :mod:`synomicsbench.metrics.privacy` returns, per synthetic
dataset, a list of evaluated Anonymeter evaluators (or ``(level, secret, results)`` tuples
for attribute inference). :func:`privacy_risk_table` turns them into one row per evaluation.

* With a control dataset, the reported risk is Anonymeter's residual risk
  ``R_residual = (R_attack - R_control) / (1 - R_control)``, bounded below by zero: the
  part of the attack's success that it would not also achieve on patients the generator
  never saw. ``R_attack`` and ``R_control`` are reported alongside.
* Without a control dataset, the attack risk ``R_attack`` is reported with the risk of a
  naive attacker guessing at random, ``R_naive``; an attack that does not beat it has
  failed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

RESIDUAL_COLUMNS = [
    "R_residual", "R_residual_ci_low", "R_residual_ci_high",
    "R_attack", "R_attack_ci_low", "R_attack_ci_high", "R_control",
]
NAIVE_COLUMNS = [
    "R_attack", "R_attack_ci_low", "R_attack_ci_high",
    "R_naive", "R_naive_ci_low", "R_naive_ci_high",
]


def _results(item: Any, confidence_level: float):
    """``EvaluationResults`` of an evaluator, or the results object itself."""
    if hasattr(item, "results") and callable(item.results):
        return item.results(confidence_level=confidence_level)
    return item


def risk_record(res: Any) -> Dict[str, float]:
    """Risks of one evaluation (an Anonymeter ``EvaluationResults``).

    Returns:
        With a control set: R_residual (+ CI), R_attack (+ CI) and R_control.
        Without: R_attack (+ CI) and R_naive (+ CI).
    """
    attack = res.attack_rate.to_risk()
    row = {
        "R_attack": float(attack.value),
        "R_attack_ci_low": float(attack.ci[0]),
        "R_attack_ci_high": float(attack.ci[1]),
    }
    if res.control_rate is not None:
        residual = res.risk()
        row.update({
            "R_residual": float(residual.value),
            "R_residual_ci_low": float(residual.ci[0]),
            "R_residual_ci_high": float(residual.ci[1]),
            "R_control": float(res.control_rate.value),
        })
    else:
        naive = res.risk(baseline=True)
        row.update({
            "R_naive": float(naive.value),
            "R_naive_ci_low": float(naive.ci[0]),
            "R_naive_ci_high": float(naive.ci[1]),
        })
    return row


def privacy_risk_table(
    results: Mapping[str, Sequence[Any]],
    attack: str,
    configs: Optional[Sequence[str]] = None,
    confidence_level: float = 0.95,
) -> pd.DataFrame:
    """One row per evaluation of one attack family.

    Args:
        results: Output of one attack function, ``{dataset: [evaluator, ...]}`` or, for
            attribute inference, ``{dataset: [(level, secret, results), ...]}``.
        attack: Attack name written in the ``Attack`` column (e.g. ``"Singling out (univariate)"``).
        configs: Label of each evaluation in the lists, e.g. the knowledge levels
            (``["FGES", "25%", "100%"]``) or the ``n_cols`` values; defaults to the position
            in the list. Inference results carry their level (``Config``) and secret
            (``Secret`` column).
        confidence_level: Confidence level of the intervals.

    Returns:
        pd.DataFrame: Columns Dataset, Attack, Config (and Secret for inference), then the
        residual-risk columns
        (R_residual, its CI, R_attack, its CI, R_control) when the evaluations used a
        control dataset, otherwise R_attack, its CI and R_naive with its CI. Failed
        inference evaluations are left out.
    """
    rows: List[Dict[str, Any]] = []
    for dataset, items in results.items():
        for i, item in enumerate(items):
            if isinstance(item, tuple):
                level, secret, item = item
                labels = {"Config": str(level), "Secret": str(secret)}
            else:
                labels = {"Config": str(configs[i]) if configs is not None else str(i)}
            if isinstance(item, dict):
                continue
            res = _results(item, confidence_level)
            rows.append({"Dataset": dataset, "Attack": attack, **labels, **risk_record(res)})

    table = pd.DataFrame(rows)
    if table.empty:
        return pd.DataFrame(columns=["Dataset", "Attack", "Config", *NAIVE_COLUMNS])
    risk_cols = RESIDUAL_COLUMNS if "R_residual" in table.columns else NAIVE_COLUMNS
    keys = [c for c in ("Dataset", "Attack", "Config", "Secret") if c in table.columns]
    extra = [c for c in table.columns if c not in risk_cols and c not in keys]
    return table[[*keys, *risk_cols, *extra]].replace({None: np.nan})
