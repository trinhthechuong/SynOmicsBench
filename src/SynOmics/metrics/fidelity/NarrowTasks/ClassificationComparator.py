import json
import os
import warnings
from joblib import Parallel, delayed
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.base import clone
from sklearn.metrics import get_scorer
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score

from ..utils import (PreprocessingForValidation, check_column_consistency,
                    extract_metadata, np_encoder)


class SyntheticDataClassificationComparator:
    """
    Evaluate and compare the performance of machine learning models on real and synthetic tabular data.

    Args:
        synthetic_data (pd.DataFrame): Synthetic dataset.
        origin_data (pd.DataFrame): Real/original dataset.
        metadata_path (str): Path to metadata JSON file.
        target_column (str): Name of the target column.
        model (sklearn.base.BaseEstimator): scikit-learn estimator.
        n_splits (int): Number of cross-validation splits.
        n_repeats (int): Number of cross-validation repeats.
        metric (str or callable): Scoring metric compatible with scikit-learn.
        random_state (int, optional): Random seed. Defaults to 42.
        n_jobs (int, optional): Number of parallel jobs. Defaults to -1.

    Raises:
        ValueError: If column consistency check fails.
    """

    def __init__(
        self,
        synthetic_data: pd.DataFrame,
        origin_data: pd.DataFrame,
        metadata_path: str,
        target_col: str,
        model,
        n_splits: int,
        n_repeats: int,
        metric,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.origin_data = origin_data
        self.synthetic_data = synthetic_data
        self.target_col = target_col
        self.cv = RepeatedStratifiedKFold(
            n_splits=n_splits, n_repeats=n_repeats, random_state=random_state
        )

        self.model = model
        self.metric = metric
        self.metadata_path = metadata_path
        self.random_state = random_state
        self.n_jobs = n_jobs
        if not self._check_column_consistency(self.origin_data, self.synthetic_data):
            raise ValueError("Synthetic and real data columns are inconsistent.")
        # self.metadata_dict = self.extract_metadata(metadata_path)

    def _check_column_consistency(self, origin_data, synthetic_data) -> bool:
        """
        Check if the columns of the synthetic and real datasets are consistent.

        Returns:
            bool: True if columns match, False otherwise.
        """
        return check_column_consistency(origin_data, synthetic_data)

    def _load_metadata(self, data: pd.DataFrame) -> dict:
        """
        Extract column type metadata from a JSON file.

        Args:
            data (pd.DataFrame): DataFrame used to filter available columns.

        Returns:
            dict: Dictionary with keys 'numerical', 'ordinal_categorical', 'dummy_categorical',
                  and 'missing_categorical' mapping to lists of column names.

        Raises:
            FileNotFoundError: If the metadata file is not found.
            json.JSONDecodeError: If the metadata file is not a valid JSON.
        """
        return extract_metadata(data, self.metadata_path)

    def preprocess(
        self,
        original_data: pd.DataFrame,
        synthetic_data: pd.DataFrame,
        output_dir: str = ".",
        scaler: str = "minmax",
        n_neighbors: int = 5,
    ) -> pd.DataFrame:
        """
        Preprocess a DataFrame for machine learning tasks.

        Args:
            orginal_data (pd.DataFrame): Data to preprocess.
            synthetic_data (pd.DataFrame): Data to preprocess.
            output_dir (str): Output directory for preprocessing artifacts.
            scaler (str): Scaler to use for numerical features.
            n_neighbors (int): Number of neighbors for imputation if used.

        Returns:
            pd.DataFrame: Preprocessed DataFrame.
        """
        meta = self._load_metadata(original_data)
        or_preproc = PreprocessingForValidation(
            data=original_data,
            target_col=self.target_col,
            output_dir=output_dir,
            is_synthetic = False,
            ordinal_cat_columns=meta.get("ordinal_categorical", []),
            dummy_cat_columns=meta.get("dummy_categorical", []),
            numerical_columns=meta.get("numerical", []),
            scaler=scaler,
            n_neighbors=n_neighbors,
        )
        processed_or_df = or_preproc.fit()
        synth_preproc = PreprocessingForValidation(
            data=synthetic_data,
            target_col=self.target_col,
            output_dir=output_dir,
            is_synthetic = True,
            ordinal_cat_columns=meta.get("ordinal_categorical", []),
            dummy_cat_columns=meta.get("dummy_categorical", []),
            numerical_columns=meta.get("numerical", []),
            scaler=scaler,
            n_neighbors=n_neighbors,
        )
        processed_synth_df = synth_preproc.fit()
        is_consitency = self._check_column_consistency(processed_or_df, processed_synth_df)
        if is_consitency:
            return processed_or_df, processed_synth_df
        else:
            real_cols = set(processed_or_df.columns) - {self.target_col}
            synth_cols = set(processed_synth_df.columns) - {self.target_col}
            all_cols = sorted(real_cols | synth_cols)
            missing_in_real = synth_cols - real_cols
            missing_in_synth = real_cols - synth_cols
            
            warn_msg = (
            f"Column mismatch after preprocessing. "
            f"Missing in real: {missing_in_real}; "
            f"Missing in synthetic: {missing_in_synth}. "
            "Aligning columns and filling missing ones with zeros."
        )
            warnings.warn(warn_msg, UserWarning)
            or_preproc.logger.warning(warn_msg)
            synth_preproc.logger.warning(warn_msg)

            # Align columns and add target at the end
            align_or_df = processed_or_df.reindex(columns=all_cols + [self.target_col], fill_value=0)
            align_synth_df = processed_synth_df.reindex(columns=all_cols + [self.target_col], fill_value=0)
            return align_or_df, align_synth_df

    def _statistical_test(self, scores_a, scores_b) -> float:
        """
        Perform a Wilcoxon signed-rank test to compare two score distributions.

        Args:
            scores_a (array-like): First set of scores.
            scores_b (array-like): Second set of scores.

        Returns:
            float: Two-sided p-value from the Wilcoxon test.
        """
        differences = np.array(scores_a) - np.array(scores_b)
        if np.all(differences == 0):
            return 1.0
        _, p_value = wilcoxon(scores_a, scores_b, alternative="two-sided")
        return p_value

    def compare_cross_validation(
        self,
        output_dir: str = ".",
        scaler: str = "minmax",
        n_neighbors: int = 5,
        return_full_scores: bool = True,
        save: bool = True
    ) -> dict:
        """
        Compare cross-validation scores of a model trained on real and synthetic data.

        Args:
            output_dir (str): Output directory for preprocessing artifacts.
            scaler (str): Scaler to use for numerical features.
            n_neighbors (int): Number of neighbors for imputation if used.
            return_full_scores (bool): If True, return all scores. If False, return mean and std.

        Returns:
            dict: Results containing scores, improvement flag, and statistical test p-value.
        """
        real, synth = self.preprocess(self.origin_data, self.synthetic_data, output_dir, scaler, n_neighbors)
        # synth = self.preprocess(self.synthetic_data, output_dir, scaler, n_neighbors)
        X_real = real.drop(columns=[self.target_col])
        y_real = real[self.target_col]
        X_synth = synth.drop(columns=[self.target_col])
        y_synth = synth[self.target_col]

        rkf = self.cv
        scorer = get_scorer(self.metric)
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
            model_real = clone(self.model)
            # except ValueError:
                # model_real = clone(self.model)
            model_real.fit(X_real_train, y_real_train)
            orig_score = scorer(model_real, X_real_test, y_real_test)
    
            # try:
                # model_synth = clone(self.model).set_params(n_jobs=self.n_jobs)
            # except ValueError:
            model_synth = clone(self.model)
            model_synth.fit(X_synth_train, y_synth_train)
            synth_score = scorer(model_synth, X_real_test, y_real_test)
            return orig_score, synth_score
    
        results = Parallel(n_jobs=self.n_jobs)(
            delayed(fit_and_score)(real_train_idx, real_test_idx, synth_train_idx)
            for (real_train_idx, real_test_idx), (synth_train_idx, _) in zip(real_folds, synth_folds)
        )
        orig_scores, synth_scores = zip(*results)

        p_value = self._statistical_test(orig_scores, synth_scores)
        is_improved = np.mean(orig_scores) <= np.mean(synth_scores)

        if return_full_scores:
            compare_cross_validation_result = {
                "real_scores": orig_scores,
                "synthetic_scores": synth_scores,
                "is_improved": is_improved,
                "p_value": p_value,
            }
        else:
            compare_cross_validation_result = {
                "real_scores": [np.mean(orig_scores), np.std(orig_scores)],
                "synthetic_scores": [np.mean(synth_scores), np.std(synth_scores)],
                "is_improved": is_improved,
                "p_value": p_value,
            }
        if save:
            filepath = os.path.join(output_dir, "compare_cross_validation_result.json")
            with open(filepath, "w") as f:
                json.dump(compare_cross_validation_result, f, indent=4, default=np_encoder)
        return compare_cross_validation_result

    def compare_with_augmentation(
        self,
        output_dir: str = ".",
        scaler: str = "minmax",
        n_neighbors: int = 5,
        return_full_scores: bool = True,
        save: bool = True
    ) -> dict:
        """
        Assess if augmenting real data with synthetic data improves model performance.

        Args:
            output_dir (str): Output directory for preprocessing artifacts.
            scaler (str): Scaler to use for numerical features.
            n_neighbors (int): Number of neighbors for imputation if used.
            return_full_scores (bool): If True, return all scores. If False, return mean and std.

        Returns:
            dict: Results containing scores, improvement flag, and statistical test p-value.
        """
        real, synth = self.preprocess(self.origin_data, self.synthetic_data, output_dir, scaler, n_neighbors)
        # synth = self.preprocess(self.synthetic_data, output_dir, scaler, n_neighbors)

        X_real = real.drop(columns=[self.target_col])
        y_real = real[self.target_col]
        X_synth = synth.drop(columns=[self.target_col])
        y_synth = synth[self.target_col]

        rkf = self.cv
        scorer = get_scorer(self.metric)
        # orig_scores, aug_scores = [], []

        real_folds = list(rkf.split(X_real, y_real))
        synth_folds = list(rkf.split(X_synth, y_synth))

        def fit_and_score(real_train_idx, real_test_idx, synth_train_idx):
            X_train, X_test = X_real.iloc[real_train_idx], X_real.iloc[real_test_idx]
            y_train, y_test = y_real.iloc[real_train_idx], y_real.iloc[real_test_idx]
            X_aug_train = pd.concat([X_train, X_synth.iloc[synth_train_idx]], axis=0).reset_index(drop=True)
            y_aug_train = pd.concat([y_train, y_synth.iloc[synth_train_idx]], axis=0).reset_index(drop=True)
    
            # Try to set n_jobs if supported
            # try:
            #     model_real = clone(self.model).set_params(n_jobs=self.n_jobs)
            # except ValueError:
            model_real = clone(self.model)
            model_real.fit(X_train, y_train)
            orig_score = scorer(model_real, X_test, y_test)
    
            # try:
                # model_aug = clone(self.model).set_params(n_jobs=self.n_jobs)
            # except ValueError:
            model_aug = clone(self.model)
            model_aug.fit(X_aug_train, y_aug_train)
            aug_score = scorer(model_aug, X_test, y_test)
            return orig_score, aug_score

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(fit_and_score)(real_train_idx, real_test_idx, synth_train_idx)
            for (real_train_idx, real_test_idx), (synth_train_idx, _) in zip(real_folds, synth_folds)
        )
        orig_scores, aug_scores = zip(*results)

        p_value = self._statistical_test(orig_scores, aug_scores)
        is_improved = np.mean(orig_scores) <= np.mean(aug_scores)

        if return_full_scores:
            compare_with_augmentation_result = {
                "real_scores": orig_scores,
                "augmented_scores": aug_scores,
                "is_improved": is_improved,
                "p_value": p_value,
            }
        else:
            compare_with_augmentation_result = {
                "real_scores": [np.mean(orig_scores), np.std(orig_scores)],
                "augmented_scores": [np.mean(aug_scores), np.std(aug_scores)],
                "is_improved": is_improved,
                "p_value": p_value,
            }
        if save:
            filepath = os.path.join(output_dir, "compare_with_augmentation_result.json")
            with open(filepath, "w") as f:
                json.dump(compare_with_augmentation_result, f, indent=4, default=np_encoder)
        return compare_with_augmentation_result


if __name__ == "__main__":
    # synthetic_data = pd.read_csv("../../../Job_submitting/CTGAN_23072025/CTGAN_synthetic_data.csv", index_col = 0)
    # origin_data = pd.read_csv("../../../Job_submitting/Notebook/Integration_pipeline_JOBIM/integrated_data_jobim.csv", index_col=0)
    # meta_data_path = "../../../Job_submitting/Notebook/Integration_pipeline_JOBIM/feature_metadata.json"
    pass
