import sys
import os
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from typing import List, Tuple, Union, Optional
from synomicsbench.processing.metadata import MetaData
from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.utils.correlations import MixedCorrelation
from tqdm import tqdm
from synomicsbench.utils.monitoring import monitor_resources

class PairwiseSimilarity:
    """
    Compute and analyze pairwise similarity metrics (Pearson and contingency) between columns of original and synthetic datasets.

    Args:
        original_data (pd.DataFrame): Input original dataset.
        synthetic_data (pd.DataFrame): Input synthetic dataset.
        metadata (dict): Column type metadata.
        output_dir (str): Directory for logs and outputs.

    Returns:
        PairwiseSimilarity: An initialized instance for similarity analysis.

    Raises:
        OSError: If the output directory cannot be created.
    """

    def __init__(self, original_data: pd.DataFrame, synthetic_data: pd.DataFrame, metadata: dict, output_dir: str="", verbose: bool=False, save: bool=True, name: str=''):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.all_columns = original_data.columns.to_list()
        self.original_data = original_data
        self.synthetic_data = synthetic_data
        self.metadata = metadata
        if set(metadata.keys()) != set(original_data.columns):
            raise RuntimeError("metadata does not match columns in the data.")
        self.grouping_metadata = MetaData.grouping_features_astype(self.original_data, self.metadata)
        self.numerical_features = self.grouping_metadata.get("numerical")
        self.ordinal_features = self.grouping_metadata.get("ordinal_categorical") 
        self.dummy_features = self.grouping_metadata.get("dummy_categorical") 
        self.missing_indicators = self.grouping_metadata.get("missing_categorical")
        
        self.categorical_features = self.dummy_features + self.ordinal_features + self.missing_indicators
        self.numerical_indices = MetaData.get_column_indices(self.original_data, self.numerical_features)
        self.categorical_indices = MetaData.get_column_indices(self.original_data, self.categorical_features)
        self.verbose = verbose
        self.square_form_or_corr = None
        self.square_form_syn_corr = None
        self.square_form_score_matrix = None
        self.save = save
        self.name = name

    @staticmethod
    def save(path, condensed):
        condensed = np.asarray(condensed)
        np.save(path, condensed)
        
    def _process(self, data: pd.DataFrame, metadata: dict):
        """
        Preprocess data by encoding categorical features and returning the processed DataFrame.

        Args:
            data (pd.DataFrame): Input data.
            metadata (dict): Metadata for grouping features.

        Returns:
            pd.DataFrame: Preprocessed DataFrame.

        Raises:
            ValueError: If no columns are specified for processing.
        """
        column_order = data.columns.to_list()
        self.grouping_metadata = MetaData.grouping_features_astype(data, metadata)
        num_features =  self.grouping_metadata.get("numerical")
        # print(num_features)
        ordinal_features = self.grouping_metadata.get("ordinal_categorical")
        # print(ordinal_features)
        dummy_features = self.grouping_metadata.get("dummy_categorical")
        # print(dummy_features)
        missing_indicators = self.grouping_metadata.get("missing_categorical")
        # print(missing_indicators)
        preprocessed_parts = []
        if ordinal_features: 
            ordinal_data = data[ordinal_features]
            ordinal_encoded, _ = DataProcessor.encode_ordinal_features(ordinal_data)
            preprocessed_parts.append(ordinal_encoded)

        if dummy_features:
            dummy_data = data[dummy_features]
            dummy_encoded,_ = DataProcessor.encode_ordinal_features(dummy_data)
            preprocessed_parts.append(dummy_encoded)

        if num_features:
            numerical_data = data[num_features]
            preprocessed_parts.append(numerical_data)

        if missing_indicators:
            missing_indicators_data = data[missing_indicators]
            preprocessed_parts.append(missing_indicators_data)

        if not preprocessed_parts:
            raise ValueError("No columns specified for processing")
        
        data_preprocessed = pd.concat(preprocessed_parts, axis=1)
        data_preprocessed = data_preprocessed[column_order]
        return data_preprocessed            

    def _calculate_corr_matrix(self, data: pd.DataFrame, method: str = "spearman", n_bins: int=10):
        """
        Calculate the mixed correlation matrix (Pearson, Spearman, Cramér's V) for the given data.

        Args:
            data (pd.DataFrame): Input data.
            method (str): Correlation method.
            n_bins (int): Number of bins for discretization.

        Returns:
            np.ndarray: Correlation matrix.
        """
        corr_matrix_computer = MixedCorrelation(self.categorical_indices, self.numerical_indices, method=method, n_bins=n_bins)
        corr_matrix = corr_matrix_computer.compute(data)
        return corr_matrix

    def _calculate_score_matrix(self, original_matrix: np.array, synthetic_matrix: np.array):
        """
        Calculate the similarity score matrix between original and synthetic data.
        Scoring rules (direction-aware):
            - numeric-numeric (Spearman/Pearson in [-1, 1]):
                score = 1 - 0.5 * |delta|
            - categorical-categorical OR categorical-(binned numeric) (Cramér's V in [0, 1]):
                score = 1 - |delta|
        Args:
            original_matrix (np.array): Correlation matrix for original data.
            synthetic_matrix (np.array): Correlation matrix for synthetic data.

        Returns:
            np.array: Similarity score matrix.

        Raises:
            ValueError: If calculation fails.
        """
        
        # try:
        #     score_matrix = 1 - 0.5 * np.abs(original_matrix - synthetic_matrix)
        #     return score_matrix
        # except Exception as e:
        #     raise ValueError(f"Error in calculating score matrix: {e}")
        
        if original_matrix.shape != synthetic_matrix.shape:
            raise ValueError("original_matrix and synthetic_matrix must have the same shape.")

        A = np.asarray(original_matrix, dtype=float)
        B = np.asarray(synthetic_matrix, dtype=float)
        n = A.shape[0]

        num_set = set(int(i) for i in self.numerical_indices)
        score = np.ones((n, n), dtype=float)

        for i in range(n):
            score[i, i] = 1.0
            for j in range(i + 1, n):
                if (i in num_set) and (j in num_set):
                    # Spearman/Pearson: [-1, 1] => max delta = 2
                    d = abs(A[i, j] - B[i, j])
                    s = 1.0 - 0.5 * d
                else:
                    # Cramér's V (including cat-num after discretization): [0, 1] => max delta = 1
                    d = abs(A[i, j] - B[i, j])
                    s = 1.0 - d

                score[i, j] = s
                score[j, i] = s

        np.clip(score, 0.0, 1.0, out=score)
        return score
        
    def print_condensed_matrix_summary(self, condensed_matrix: np.ndarray, name: str = "Condensed Matrix"):
        """
        Print statistical summary of a condensed matrix (1D array containing the upper triangle of a square matrix).

        Args:
            condensed_matrix (np.ndarray): 1D numpy array containing condensed matrix values.
            name (str): Name for display.

        Returns:
            None

        Raises:
            ValueError: If condensed_matrix is not a 1D numpy array.
        """
        if not isinstance(condensed_matrix, np.ndarray) or condensed_matrix.ndim != 1:
            raise ValueError("condensed_matrix must be a 1D numpy array.")
        print(f"Summary of {name}:")
        print(f"  Number of elements: {condensed_matrix.size}")
        print(f"  Min value: {np.min(condensed_matrix):.4f}")
        print(f"  Max value: {np.max(condensed_matrix):.4f}")
        print(f"  Mean: {np.mean(condensed_matrix):.4f}")
        print(f"  Median: {np.median(condensed_matrix):.4f}")
        print(f"  Standard deviation: {np.std(condensed_matrix):.4f}")

    @monitor_resources
    def get_pairwise_scores(self, method: str, n_bins: int = 10):
        """
        Compute the pairwise similarity matrices and print summary statistics.

        Args:
            method (str): Correlation method for MixedCorrelation.
            n_bins (int): Number of bins for discretization (default 10).

        Returns:
            dict: Dictionary containing pairwise score matrix, original condensed correlation, and synthetic condensed correlation.

        Raises:
            Exception: If any computation or extraction fails.
        """
        try:
            if self.verbose: 
                print("Processing data")
            processed_or_df = self._process(self.original_data, self.metadata)
            processed_syn_df = self._process(self.synthetic_data, self.metadata)
            
            if self.verbose:
                print(f"Calculating correlation matrix for both original data and synthetic data. This matrix is mixed between {method} correlation and Cramér's V.")
                
            or_corr_matrix = self._calculate_corr_matrix(processed_or_df, method, n_bins)
            syn_corr_matrix = self._calculate_corr_matrix(processed_syn_df, method, n_bins)
            
            self.square_form_or_corr = MixedCorrelation.get_squareform(or_corr_matrix)
            self.square_form_syn_corr = MixedCorrelation.get_squareform(syn_corr_matrix)
            
            # self.square_form_score_matrix = self._calculate_score_matrix(self.square_form_or_corr, self.square_form_syn_corr)
            # Compute score on square matrix, then condense
            score_square = self._calculate_score_matrix(or_corr_matrix, syn_corr_matrix)
            self.square_form_score_matrix = MixedCorrelation.get_squareform(score_square)
            
            # overall_score = np.mean(self.square_form_score_matrix)
            if self.verbose:
                print("\nSummary of Pairwise score:")
                self.print_condensed_matrix_summary(self.square_form_score_matrix, "Pairwise Score Matrix")
            if self.save:
                fig = PairwiseSimilarity.plot_column_score_histogram(self.square_form_score_matrix, 
                                                              data_name = self.name)
                fig_path = os.path.join(self.output_dir, f"{self.name}.png")
                fig.savefig(fig_path, dpi=300, bbox_inches='tight')
                plt.close(fig)
                
                # dict_path = os.path.join(self.output_dir, f"{self.name}_pairwisescore.npy")
                # PairwiseSimilarity.save(dict_path, self.square_form_score_matrix)
                
            dict_results = {
                "PairwiseScore": self.square_form_score_matrix,
                "OriginalCorrelation": self.square_form_or_corr,
                "SyntheticCorrelation": self.square_form_syn_corr
            }
            return dict_results
        except Exception as e:
            raise Exception(f"Error in get_scores: {e}")

    def get_single_associations(
        self,
        feature_1: Union[str, int],
        feature_2: Union[str, int],
        score_matrix: Optional[np.array] = None,
        original_matrix: Optional[np.array] = None,
        synthetic_matrix: Optional[np.array] = None
    ):
        """
        Retrieve detailed correlation and score between two features from the condensed correlation matrices.

        Args:
            feature_1 (Union[str, int]): First feature name or column index.
            feature_2 (Union[str, int]): Second feature name or column index.
            score_matrix (Optional[np.array]): Condensed score matrix.
            original_matrix (Optional[np.array]): Condensed correlation matrix for original data.
            synthetic_matrix (Optional[np.array]): Condensed correlation matrix for synthetic data.

        Returns:
            dict: Dictionary containing feature names, metric type, original correlation, synthetic correlation, and score.

        Raises:
            RuntimeError: If features are not in the data, or indices are out-of-bounds.
            ValueError: If correlation matrices are not provided.
        """
        # Convert feature names to indices if necessary
        if isinstance(feature_1, str):
            if feature_1 not in self.all_columns or feature_2 not in self.all_columns:
                raise RuntimeError(f"{feature_1} and {feature_2} are not in data")
            feature_1 = MetaData.get_column_indices(self.original_data, [feature_1])[0]
            feature_2 = MetaData.get_column_indices(self.original_data, [feature_2])[0]
        else:
            n_cols = self.original_data.shape[1]
            if feature_1 >= n_cols or feature_2 >= n_cols or feature_1 < 0 or feature_2 < 0:
                raise RuntimeError(f"Exceed the range. Data has {len(self.all_columns)} columns")

        # Use instance variables if parameters not provided
        if original_matrix is None:
            if self.square_form_or_corr is None:
                raise ValueError("Original correlation matrix is not provided.")
            original_matrix = self.square_form_or_corr
        if synthetic_matrix is None:
            if self.square_form_syn_corr is None:
                raise ValueError("Synthetic correlation matrix is not provided.")
            synthetic_matrix = self.square_form_syn_corr
        if score_matrix is None:
            if self.square_form_score_matrix is None:
                raise ValueError("Score matrix is not provided.")
            score_matrix = self.square_form_score_matrix

        n = self.original_data.shape[1]
        # Always make sure i < j for condensed index
        i, j = sorted([feature_1, feature_2])
        if i ==j:
            or_corr = 1.0
            syn_corr = 1.0
            score = 1.0
        else:
            k = n * i - i * (i + 1) // 2 + (j - i - 1)
            or_corr = original_matrix[k]
            syn_corr = synthetic_matrix[k]
            score = score_matrix[k]

        metrics = "CramersV_Correlation" if (feature_1 in self.categorical_indices or feature_2 in self.categorical_indices) else "Spearman_Correlation"

        results = {
            "Feature_1": self.all_columns[feature_1],
            "Feature_2": self.all_columns[feature_2],
            "Metrics": metrics,
            "Original_Correlation": or_corr,
            "Synthetic_Correlation": syn_corr,
            "Score": score
        }
        return results


    @monitor_resources
    def get_multiple_associations(
        self,
        feature_pairs: List[Tuple[Union[str, int], Union[str, int]]],
        score_matrix: Optional[np.ndarray] = None,
        original_matrix: Optional[np.ndarray] = None,
        synthetic_matrix: Optional[np.ndarray] = None,
        condensed: bool = True,
    ) -> pd.DataFrame:
        """
        Extract association metrics for multiple feature pairs using vectorized indexing.

        This implementation minimizes Python-loop overhead by computing all indices at once and
        gathering values from correlation/score matrices via NumPy advanced indexing.

        Args:
            feature_pairs (List[Tuple[Union[str, int], Union[str, int]]]):
                List of (feature_1, feature_2) pairs specified by name or index.
            score_matrix (Optional[np.ndarray]):
                Score matrix. If `condensed=True`, must be 1D of length n*(n-1)/2; if `condensed=False`,
                must be square (n x n). If None, uses `self.square_form_score_matrix`.
            original_matrix (Optional[np.ndarray]):
                Original correlation matrix (condensed or square depending on `condensed`).
                If None, uses `self.square_form_or_corr`.
            synthetic_matrix (Optional[np.ndarray]):
                Synthetic correlation matrix (condensed or square depending on `condensed`).
                If None, uses `self.square_form_syn_corr`.
            condensed (bool):
                If True, matrices are interpreted as condensed upper-triangular vectors (no diagonal).
                If False, matrices are interpreted as square (n x n) arrays.

        Returns:
            pd.DataFrame: DataFrame with columns:
                - 'Feature_1'
                - 'Feature_2'
                - 'Metrics' ("CramersV_Correlation" if either feature is categorical, else "Spearman_Correlation")
                - 'Original_Correlation'
                - 'Synthetic_Correlation'
                - 'Score'

        Raises:
            RuntimeError:
                - If any feature name is not in the data.
                - If any feature index is out-of-bounds.
                - If any pair repeats the same feature (i == j) when `condensed=True`.
            ValueError:
                - If required matrices are not provided.
                - If provided matrix shapes are inconsistent with `condensed`.
        """
        # Resolve matrices
        if original_matrix is None:
            if self.square_form_or_corr is None:
                raise ValueError("Original correlation matrix is not provided.")
            original_matrix = self.square_form_or_corr
        if synthetic_matrix is None:
            if self.square_form_syn_corr is None:
                raise ValueError("Synthetic correlation matrix is not provided.")
            synthetic_matrix = self.square_form_syn_corr
        if score_matrix is None:
            if self.square_form_score_matrix is None:
                raise ValueError("Score matrix is not provided.")
            score_matrix = self.square_form_score_matrix

        # Validate shapes against number of columns
        n_cols = int(self.original_data.shape[1])
        if condensed:
            expected_len = n_cols * (n_cols - 1) // 2
            for name, arr in (
                ("original_matrix", original_matrix),
                ("synthetic_matrix", synthetic_matrix),
                ("score_matrix", score_matrix),
            ):
                if arr.ndim != 1:
                    raise ValueError(f"{name} must be 1D (condensed), got shape {arr.shape}.")
                if arr.size != expected_len:
                    raise ValueError(
                        f"{name} length {arr.size} != expected {expected_len} for n={n_cols}."
                    )
        else:
            for name, arr in (
                ("original_matrix", original_matrix),
                ("synthetic_matrix", synthetic_matrix),
                ("score_matrix", score_matrix),
            ):
                if arr.ndim != 2 or arr.shape != (n_cols, n_cols):
                    raise ValueError(
                        f"{name} must be square with shape ({n_cols}, {n_cols}), got {arr.shape}."
                    )

        # Resolve pairs to indices (vector-friendly via list -> arrays)
        name_to_idx = {name: idx for idx, name in enumerate(self.all_columns)}

        def resolve_one(x: Union[str, int]) -> int:
            if isinstance(x, str):
                if x not in name_to_idx:
                    raise RuntimeError(f"Feature '{x}' is not in data.")
                return name_to_idx[x]
            if isinstance(x, int):
                return x
            raise RuntimeError(f"Feature identifier must be str or int, got {type(x)}")

        idx_pairs = np.array([(resolve_one(a), resolve_one(b)) for a, b in feature_pairs], dtype=int)
        i_arr = idx_pairs[:, 0]
        j_arr = idx_pairs[:, 1]

        # Bounds check
        if (i_arr.min() < 0) or (j_arr.min() < 0) or (i_arr.max() >= n_cols) or (j_arr.max() >= n_cols):
            raise RuntimeError(f"Index out of bounds. Data has {len(self.all_columns)} columns.")

        # Disallow i == j for condensed form (undefined index on diagonal)
        if condensed and np.any(i_arr == j_arr):
            raise RuntimeError("Pairs with identical features (i == j) are not allowed in condensed form.")

        # For condensed, enforce i<j to index the upper triangle vector
        if condensed:
            imin = np.minimum(i_arr, j_arr)
            jmax = np.maximum(i_arr, j_arr)
            # condensed index formula (upper triangle, no diag), matches squareform
            # k = n*i - i*(i+1)//2 + (j - i - 1)
            k_arr = n_cols * imin - imin * (imin + 1) // 2 + (jmax - imin - 1)
            original_vals = original_matrix[k_arr]
            synthetic_vals = synthetic_matrix[k_arr]
            score_vals = score_matrix[k_arr]
            # Keep display names aligned to original input order (use original i_arr, j_arr)
            f1_idx, f2_idx = i_arr, j_arr
        else:
            # Square matrix direct advanced indexing
            original_vals = original_matrix[i_arr, j_arr]
            synthetic_vals = synthetic_matrix[i_arr, j_arr]
            score_vals = score_matrix[i_arr, j_arr]
            f1_idx, f2_idx = i_arr, j_arr

        # Determine metric labels vectorized
        categorical_set = np.array(self.categorical_indices, dtype=int)
        # Fast path when no categorical indices
        if categorical_set.size == 0:
            metrics = np.full(i_arr.shape[0], "Spearman_Correlation", dtype=object)
        else:
            is_cat = np.isin(f1_idx, categorical_set) | np.isin(f2_idx, categorical_set)
            metrics = np.where(is_cat, "CramersV_Correlation", "Spearman_Correlation")

        # Build DataFrame
        col_names = np.array(self.all_columns, dtype=object)
        df = pd.DataFrame({
            "Feature_1": col_names[f1_idx],
            "Feature_2": col_names[f2_idx],
            "Metrics": metrics,
            "Original_Correlation": original_vals,
            "Synthetic_Correlation": synthetic_vals,
            "Score": score_vals,
        })

        return df
        
    @staticmethod
    def summarize(results: pd.DataFrame):
        """
        Summarize pairwise similarity scores by metric type.

        Args:
            results (pd.DataFrame): DataFrame containing pairwise association results.

        Returns:
            pd.DataFrame: Summary statistics (count, mean, std, min, max, etc.) grouped by metric type.

        Raises:
            Exception: If summary calculation fails.
        """
        try:
            print("\nSummary by Metric Type:")
            summary = results.groupby('Metrics')['Score'].describe()
            return summary
        except Exception as e:
            raise Exception(f"Error in summarize: {e}")

    @staticmethod
    def plot_column_score_histogram(results: np.ndarray, data_name: str = "", bins: int = 50):
        """
        Plot a histogram of column shape scores for a set of features.

        Args:
            results (np.array): Numpy array containing at least a 'Score' column with numerical values.
            data_name (str): Optional label for the data (for title).
            bins (int): Number of bins for the histogram.

        Returns:
            matplotlib.figure.Figure: Figure object for saving or further manipulation.

        Raises:
            KeyError: If the 'Score' column is not present in the DataFrame.
            TypeError: If results is not a pandas DataFrame.
        """
        if not isinstance(results,np.ndarray):
            raise TypeError("results must be a Numpy array.")
        # if 'Score' not in results.columns:
        #     raise KeyError("The 'Score' column must be present in the results DataFrame.")

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10, 6))
        results_no_nan = results[~np.isnan(results)]
        # Plot histogram only (no KDE)
        n, bins_, patches = ax.hist(
            results_no_nan,
            bins=bins,
            color='#4682B4',
            alpha=0.75,
            edgecolor='white',
            linewidth=1.2
        )

        # Add vertical lines for key statistics
        mean_score = np.mean(results_no_nan)
        median_score = np.median(results_no_nan)
        ax.axvline(mean_score, color='green', linestyle='--', linewidth=2, label=f'Mean: {mean_score:.2f}')
        ax.axvline(median_score, color='purple', linestyle='-.', linewidth=2, label=f'Median: {median_score:.2f}')

        # Customize ticks and grid
        ax.set_xticks(np.linspace(0, 1, 11))
        ax.tick_params(axis='x', labelsize=12)
        ax.tick_params(axis='y', labelsize=12)
        ax.grid(axis='y', alpha=0.3)

        # Add labels and title with font size and weight
        ax.set_xlabel('Score', fontsize=14, fontweight='bold')
        ax.set_ylabel('Number of Features', fontsize=14, fontweight='bold')
        ax.set_title(f'Distribution of PairWise Scores {data_name}', fontsize=16, fontweight='bold', pad=20)

        # Add legend
        ax.legend(fontsize=12, frameon=True)

        # Add annotation for total features
        ax.annotate(
            f"Total associations: {results_no_nan.shape[0]}",
            xy=(0.01, 0.05), xycoords='axes fraction',
            ha='left', va='bottom', fontsize=12, color='gray'
        )

        plt.tight_layout()
        return fig
    @monitor_resources
    def get_cross_group_associations(
        self,
        group_1_features: List[str],
        group_2_features: List[str],
        score_matrix: Optional[np.ndarray] = None,
        original_matrix: Optional[np.ndarray] = None,
        synthetic_matrix: Optional[np.ndarray] = None,
        condensed: bool = True,
    ) -> pd.DataFrame:
        """
        Calculate bivariate scores ONLY between two groups of features (e.g., clinical vs transcriptomics).
        
        Args:
            group_1_features (List[str]): List of feature names in first group (e.g., clinical).
            group_2_features (List[str]): List of feature names in second group (e.g., transcriptomics).
            score_matrix (Optional[np.ndarray]): Score matrix (condensed or square).
            original_matrix (Optional[np.ndarray]): Original correlation matrix.
            synthetic_matrix (Optional[np.ndarray]): Synthetic correlation matrix.
            condensed (bool): Whether matrices are in condensed form.
        
        Returns:
            pd.DataFrame: DataFrame with cross-group associations only.
            
        Raises:
            ValueError: If any feature name is not found in the data.
        """
        # Validate feature names
        missing_g1 = set(group_1_features) - set(self.all_columns)
        missing_g2 = set(group_2_features) - set(self.all_columns)
        
        if missing_g1:
            raise ValueError(f"Features not found in group 1: {missing_g1}")
        if missing_g2:
            raise ValueError(f"Features not found in group 2: {missing_g2}")
        
        # Check for overlap
        overlap = set(group_1_features) & set(group_2_features)
        if overlap:
            raise ValueError(f"Features cannot be in both groups: {overlap}")
        
        # Generate all cross-group pairs (Cartesian product)
        feature_pairs = [
            (f1, f2) 
            for f1 in group_1_features 
            for f2 in group_2_features
        ]
        
        if self.verbose:
            print(f"Computing {len(feature_pairs)} cross-group associations:")
            print(f"  Group 1 ({len(group_1_features)} features): {group_1_features[:3]}...")
            print(f"  Group 2 ({len(group_2_features)} features): {group_2_features[:3]}...")
        
        # Use existing method to compute associations
        results_df = self.get_multiple_associations(
            feature_pairs=feature_pairs,
            score_matrix=score_matrix,
            original_matrix=original_matrix,
            synthetic_matrix=synthetic_matrix,
            condensed=condensed
        )
        
        if self.verbose:
            print(f"\nCross-group association summary:")
            print(f"  Total pairs: {len(results_df)}")
            print(f"  Mean score: {results_df['Score'].mean():.4f}")
            print(f"  Median score: {results_df['Score'].median():.4f}")
        
        return results_df