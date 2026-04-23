import pandas as pd
import numpy as np
from typing import Optional, List
import warnings
import json
import os

class MetaData:
    def __init__(self):
        pass

    @staticmethod
    def classify_features_types(
        data: pd.DataFrame,
        threshold_unique_values: int,
        ordinal_features: Optional[List] = None,
        binary_values: set = {0, 1}
    ) -> (List[str], List[str]):
        """
        Classify columns into dummy categorical and numerical features.

        Args:
            data (pd.DataFrame): Input dataframe.
            threshold_unique_values (int): Threshold for unique values to consider as categorical.
            ordinal_features (Optional[List]): List of columns to treat as ordinal (will be excluded from both outputs).
            binary_values (set): Set of values to consider as binary for dummy categorical.

        Returns:
            tuple: (dummy_categorical_columns, numerical_columns)
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            if ordinal_features is None:
                ordinal_features = []
            # Identify dummy categorical features:
            dummy_cat_columns = []
            num_columns = []
            for col in data.columns:
                col_data = data[col].dropna()
                unique_vals = set(col_data.unique())
                if pd.api.types.is_object_dtype(data[col]) or isinstance(data[col].dtype, pd.CategoricalDtype):
                    dummy_cat_columns.append(col)
                elif unique_vals <= binary_values and len(unique_vals) > 0:
                    dummy_cat_columns.append(col)
                elif len(unique_vals) <= threshold_unique_values:
                    dummy_cat_columns.append(col)
                elif pd.api.types.is_numeric_dtype(data[col]):
                    # Prioritize dtype: all numeric columns are NUMERICAL, even with low unique values
                    num_columns.append(col)
            # Remove ordinal features from outputs if provided
            dummy_cat_columns = list(set(dummy_cat_columns) - set(ordinal_features))
            num_columns = list(set(num_columns) - set(ordinal_features))
            return dummy_cat_columns, num_columns
        except Exception as e:
            raise ValueError(f"Error classifying feature types: {e}")

    @staticmethod
    def get_metadata(
        data: pd.DataFrame,
        threshold_unique_values: int,
        id_columns: Optional[List] = None,
        ordinal_features: Optional[List] = None,
        transcriptomic_cols: Optional[List] = None,
        binary_values: set = {0, 1},
    ) -> dict[str, str]:
        """
        Extract column type metadata from a DataFrame and assign columns to corresponding types.

        Args:
            data (pd.DataFrame): DataFrame with features.
            threshold_unique_values (int): Threshold for unique values to consider as categorical.
            id_columns (Optional[List]): List of columns to ignore (e.g., sample IDs).
            ordinal_features (Optional[List]): List of columns to treat as ordinal.
            binary_values (set): Set of values to consider as binary.

        Returns:
            dict: Dictionary mapping each column to its feature type:
                'numerical', 'ordinal_categorical', 'dummy_categorical', 'missing_categorical', or 'unclassified'.

        Raises:
            ValueError: If classification fails.
        """
        if id_columns is not None:
            data = data.drop(id_columns, axis=1)
        features = data.columns.to_list()
        metadata_dict = {}
        dummy_cols, numerical_cols = MetaData.classify_features_types(
            data=data,
            threshold_unique_values=threshold_unique_values,
            ordinal_features=ordinal_features,
            binary_values=binary_values
        )
        if transcriptomic_cols is None:
            transcriptomic_cols = []
            
        for col in features:
            if col in transcriptomic_cols:
                metadata_dict[col] = "numerical"
                continue
                
            if ordinal_features and col in ordinal_features:
                metadata_dict[col] = "ordinal_categorical"
            elif col in dummy_cols:
                metadata_dict[col] = "dummy_categorical"
            elif col in numerical_cols:
                metadata_dict[col] = "numerical"
            elif col.startswith("missingindicator_"):
                metadata_dict[col] = "missing_categorical"
            else:
                metadata_dict[col] = "unclassified"
        if "unclassified" in metadata_dict.values():
            count_unclassified = list(metadata_dict.values()).count("unclassified")
            warnings.warn(
                f"There are {count_unclassified} unclassified features in the metadata. "
                "Consider reviewing your metadata or feature typing logic.",
                UserWarning
            )
            
        return metadata_dict

    @staticmethod
    def grouping_features_astype(data: pd.DataFrame, metadata: dict) -> dict:
        """
        Extract column type metadata from a JSON file and assign columns to corresponding types.
    
        Args:
            data (pd.DataFrame): DataFrame used to filter available columns.
            metadata (str): metadata dictionary.
    
    
        Returns:
            dict: Dictionary with keys 'numerical', 'ordinal_categorical', 'dummy_categorical', and
                'missing_categorical', mapping to lists of column names.
    
        Raises:
            FileNotFoundError: If the metadata file is not found.
            json.JSONDecodeError: If the metadata file is not a valid JSON.
        """

        # try:
        #     with open(metadata_path, "r") as f:
        #         metadata = json.load(f)
        # except FileNotFoundError as e:
        #     raise FileNotFoundError(f"Metadata file not found: {metadata_path}") from e
        # except json.JSONDecodeError as e:
        #     raise json.JSONDecodeError(
        #         f"Invalid JSON in metadata file: {metadata_path}", doc=e.doc, pos=e.pos
        #     )
    
        dummy_cat_cols = []
        ordinal_cat_cols = []
        num_cols = []
        missing_indicator_cols = []
        for k, v in metadata.items():
            if k in data.columns:
                if v == "numerical":
                    num_cols.append(k)
                elif v == "ordinal_categorical":
                    ordinal_cat_cols.append(k)
                elif v == "missing_categorical":
                    missing_indicator_cols.append(k)
                else:
                    dummy_cat_cols.append(k)
        return {
            "numerical": num_cols,
            "ordinal_categorical": ordinal_cat_cols,
            "dummy_categorical": dummy_cat_cols,
            "missing_categorical": missing_indicator_cols,
        }

    @staticmethod
    def metadata_as_SDV(data: pd.DataFrame, metadata: dict)->dict:
        """
        Extract column type metadata from a JSON file and assign columns to corresponding types follow SDV library format.
    
        Args:
            data (pd.DataFrame): DataFrame used to filter available columns.
            metadata (str): metadata dictionary.
    
    
        Returns:
            dict: Dictionary followed SDV format.
    
        Raises:
            FileNotFoundError: If the metadata file is not found.
            json.JSONDecodeError: If the metadata file is not a valid JSON.
        """
        metadata = MetaData.grouping_features_astype(data, metadata)
        # Build SDMetrics metadata dict
        metadata_sdmetrics = {'columns': {}}
        for col in metadata.get("numerical"):
            metadata_sdmetrics['columns'][col] = {'sdtype': 'numerical'}
        for col in metadata.get("ordinal_categorical"):
            metadata_sdmetrics['columns'][col] = {'sdtype': 'categorical'}  # or 'ordinal' if supported
        for col in  metadata.get("dummy_categorical"):
            metadata_sdmetrics['columns'][col] = {'sdtype': 'categorical'}
        for col in metadata.get("missing_categorical"):
            metadata_sdmetrics['columns'][col] = {'sdtype': 'categorical'}
        return metadata_sdmetrics

    @staticmethod
    def get_column_indices(data: pd.DataFrame, column_list: list) -> np.array:
        """
        Get indices of columns in a given list in a given dataframe.
    
        Args:
            data (pd.DataFrame): The DataFrame containing columns extracted indices.
            column_list (list): List of columns.
    
        Returns:
            np.array: Array containing the column indices.
    
        Raises:
            ValueError: If a specified column does not exist in the DataFrame.
        """
        column_df = data.columns.tolist()
        missing = [column for column in column_list if column not in column_df]
        if missing:
            raise ValueError(f"The following columns from column_list are not found in the DataFrame: {missing}")
        col_indices = []
        for col in column_list:
            col_indice = column_df.index(col)
            col_indices.append(col_indice)
        col_indices_array = np.array(col_indices, dtype=np.int64)
        return col_indices_array

    @staticmethod
    def save(metadata: dict, output_dir: str="", filename: str= "metadata"):
        json_dir = os.path.join(output_dir, f"{filename}.json")
        with open(json_dir, 'w') as file: 
            json.dump(metadata, file, indent=4)
            
    @staticmethod
    def load(metadata_dir: str) -> dict:
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
            with open(metadata_dir, 'r') as file:
                metadata = json.load(file)
            return metadata
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Metadata file not found: {e}. Please run get_metadata and save functions in MetaData module")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Error decoding JSON from metadata file: {e}")
                
                
            
                
                
                
        
        