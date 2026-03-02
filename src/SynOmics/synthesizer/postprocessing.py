import pandas as pd
import numpy as np
import json
import os
import uuid

def load_metadata(metadata_path: str) -> dict:
    """
    Load metadata from a JSON file.

    Args:
        metadata_path (str): Path to the metadata JSON file.

    Returns:
        dict: Loaded metadata.
    
    Raises:
        FileNotFoundError: If the metadata file does not exist.
        json.JSONDecodeError: If the metadata file is not a valid JSON.
    """
    try:    
        with open(metadata_path, 'r') as file:
            metadata = json.load(file)
        return metadata
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Metadata file not found: {e}. Please run classify_feature_type function in Preprocess module")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error decoding JSON from metadata file: {e}")

def _detect_discrete_columns(df: pd.DataFrame, metadata: dict) -> list:
    """
    Detect discrete (categorical) columns in a DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        list: List of column names that are discrete.
    """
    try:
        discrete_columns = list()
        for column, column_type in metadata.items():
            if column in df.columns:
                if column_type != "numerical":
                    discrete_columns.append(column)
        return discrete_columns
    except Exception as e:
        raise ValueError(f"Error detecting discrete columns: {e}")
    
def _detect_numerical_columns(df: pd.DataFrame, metadata: dict) -> list:
    """
    Detect numerical columns in a DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        list: List of column names that are numerical.
    """
    try:
        numerical_columns = []
        for key, value in metadata.items():
            if key in df.columns and value == "numerical":
                numerical_columns.append(key)
        return numerical_columns
    except Exception as e:
        raise ValueError(f"Error detecting numerical columns: {e}")
    
def _detect_min_max_values(data: pd.DataFrame, numerical_columns: list):
    """
    Store the minimum and maximum values of numerical columns in a DataFrame.

    Args:
        data (pd.DataFrame): Input DataFrame.
        numerical_columns (list): List of numerical column names.

    Returns:
        dict: Dictionary containing min and max values for each numerical column.
    """
    try:
        min_values = {}
        max_values = {}
        for col in numerical_columns:
            if col in data.columns:
                min_values[col] = data[col].min()
                max_values[col] = data[col].max()
            else:
                continue
        return min_values, max_values
    except Exception as e:
        raise ValueError(f"Error storing min/max values: {e}")
    
def _detect_rounding_digits(data: pd.DataFrame, numerical_columns: list) -> dict:
    """
    Detect the number of decimal places for each numerical column in a DataFrame.

    Args:
        data (pd.DataFrame): Input DataFrame.
        numerical_columns (list): List of numerical column names.

    Returns:
        dict: Dictionary containing the number of rounding digits for each numerical column.
    """
    try:
        rounding_digits = {}
        for col in numerical_columns:
            if col in data.columns:
                #Check float
                if pd.api.types.is_float_dtype(data[col]):
                    decimals = data[col].dropna().apply(
                        lambda x: len(str(x).split('.')[-1]) if '.' in str(x) else 0
                        )
                    rounding_digits[col] = decimals.max() if not decimals.empty else 0
                else:
                    rounding_digits[col] = 0
            else:
                continue
        return rounding_digits
    except Exception as e:
        raise ValueError(f"Error detecting rounding digits: {e}")
    
def apply_min_max(synthetic_data: pd.DataFrame, numerical_columns: list, min_values: dict, max_values: dict) -> pd.DataFrame:
    """
    Apply minimum and maximum constraints to numerical columns in synthetic data.
    Args:
        synthetic_data (pd.DataFrame): Synthetic data DataFrame.
        numerical_columns (list): List of numerical column names.
        min_values: Dictionary of min value of the corresponding column
        max_values:  Dictionary of max value of the corresponding column
    """
    for column in numerical_columns:
        if column in synthetic_data.columns:
            synthetic_data[column] = synthetic_data[column].clip(lower=min_values[column], upper=max_values[column])
        else:
            continue
    return synthetic_data

def apply_rounding(synthetic_data: pd.DataFrame, numerical_columns: list, rounding_digits : dict):
    """
    Round numerical columns to the sotred numer of decimal places
    Args:
        synthetic_data (pd.DataFrame): Synthetic data DataFrame.
        numerical_columns (list): List of numerical column names
        rounding_digits (dict): Dictionary containing the number of rounding digits for each numerical column.
    """
    for column in numerical_columns:
        if column in rounding_digits:
            synthetic_data[column] = synthetic_data[column].round(rounding_digits[column])
        else:
            continue
    return synthetic_data

def anonymize_ids(ids: list, 
                  synthetic_data: pd.DataFrame, 
                  output_path: str, 
                  mapping_file="anonymized_ids.json") -> pd.DataFrame:
    """
    Anonymize a list of IDs using random UUIDs and save the mapping.

    Args:
        ids (list or pd.Series): List of original IDs to anonymize.
        synthetic_data (pd.DataFrame): synthetic data
        output_path (str): Directory to save the ID mapping.
        mapping_file (str): Filename for the mapping JSON. Defaults to 'anonymized_ids.json'.

    Returns:
        pd.DataFrame: synthetic data with anonymized IDs
    """
    mapping_path = os.path.join(output_path, mapping_file)
    id_mapping = {}

    # Load existing mapping if it exists
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r') as f:
            id_mapping = json.load(f)

    anonymized_ids = []
    for id_value in ids:
        id_str = str(id_value)
        if id_str not in id_mapping:
            # Generate random UUID
            id_mapping[id_str] = str(uuid.uuid4())
        anonymized_ids.append(id_mapping[id_str])

    # Save updated mapping
    with open(mapping_path, 'w') as f:
        json.dump(id_mapping, f, indent=4)

    synthetic_data_anonymized = synthetic_data.copy()
    synthetic_data_anonymized.insert(0, 'Patient_ID', anonymized_ids)
    return synthetic_data_anonymized

def post_masking(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    try:
        # Determine missingindicator
        missingindicator_cols = [col for col in df.columns if col.startswith("missingindicator_")]
        if not missingindicator_cols:
            return df  # No missingindicator columns to process
        else:
        # Extract features from missingindicator
            feature_map = {}
            for col in missingindicator_cols:
                feature = col.replace("missingindicator_", "")
                feature_map.setdefault(feature, []).append(col)
            # Remove missingindicator columns and set related columns to np.nan
            # Iterate over each feature and its corresponding indicator columns
            for feature, indicator_cols in feature_map.items():
                # Find rows where any of the indicator columns is 1
                indicator_any = df[indicator_cols].any(axis=1)
                # Find all columns related to the feature
                related_cols = [col for col in df.columns if col.startswith(feature) and not col.startswith("missingindicator_")]
                # For those rows, set the related columns to np.nan
                df.loc[indicator_any, related_cols] = np.nan
            # Drop the missingindicator columns
            df = df.drop(columns=missingindicator_cols)
            return df
    except Exception as e:
        raise ValueError(f"Error in masking in post processing: {e}")


# def mask_value(data: pd.DataFrame, missing_indicators: list) -> pd.DataFrame:
#     try:
#         masked_data = data.copy()
#         #Check sublist:
#         if all(indicator in data.columns for indicator in missing_indicators): 
#             target_cols = [col.replace('missingindicator_', '') for col in missing_indicators]
#             for indicator, target in zip(missing_indicators, target_cols):
#                 masked_data.loc[masked_data[indicator] == 1, target] = np.nan
#             masked_data = masked_data.drop(columns = missing_indicators)
#             return masked_data
#         else:
#             raise ValueError("Some missing indicators are not the columns")
#     except Exception as e:
#         raise ValueError(f"Error in masking in post processing: {e}"