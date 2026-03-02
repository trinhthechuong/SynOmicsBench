import json
import sys
import os
import logging
import pandas as pd
import numpy as np
from numba import njit, prange
sys.path.append("../../")
from typing import List, Optional
from sklearn.preprocessing import LabelEncoder
from SynOmics.processing.preprocessing import DataProcessor 
from SynOmics.processing.postprocessing import post_masking


def check_column_consistency(
    origin_data: pd.DataFrame, synthetic_data: pd.DataFrame
) -> bool:
    """
    Check if columns and their data types match between the original and synthetic DataFrames.

    Args:
        origin_data (pd.DataFrame): The original DataFrame.
        synthetic_data (pd.DataFrame): The synthetic DataFrame to compare.

    Returns:
        bool: True if both column names and data types match, False otherwise.

    Raises:
        None
    """
    # Check columns
    check_columns = False
    orig_cols = set(origin_data.columns)
    syn_cols = set(synthetic_data.columns)
    if orig_cols != syn_cols:
        check_columns = False
    else:
        # print("Column names match.")
        check_columns = True

    # Check column data types (for matching columns)
    check_type = False
    common_cols = orig_cols & syn_cols
    mismatches = []
    for col in common_cols:
        if origin_data[col].dtype != synthetic_data[col].dtype:
            mismatches.append((col, origin_data[col].dtype, synthetic_data[col].dtype))
    if mismatches:
        check_type = False
    else:
        check_type = True
    return all([check_columns, check_type])




class DataProcessValidation(DataProcessor):
    """
    Preprocessing pipeline for preparing tabular data for validation, including encoding, scaling, and imputation.

    Args:
        data (pd.DataFrame): Input data to preprocess.
        target_col (str): Name of the target column.
        output_dir (str): Directory for outputs. Defaults to ".".
        ordinal_cat_columns (Optional[List[str]]): List of ordinal categorical column names.
        dummy_cat_columns (Optional[List[str]]): List of dummy categorical column names.
        numerical_columns (Optional[List[str]]): List of numerical column names.
        scaler (str): Which scaler to use for numerical columns. Defaults to "minmax".
        n_neighbors (int): Number of neighbors for KNN imputation. Defaults to 5.

    Raises:
        ValueError: If the target column is not found in the input data.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        metadata: dict = None, 
        scaler: str = "minmax",
        n_neighbors: int = 5,
        **kwargs,
    ):
        """
        Initialize the PreprocessingForValidation class.

        Args:
            data (pd.DataFrame): Input data to preprocess.
            metadata (dict) : Metadata
            scaler (str): Which scaler to use for numerical columns. Defaults to "minmax".
            n_neighbors (int): Number of neighbors for KNN imputation. Defaults to 5.

        Raises:
            ValueError: If the target column is not found in the input data.
        """
        self.data = data
        self.ordinal_cat_columns = None 
        self.dummy_cat_columns = None
        self.numerical_columns = None
        self.scaler = scaler
        self.n_neighbors = n_neighbors
        

    def fit(self) -> pd.DataFrame:
        """
        Preprocess the data by encoding categorical features, normalizing numerical features,
        imputing missing values, and encoding the target variable.

        Returns:
            pd.DataFrame: The preprocessed data with transformed features and target column.

        Raises:
            ValueError: If required columns are missing or preprocessing fails.
            RuntimeError: If an unexpected error occurs during preprocessing.
        """
        try:
            preprocessed_parts = []

            for col_list in [
                self.ordinal_cat_columns,
                self.dummy_cat_columns,
                self.numerical_columns,
            ]:
                if col_list and self.target_col in col_list:
                    col_list.remove(self.target_col)

            y = pd.DataFrame(self.data[self.target_col])
            le = LabelEncoder()
            transformed_y = pd.DataFrame(
                le.fit_transform(y), index=y.index, columns=[self.target_col]
            )

            if self.ordinal_cat_columns:
                ordinal_data = self.data[self.ordinal_cat_columns]
                ordinal_encoded = super().encode_ordinal_cat_features(ordinal_data)
                preprocessed_parts.append(ordinal_encoded)

            if self.dummy_cat_columns:
                dummy_data = self.data[self.dummy_cat_columns]
                dummy_encoded = super().encode_dummy_cat_features(dummy_data)
                preprocessed_parts.append(dummy_encoded)
            # Normalize numerical columns
            if self.numerical_columns:
                numerical_data = self.data[self.numerical_columns]
                numerical_normalized = super().standardization(
                    numerical_data, scaler=self.scaler
                )
                preprocessed_parts.append(numerical_normalized)

            if not preprocessed_parts:
                raise ValueError("No columns specified for processing")

            data_preprocessed = pd.concat(preprocessed_parts, axis=1)

            # Imputation
            data_imputed = super().knn_imputer(
                data_preprocessed,
                dummy_cat_columns=self.dummy_cat_columns,
                ordinal_cat_columns=self.ordinal_cat_columns,
                n_neighbors=self.n_neighbors,
                add_indicators = False
            )
            data_preprocessed = pd.concat([transformed_y, data_imputed], axis=1)
            return data_preprocessed

        except KeyError as ke:
            raise ValueError(
                f"KeyError in class '{self.__class__.__name__}', method 'fit': {ke}"
            )
        except ValueError as ve:
            raise ValueError(
                f"ValueError in class '{self.__class__.__name__}', method 'fit': {ve}"
            )
        except Exception as e:
            raise RuntimeError(
                f"Error in class '{self.__class__.__name__}', method 'fit': {str(e)}"
            )


def np_encoder(obj):
    """
    Convert NumPy data types to native Python types for JSON serialization.

    Args:
        obj: The object to be encoded, potentially a NumPy scalar or array.

    Returns:
        int, float, bool, list: The object converted to a native Python type suitable for JSON serialization.

    Raises:
        TypeError: If the object type is not supported for conversion.
    """
    import numpy as np

    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_, np.bool8)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")

