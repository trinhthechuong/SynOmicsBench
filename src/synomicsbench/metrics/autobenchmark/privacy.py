"""
Privacy risks of the four attack categories of the automatic benchmark.

Each attack category (univariate singling out, multivariate singling out, linkability,
attribute inference) is one meta-score dimension; its value is the mean, over the attack's
configurations (``n_cols`` values, secrets), of

* the residual risk ``(R_attack - R_control) / (1 - R_control)`` when the attack was run
  against a control cohort, or
* the attack risk floored at the naive (random-guess) risk otherwise.

Lower is better.
"""

from __future__ import annotations

from typing import Dict

import numpy as np


#: attack label -> meta-score dimension
ATTACK_DIMS = {
    "SO_uni": "Singling-out (uni)",
    "SO_multi": "Singling-out (multi)",
    "Linkability": "Linkability",
    "Inference": "Inference",
}


def _final_risk(obj) -> float:
    """Attack risk floored at the naive baseline.

    Accepts an Anonymeter evaluator or an ``EvaluationResults`` object. Without a
    ``baseline`` risk (an ``EvaluationResults``), the attack risk is returned as is.
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

    The arguments are the ``{dataset: [...]}`` returns of the ``metrics.privacy`` functions
    (``None`` for an attack that was not run); failed inference evaluations
    (``{"error": ...}``) are skipped.

    Returns:
        dict: dimension name (see ``ATTACK_DIMS``) -> {dataset: mean risk}.
    """
    def _mean(items) -> float:
        vals = []
        for item in items:
            ev = item[-1] if isinstance(item, tuple) else item
            if not isinstance(ev, dict):
                vals.append(_category_risk(ev))
        return float(np.mean(vals)) if vals else float("nan")

    out: Dict[str, Dict[str, float]] = {}
    for key, res in (("SO_uni", uni), ("SO_multi", multi), ("Linkability", link), ("Inference", infer)):
        out[ATTACK_DIMS[key]] = {tool: _mean(items) for tool, items in (res or {}).items()}
    return out
