"""
Predictive model comparison module for evaluating synthetic data utility.

This module provides utilities for comparing the performance of predictive models
trained on original vs synthetic data, assessing whether synthetic data can be used
for downstream machine learning tasks.

Functions:
    compare_cross_validation: Compare CV scores between real and synthetic data
    SyntheticDataClassificationComparator: Main comparator class
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import clone
from sklearn.metrics import get_scorer
from sklearn.model_selection import BaseCrossValidator
from scipy.stats import wilcoxon



DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}


def _statistical_test(a,b):
    diff = np.array(a)-np.array(b)
    if np.all(diff==0): return 1.0
    _, p = wilcoxon(a,b,alternative="two-sided")
    return p

def compare_cross_validation(
    real,
    synth,
    target_col,
    model,
    cv, 
    metric, 
    n_jobs = -1
) -> dict:

    X_real = real.drop(columns=[target_col])
    y_real = real[target_col]
    X_synth = synth.drop(columns=[target_col])
    y_synth = synth[target_col]

    rkf = cv
    scorer = get_scorer(metric)
    # orig_scores, synth_scores = [], []

    real_folds = list(rkf.split(X_real, y_real))
    synth_folds = list(rkf.split(X_synth, y_synth))
    
    def fit_and_score(real_train_idx, real_test_idx, synth_train_idx):
        X_real_train, X_real_test = (
            X_real.iloc[real_train_idx],
            X_real.iloc[real_test_idx],
        )
        y_real_train, y_real_test = (
            y_real.iloc[real_train_idx],
            y_real.iloc[real_test_idx],
        )

        X_synth_train = X_synth.iloc[synth_train_idx]
        y_synth_train = y_synth.iloc[synth_train_idx]

        # Try to set n_jobs if supported
        # try:
        model_real = clone(model)
        # except ValueError:
            # model_real = clone(self.model)
        model_real.fit(X_real_train, y_real_train)
        orig_score = scorer(model_real, X_real_test, y_real_test)

        # try:
            # model_synth = clone(self.model).set_params(n_jobs=self.n_jobs)
        # except ValueError:
        model_synth = clone(model)
        model_synth.fit(X_synth_train, y_synth_train)
        synth_score = scorer(model_synth, X_real_test, y_real_test)
        return orig_score, synth_score

    results = Parallel(n_jobs=n_jobs)(
        delayed(fit_and_score)(real_train_idx, real_test_idx, synth_train_idx)
        for (real_train_idx, real_test_idx), (synth_train_idx, _) in zip(real_folds, synth_folds)
    )
    orig_scores, synth_scores = zip(*results)

    p_value = _statistical_test(orig_scores, synth_scores)
    is_improved = np.mean(orig_scores) <= np.mean(synth_scores)

    compare_cross_validation_result = {
        "real_scores": orig_scores,
        "synthetic_scores": synth_scores,
        "is_improved": is_improved,
        "p_value": p_value,
    }

    return compare_cross_validation_result