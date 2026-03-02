import pandas as pd
from tqdm import tqdm
import json
import numpy as np
import matplotlib.pyplot as plt
def check_duplicates(data: pd.DataFrame):
        try:
            print("Grouping genes with identical expression values...")
            # Transpose to check duplicates across genes
            genes_duplicated = data.T[data.T.duplicated(keep=False)].T
            if genes_duplicated.empty:
                print("No duplicate genes found")
                return {}, {}

            # Map each gene to its expression values
            gene_values = {col: vals.tolist() for col, vals in genes_duplicated.items()}
            duplicated_genes_dict = {col: [] for col in genes_duplicated.columns}
            mapped_genes_dict = duplicated_genes_dict.copy()

            # Group duplicates by expression values
            seen_values = set()
            for column in tqdm(genes_duplicated.columns, desc="Processing duplicates"):
                values = tuple(gene_values[column])  # Use tuple for hashability
                if values in seen_values:
                    continue
                seen_values.add(values)
                duplicates = [col for col, vals in gene_values.items() if vals == gene_values[column]]
                for dup in duplicates:
                    duplicated_genes_dict[dup] = duplicates

            # Save results
            with open("duplicated_genes_dict.json", "w") as f:
                json.dump(duplicated_genes_dict, f) 
            return duplicated_genes_dict
        except Exception as e:
            raise ValueError(f"Duplicate check failed: {e}")



def plot_top_features_plateau(top_features, save_path=None):
    """
    Plot the number of high-correlation links for top features to identify a plateau, and optionally save the figure.

    Args:
        top_features (list): List of tuples (feature_name, high_corr_count), sorted descendingly.
        save_path (str, optional): If provided, the plot will be saved to this path.

    Returns:
        None

    Example:
        top_features = [('A', 8), ('B', 7), ('C', 7), ('D', 5)]
        plot_top_features_plateau(top_features, save_path="plateau_plot.png")

    """
    feature_names = [f[0] for f in top_features]
    high_corr_counts = [f[1] for f in top_features]

    plt.figure(figsize=(8, 4))
    plt.plot(range(1, len(feature_names)+1), high_corr_counts)
    # plt.xticks(range(1, len(feature_names)+1), feature_names, rotation=45, ha='right')
    plt.xlabel('Feature (sorted by high correlation count)')
    plt.ylabel('Number of high-correlation features')
    plt.title('Top Features by High Correlation Count\n(Plateau Identification)')
    plt.tight_layout()
    plt.grid(True, linestyle='--', alpha=0.5)
    if save_path is not None:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()

def find_elbow_point(counts: list) -> int:
    """
    Find the elbow point (plateau) in a sorted list of counts using the "distance to line" method.

    Args:
        counts (list): A list of integers, sorted in descending order.

    Returns:
        int: Index of the elbow point in the list.

    Raises:
        ValueError: If counts is empty or not sorted in descending order.
    """
    if len(counts) == 0:
        raise ValueError("counts list must not be empty.")
    if any(counts[i] < counts[i+1] for i in range(len(counts) - 1)):
        raise ValueError("counts list must be sorted in descending order.")

    n_points = len(counts)
    all_points = np.array([range(n_points), counts]).T

    line_vec = all_points[-1] - all_points[0]
    line_vec_norm = line_vec / np.linalg.norm(line_vec)

    vec_from_first = all_points - all_points[0]
    scalar_product = np.dot(vec_from_first, line_vec_norm)
    proj = np.outer(scalar_product, line_vec_norm)
    vec_to_line = vec_from_first - proj
    dist_to_line = np.linalg.norm(vec_to_line, axis=1)

    elbow_idx = np.argmax(dist_to_line)
    return elbow_idx

def top_high_correlation_features(
    corr_matrix: np.ndarray,
    feature_names: list,
    threshold: float,
    n_tops: int = None
) -> list:
    """
    Identify features with the highest number of correlations above a specified threshold.
    If n_tops is given, return up to n_tops features with the largest counts. 
    If n_tops is None, use the elbow rule and return features with counts strictly greater than the elbow value.

    Args:
        corr_matrix (np.ndarray): A square (n x n) numpy array representing feature-by-feature correlations.
        feature_names (list): List of feature names (strings), length must match the dimensions of corr_matrix.
        threshold (float): The correlation threshold (e.g., 0.5 for 50%) to consider as "high correlation".
        n_tops (int, optional): The maximum number of top features to return. If None, the elbow rule is used.

    Returns:
        list: List of tuples (feature_name, high_corr_count) for the top features, sorted descendingly by count.

    Raises:
        ValueError: If corr_matrix is not a square numpy array.
        ValueError: If the length of feature_names does not match the matrix size.
        ValueError: If threshold is not between 0 and 1.
        ValueError: If n_tops is not None and is not a positive integer.
    """
    if not isinstance(corr_matrix, np.ndarray) or corr_matrix.ndim != 2 or corr_matrix.shape[0] != corr_matrix.shape[1]:
        raise ValueError("corr_matrix must be a square numpy array (n x n).")
    if len(feature_names) != corr_matrix.shape[0]:
        raise ValueError("feature_names length must match corr_matrix dimensions.")
    if not (0 <= threshold <= 1):
        raise ValueError("threshold must be between 0 and 1.")
    if n_tops is not None and (not isinstance(n_tops, int) or n_tops <= 0):
        raise ValueError("n_tops must be a positive integer.")

    corr_matrix = corr_matrix.copy()
    np.fill_diagonal(corr_matrix, 0)

    high_corr_counts = np.sum(np.abs(corr_matrix) <= threshold, axis=1)
    feature_count_pairs = list(zip(feature_names, high_corr_counts))
    feature_count_pairs.sort(key=lambda x: (-x[1], x[0]))

    if n_tops is not None:
        # Trả về đúng n_tops feature lớn nhất, bất kể elbow
        return feature_count_pairs[:n_tops]
    else:
        # Dùng elbow rule, lấy các feature có count > elbow_count
        counts_sorted = [x[1] for x in feature_count_pairs]
        elbow_idx = find_elbow_point(counts_sorted)
        elbow_count = counts_sorted[elbow_idx]
        top_features = [x for x in feature_count_pairs if x[1] > elbow_count]
        return top_features

def construct_predictor_matrix(
    corr_matrix: np.ndarray,
    feature_names: list,
    threshold: float,
    categorical_features: list,
    top_features: list,
    numerical_features: list
) -> pd.DataFrame:
    """
    Construct a predictor matrix for synthetic data modeling.

    For each target feature (row), predictors are assigned as follows:
    - If the absolute correlation with the target is below the threshold, set as a predictor (value 1).
    - All categorical features are always predictors for every feature (except themselves).
    - Only numerical features in the top_features list are also always predictors for every feature (except themselves).
    - A feature cannot be its own predictor (diagonal is 0).

    Args:
        corr_matrix (np.ndarray): Square (n x n) array of absolute correlations between features.
        feature_names (list): List of feature names, length must match corr_matrix dimensions.
        threshold (float): Threshold for low correlation; under threshold means feature is used as predictor.
        categorical_features (list): List of categorical feature names to always use as predictors.
        top_features (list): List of top feature names to always use as predictors (only numerical features will be used).
        numerical_features (list): List of numerical feature names to intersect with top_features for always predictors.

    Returns:
        pd.DataFrame: Predictor matrix (features x features) with 1 for predictors, 0 otherwise.

    Raises:
        ValueError: If corr_matrix is not square or does not match feature_names length.
        ValueError: If threshold is not between 0 and 1.
    """
    if not isinstance(corr_matrix, np.ndarray) or corr_matrix.ndim != 2 or corr_matrix.shape[0] != corr_matrix.shape[1]:
        raise ValueError("corr_matrix must be a square numpy array (n x n).")
    if len(feature_names) != corr_matrix.shape[0]:
        raise ValueError("feature_names length must match corr_matrix dimensions.")
    if not (0 <= threshold <= 1):
        raise ValueError("threshold must be between 0 and 1.")

    n = len(feature_names)
    pred_mat = np.zeros((n, n), dtype=int)
    feature_idx = {f: i for i, f in enumerate(feature_names)}

    # Set predictors based on correlation threshold
    for i in range(n):
        for j in range(n):
            if i != j and abs(corr_matrix[i, j]) <= threshold:
                pred_mat[i, j] = 1

    # Always include categorical features as predictors for all features (except themselves)
    for pred in categorical_features:
        if pred in feature_idx:
            j = feature_idx[pred]
            for i in range(n):
                if i != j:
                    pred_mat[i, j] = 1

    # Only include numerical features in top_features as predictors for all features (except themselves)
    numerical_top_features = [f for f in top_features if f in numerical_features]
    for pred in numerical_top_features:
        if pred in feature_idx:
            j = feature_idx[pred]
            for i in range(n):
                if i != j:
                    pred_mat[i, j] = 1

    # Diagonal must be zero (no self-prediction)
    np.fill_diagonal(pred_mat, 0)

    return pd.DataFrame(pred_mat, index=feature_names, columns=feature_names)

