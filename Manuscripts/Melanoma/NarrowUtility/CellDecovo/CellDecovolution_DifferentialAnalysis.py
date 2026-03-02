"""Differential analysis module for cell deconvolution results."""

import pandas as pd
import numpy as np
from scipy. stats import ranksums
from statsmodels.stats.multitest import multipletests
from typing import Dict, List, Tuple, Optional, Union


def differential_deconvolution_analysis(
    deconvolution_result: pd.DataFrame,
    metadata: pd.DataFrame,
    group_column: str,
    comparison_groups: Dict[str, List[str]],
    cell_type_columns: Optional[List[str]] = None,
    sample_id_column: str = "Mixture",
    normalize:  bool = True,
    alpha:  float = 0.05,
    correction_method: str = "fdr_bh"
) -> pd.DataFrame:
    """
    Perform differential analysis on cell deconvolution results between groups.
    
    Compares cell type proportions between two groups using Wilcoxon rank-sum test
    and applies multiple testing correction. 
    
    Args:
        deconvolution_result (pd.DataFrame): Cell deconvolution output containing sample IDs and cell type proportions. 
        metadata (pd.DataFrame): Sample metadata with group annotations.
        group_column (str): Column name in metadata defining sample groups.
        comparison_groups (Dict[str, List[str]]): Dictionary with 'group1' and 'group2' keys, 
            each containing list of group values to compare (e.g., {'group1': ['Desert', 'Excluded'], 'group2': ['Infiltrated']}).
        cell_type_columns (Optional[List[str]]): List of column names representing cell types.  
            If None, auto-detects numeric columns excluding sample_id_column.
        sample_id_column (str): Column name for sample identifiers in deconvolution_result.
        normalize (bool): Whether to normalize cell proportions to sum to 100 per sample.
        alpha (float): Significance level for FDR correction.
        correction_method (str): Multiple testing correction method ('fdr_bh', 'bonferroni', etc.).
    
    Returns:
        pd.DataFrame: Results table with columns:
            - Cell Type:  Cell type name
            - p_value: Raw p-value from Wilcoxon rank-sum test
            - q_value:  FDR-corrected q-value
            - Log2FC: Log2 fold change (group1 / group2)
            - Mean_Group1: Mean proportion in group1
            - Mean_Group2: Mean proportion in group2
            - -log10_q_value: -log10 transformed q-value
            - Rank_score: Signed -log10(q-value) (positive if group1 > group2)
            - Significant: Boolean indicating if q_value < alpha
    
    Raises:
        ValueError: If sample_id_column not in deconvolution_result.
        ValueError: If group_column not in metadata.
        ValueError: If comparison_groups does not have 'group1' and 'group2' keys. 
        ValueError: If no samples found for specified groups.
    """
    # Input validation
    if sample_id_column not in deconvolution_result.columns:
        raise ValueError(f"'{sample_id_column}' not found in deconvolution_result columns.")
    
    if group_column not in metadata.columns:
        raise ValueError(f"'{group_column}' not found in metadata columns.")
    
    if not isinstance(comparison_groups, dict) or 'group1' not in comparison_groups or 'group2' not in comparison_groups:
        raise ValueError("comparison_groups must be a dict with 'group1' and 'group2' keys.")
    
    # Extract cell type columns
    if cell_type_columns is None: 
        cell_type_columns = [
            col for col in deconvolution_result.columns 
            if col != sample_id_column and pd.api.types.is_numeric_dtype(deconvolution_result[col])
        ]
    
    if len(cell_type_columns) == 0:
        raise ValueError("No cell type columns found in deconvolution_result.")
    
    # Extract cell proportions
    cell_proportions = deconvolution_result[[sample_id_column] + cell_type_columns]. copy()
    
    # Normalize proportions if requested
    if normalize:
        normalized_props = cell_proportions[cell_type_columns].copy()
        for i in range(normalized_props.shape[0]):
            row_sum = normalized_props.iloc[i, :].sum()
            if row_sum > 0:
                normalized_props.iloc[i, :] = (normalized_props.iloc[i, :] / row_sum) * 100
            else:
                normalized_props. iloc[i, :] = 0
        cell_proportions[cell_type_columns] = normalized_props
    
    # Merge with metadata
    if 'Patient_ID' in metadata.columns:
        sample_col = 'Patient_ID'
    else:
        sample_col = metadata. columns[0]
    
    merged_data = cell_proportions.merge(
        metadata[[sample_col, group_column]], 
        left_on=sample_id_column, 
        right_on=sample_col, 
        how='inner'
    )
    
    # Get sample IDs for each group
    group1_samples = merged_data[
        merged_data[group_column]. isin(comparison_groups['group1'])
    ][sample_id_column].values. tolist()
    
    group2_samples = merged_data[
        merged_data[group_column].isin(comparison_groups['group2'])
    ][sample_id_column].values. tolist()
    
    if len(group1_samples) == 0 or len(group2_samples) == 0:
        raise ValueError(f"No samples found for specified groups.  Group1: {len(group1_samples)}, Group2: {len(group2_samples)}")
    
    # Perform statistical tests for each cell type
    results = _compute_differential_stats(
        cell_proportions=cell_proportions,
        cell_type_columns=cell_type_columns,
        group1_samples=group1_samples,
        group2_samples=group2_samples,
        sample_id_column=sample_id_column,
        alpha=alpha,
        correction_method=correction_method
    )
    
    return results


def _compute_differential_stats(
    cell_proportions: pd.DataFrame,
    cell_type_columns: List[str],
    group1_samples:  List[str],
    group2_samples: List[str],
    sample_id_column: str,
    alpha: float,
    correction_method: str
) -> pd.DataFrame:
    """
    Compute differential statistics for cell types between two groups.
    
    Args:
        cell_proportions (pd.DataFrame): Normalized cell proportions. 
        cell_type_columns (List[str]): List of cell type column names.
        group1_samples (List[str]): Sample IDs for group 1.
        group2_samples (List[str]): Sample IDs for group 2.
        sample_id_column (str): Column name for sample identifiers.
        alpha (float): Significance level for FDR correction.
        correction_method (str): Multiple testing correction method.
    
    Returns:
        pd.DataFrame: Statistical results for each cell type.
    """
    p_values = []
    log2fcs = []
    mean_group1_list = []
    mean_group2_list = []
    
    for cell_type in cell_type_columns:
        # Extract proportions for each group
        group1_proportions = cell_proportions[
            cell_proportions[sample_id_column]. isin(group1_samples)
        ][cell_type]. values
        
        group2_proportions = cell_proportions[
            cell_proportions[sample_id_column].isin(group2_samples)
        ][cell_type].values
        
        # Calculate means
        mean_group1 = np.mean(group1_proportions)
        mean_group2 = np.mean(group2_proportions)
        
        mean_group1_list.append(mean_group1)
        mean_group2_list.append(mean_group2)
        
        # Calculate log2 fold change (group1 / group2)
        log2fc = np.log2((mean_group1 + 1e-9) / (mean_group2 + 1e-9))
        log2fcs.append(log2fc)
        
        # Perform Wilcoxon rank-sum test
        try:
            stat, p = ranksums(group1_proportions, group2_proportions)
            p_values.append(p)
        except Exception as e:
            # Handle cases with constant values
            p_values.append(1.0)
    
    # Multiple testing correction
    rejected, q_values, _, _ = multipletests(p_values, alpha=alpha, method=correction_method)
    
    # Calculate -log10(q-value)
    neg_log10_q = [-np.log10(q) if q > 0 else np.inf for q in q_values]
    
    # Calculate directional rank score (signed by log2FC direction)
    rank_scores = [
        -np.log10(q) * np.sign(log2fc) if q > 0 else np.inf * np.sign(log2fc)
        for q, log2fc in zip(q_values, log2fcs)
    ]
    
    # Convert lists to numpy arrays for arithmetic operations
    mean_group1_array = np. array(mean_group1_list)
    mean_group2_array = np.array(mean_group2_list)
    diff_mean = mean_group1_array - mean_group2_array
    
    # Compile results
    results_df = pd.DataFrame({
        "Cell Type": cell_type_columns,
        "P_value":  p_values,
        "Q_value": q_values,
        "Log2FC": log2fcs,
        # "Mean_Group1": mean_group1_list,
        # "Mean_Group2": mean_group2_list,
        'Diff_Mean': diff_mean,
        "-log10_q_value": neg_log10_q,
        "Rank_Score": rank_scores,
        "Significant":  rejected
    })
    
    # Sort by significance
    results_df = results_df.sort_values("Q_value", ascending=True).reset_index(drop=True)
    
    return results_df


def batch_differential_deconvolution_analysis(
    deconvolution_results_dict: Dict[str, pd.DataFrame],
    metadata_dict: Dict[str, pd. DataFrame],
    group_column:  str,
    comparison_groups:  Dict[str, List[str]],
    **kwargs
) -> Dict[str, pd.DataFrame]:
    """
    Perform differential deconvolution analysis on multiple datasets. 
    
    Args:
        deconvolution_results_dict (Dict[str, pd.DataFrame]): Dictionary mapping dataset names to deconvolution results.
        metadata_dict (Dict[str, pd.DataFrame]): Dictionary mapping dataset names to metadata. 
        group_column (str): Column name in metadata defining sample groups. 
        comparison_groups (Dict[str, List[str]]): Group comparison specification.
        **kwargs: Additional arguments passed to differential_deconvolution_analysis.
    
    Returns:
        Dict[str, pd. DataFrame]: Dictionary mapping dataset names to differential analysis results.
    
    Raises:
        ValueError:  If dataset names don't match between deconvolution_results_dict and metadata_dict. 
    """
    if set(deconvolution_results_dict.keys()) != set(metadata_dict.keys()):
        raise ValueError("Dataset names must match between deconvolution_results_dict and metadata_dict.")
    
    results_dict = {}
    
    for dataset_name, deconv_result in deconvolution_results_dict.items():
        metadata = metadata_dict[dataset_name]
        
        result_df = differential_deconvolution_analysis(
            deconvolution_result=deconv_result,
            metadata=metadata,
            group_column=group_column,
            comparison_groups=comparison_groups,
            **kwargs
        )
        
        # Add dataset identifier
        result_df['Dataset'] = dataset_name
        results_dict[dataset_name] = result_df
    
    return results_dict


def combine_batch_results(results_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Combine multiple differential analysis results into a single DataFrame.
    
    Args:
        results_dict (Dict[str, pd.DataFrame]): Dictionary mapping dataset names to results DataFrames.
    
    Returns:
        pd.DataFrame: Combined results with all datasets.
    """
    combined_df = pd.concat(results_dict.values(), ignore_index=True)
    return combined_df
