from sdmetrics.single_column import MissingValueSimilarity
import pandas as pd

def MissingValue_Similarity(
    origin_data: pd.DataFrame, synthetic_data: pd.DataFrame, missing_indicators: list
):
    """
    Compute missing value similarity scores for each target column.

    Args:
        origin_data (pd.DataFrame): Original data.
        synthetic_data (pd.DataFrame): Synthetic data.
        missing_indicators (list): List of column names with missing indicators.

    Returns:
        dict: Mapping from column name to similarity score.

    Raises:
        Exception: If computation fails for any column.
    """
    MissingValue_dict = {}
    target_cols = [col.replace("missingindicator_", "") for col in missing_indicators]
    for target_col in target_cols:
        try:
            simi_score = MissingValueSimilarity.compute(
                real_data=origin_data[target_col], synthetic_data=synthetic_data[target_col]
            )
            MissingValue_dict[target_col] = simi_score
        except Exception as e:
            # Continue but note error in dict
            MissingValue_dict[target_col] = None
    return MissingValue_dict