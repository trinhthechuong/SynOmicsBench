"""
Singling-out risk evaluation for synthetic data.

Refactored from ``ccRCC/Privacy/SinglingOut/singlingout_experiment.py``.
Provides helper functions that wrap the Anonymeter SinglingOutEvaluator
to run univariate and multivariate singling-out attacks across multiple
feature-sampling proportions.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
from anonymeter.evaluators import SinglingOutEvaluator


def eval_singling_out_univariate(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    n_attacks: int = 10_000,
    max_attempts: int = 1_000_000,
    proportions: Sequence[float] = (0.25, 0.50, 0.75, 1.0),
    seed: int = 42,
) -> Dict[str, List[SinglingOutEvaluator]]:
    """Run univariate singling-out attacks at varying feature proportions.

    For each synthetic dataset and each proportion *p*, a random subset of
    *p × n_features* columns is selected and the ``SinglingOutEvaluator``
    is run in ``univariate`` mode.

    Args:
        ori: Original (real) dataset after post-processing.
        syns: Mapping from synthetic dataset name to its DataFrame.
        n_attacks: Number of attack predicates to generate per evaluation.
        max_attempts: Maximum predicate generation attempts.
        proportions: Fractions of columns to sample (e.g. 25 %, 50 %, …).
        seed: Random seed for column sampling and the evaluator.

    Returns:
        Mapping from synthetic dataset name to a list of evaluated
        ``SinglingOutEvaluator`` instances (one per proportion).
    """
    results: Dict[str, List[SinglingOutEvaluator]] = {}

    for syn_name, syn_df in syns.items():
        random.seed(seed)
        cols = ori.columns.tolist()
        risks: List[SinglingOutEvaluator] = []

        for p in proportions:
            n = int(len(cols) * p)
            sampled_cols = random.sample(cols, n)
            evaluator = SinglingOutEvaluator(
                ori=ori[sampled_cols],
                syn=syn_df[sampled_cols],
                n_attacks=n_attacks,
                max_attempts=max_attempts,
                seed=seed,
            )
            evaluator.evaluate(mode="univariate")
            risks.append(evaluator)

        results[syn_name] = risks

    return results


def eval_singling_out_multivariate(
    ori: pd.DataFrame,
    syns: Dict[str, pd.DataFrame],
    n_cols_list: Sequence[int] = (2, 3, 5, 7, 10, 20, 50),
    n_attacks: int = 10_000,
    max_attempts: int = 1_000_000,
    seed: int = 42,
) -> Dict[str, List[SinglingOutEvaluator]]:
    """Run multivariate singling-out attacks at varying attribute-combination sizes.

    Args:
        ori: Original dataset.
        syns: Mapping from synthetic dataset name to its DataFrame.
        n_cols_list: Number of columns the attacker uses per predicate.
        n_attacks: Number of attack predicates per evaluation.
        max_attempts: Maximum predicate generation attempts.
        seed: Random seed.

    Returns:
        Mapping from synthetic dataset name to a list of evaluated
        ``SinglingOutEvaluator`` instances (one per ``n_cols`` value).
    """
    results: Dict[str, List[SinglingOutEvaluator]] = {}

    for syn_name, syn_df in syns.items():
        risks: List[SinglingOutEvaluator] = []
        for n_col in n_cols_list:
            evaluator = SinglingOutEvaluator(
                ori=ori,
                syn=syn_df,
                n_cols=n_col,
                n_attacks=n_attacks,
                max_attempts=max_attempts,
                seed=seed,
            )
            evaluator.evaluate(mode="multivariate")
            risks.append(evaluator)
        results[syn_name] = risks

    return results
