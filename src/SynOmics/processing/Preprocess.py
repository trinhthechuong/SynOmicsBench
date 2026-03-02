import pandas as pd
import mygene
from sklearn.impute import KNNImputer
import numpy as np
from typing import Optional, List, Any
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.preprocessing import OrdinalEncoder
import logging
import os
import json
import warnings
warnings.filterwarnings("ignore")
# import sys
# sys.path.append("../")
from SynOmics.utils.monitoring import set_logger


class Preprocess:
    """A class to handle preprocessing tasks for clinical and transcriptome datasets.

    This class provides methods to clean and normalize data, handle missing values, encode categorical features,
    and merge clinical and transcriptome data into a single dataset for analysis.

    Attributes:
        scaler: The scaler object used for normalization tasks (e.g., StandardScaler).
        output_dir (str): Directory path for saving logs and metadata files.
        logger (logging.Logger): Logger instance for tracking operations and errors.
    """

    def __init__(self, output_dir: str, logger: str = ""):
        """Initialize the Preprocess class with an output directory and logging setup.

        Args:
            output_dir: Directory path where logs and metadata files will be saved.
            logger: Name of the logger

        Raises:
            OSError: If the output directory cannot be created or accessed.
        """
        self.scaler = None
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)  # Ensure output directory exists

        # Initialize logger with a unique name to avoid conflicts
        logger_name = f"{self.__class__.__name__}_{id(self)}"
        log_file_name = f"Preprocess_{logger}.log"
        self.logger = set_logger(logger_name, self.output_dir, log_file_name)

    def remove_duplications(self, data: pd.DataFrame, axis: int) -> pd.DataFrame:
        """Remove duplicated rows or columns from a DataFrame.

        Args:
            data: Input pandas DataFrame to process.
            axis: Axis along which to remove duplicates (0 for rows, 1 for columns).

        Returns:
            DataFrame with duplicated rows or columns removed.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If `axis` is not 0 or 1.
            RuntimeError: If an unexpected error occurs during duplicate removal.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        if axis not in [0, 1]:
            self.logger.error("Axis must be 0 (rows) or 1 (columns)")
            raise ValueError("Axis must be 0 (rows) or 1 (columns)")
        try:
            self.logger.debug(f"Removing duplicates along axis {axis}")
            if axis == 0:
                return data.drop_duplicates()
            elif axis == 1:
                return data.loc[:, ~data.columns.duplicated()]
        except Exception as e:
            self.logger.error(f"Error removing duplicates: {e}", exc_info=True)
            raise RuntimeError(f"Error removing duplicates: {e}")

    def remove_unknown_entities(self, data: pd.DataFrame, id_column: str) -> pd.DataFrame:
        """Remove rows with missing values in the specified ID column.

        Args:
            data: Input DataFrame to process.
            id_column: Column name to check for missing values.

        Returns:
            DataFrame with rows containing missing ID values removed.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            KeyError: If `id_column` is not in the DataFrame.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Data input must be a pandas DataFrame")
            raise TypeError("Data input must be a pandas DataFrame")
        if id_column not in data.columns:
            self.logger.error(f"ID column '{id_column}' not in DataFrame")
            raise KeyError(f"ID column '{id_column}' not in DataFrame")
        self.logger.debug(f"Removing rows with missing '{id_column}' values")
        return data.dropna(subset=[id_column])

    def remove_overmissing_entities(self, data: pd.DataFrame, threshold: float) -> pd.DataFrame:
        """
        Remove samples (rows) with missing values exceeding the specified threshold.

        Args:
            data (pd.DataFrame): Input DataFrame to process.
            threshold (float): Maximum allowed percentage of missing values per row (0-100).

        Returns:
            pd.DataFrame: DataFrame with over-missing samples removed.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If `threshold` is invalid or removal fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        if not 0 <= threshold <= 100:
            self.logger.error("Threshold must be between 0 and 100")
            raise ValueError("Threshold must be between 0 and 100")
        try:
            self.logger.debug(f"Removing samples with missing values > {threshold}%")
            # Calculate the percentage of missing values per row
            missing_percentage = data.isnull().mean(axis=1) * 100
            # Keep rows where missing percentage is <= threshold
            keep_rows = missing_percentage <= threshold
            self.logger.info(f"Dropping {len(data) - keep_rows.sum()} over-missing samples")
            return data[keep_rows].copy()
        except Exception as e:
            self.logger.error(f"Error removing over-missing samples: {e}", exc_info=True)
            raise ValueError(f"Error removing over-missing samples: {e}")
    
    def classify_features_types(
        self,
        data: pd.DataFrame,
        threshold_unique_values: int,
        ordinal_features: Optional[List] = None,
        binary_values: set = {0, 1}
    ) -> tuple:
        """Classify categorical (dummy and ordinal) and numerical columns in a DataFrame.

        Args:
            data: Input pandas DataFrame to classify.
            threshold_unique_values: Maximum unique values to classify a column as categorical.
            ordinal_features: Optional list of ordinal feature names.
            binary_values: Set of values identifying binary columns (default: {0, 1}).

        Returns:
            Tuple containing:
                - List of dummy categorical columns (including binary columns).
                - List of numerical columns.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If processing or JSON writing fails.
            Warning: If unclassified features are detected.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            self.logger.debug("Classifying feature types")
            dummy_cat_columns = [
                col
                for col in data.columns
                if not pd.api.types.is_numeric_dtype(data[col])
                or set(data[col].dropna().unique()) == binary_values
                or len(data[col].dropna().unique()) <= threshold_unique_values
            ]
            num_columns = [
                col
                for col in data.columns
                if pd.api.types.is_numeric_dtype(data[col])
                and set(data[col].dropna().unique()) != binary_values
                and len(data[col].dropna().unique()) > threshold_unique_values
            ]
            if ordinal_features is None:
                return dummy_cat_columns, num_columns
            else:
                dummy_cat_columns = list(set(dummy_cat_columns) - set(ordinal_features))
                num_columns = list(set(num_columns) - set(ordinal_features))
                return dummy_cat_columns, num_columns
        except Warning as w:
            raise  # Re-raise warning
        except OSError as e:
            self.logger.error(f"Failed to write features metadata: {e}", exc_info=True)
            raise ValueError(f"Failed to write features metadata: {e}")
        except Exception as e:
            self.logger.error(f"Error classifying feature types: {e}", exc_info=True)
            raise ValueError(f"Error classifying feature types: {e}")

    def find_missing_percent(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate the percentage of missing values for each column in the dataset.

        Args:
            data: Input DataFrame to analyze.

        Returns:
            DataFrame with columns 'ColumnName' and 'PercentMissing' showing missing percentages.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            RuntimeError: If calculation fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Data input must be a pandas DataFrame")
            raise TypeError("Data input must be a pandas DataFrame")
        try:
            self.logger.debug("Calculating missing value percentages")
            return (
                (data.isnull().sum() / len(data) * 100)
                .reset_index()
                .rename(columns={0: "PercentMissing", "index": "ColumnName"})
            )
        except Exception as e:
            self.logger.error(f"Error calculating missing percentages: {e}", exc_info=True)
            raise RuntimeError(f"Error calculating missing percentages: {e}")

    def remove_overmissing_features(self, data: pd.DataFrame, threshold: float) -> pd.DataFrame:
        """Remove columns with missing values exceeding the specified threshold.

        Args:
            data: Input DataFrame to process.
            threshold: Maximum allowed percentage of missing values (0-100).

        Returns:
            DataFrame with over-missing columns removed.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If `threshold` is invalid or removal fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        if not 0 <= threshold <= 100:
            self.logger.error("Threshold must be between 0 and 100")
            raise ValueError("Threshold must be between 0 and 100")
        try:
            self.logger.debug(f"Removing columns with missing values > {threshold}%")
            miss_df = self.find_missing_percent(data)
            drop_cols = miss_df[miss_df["PercentMissing"] > threshold]["ColumnName"].tolist()
            self.logger.info(f"Dropping {len(drop_cols)} over-missing columns: {drop_cols}")
            return data.drop(drop_cols, axis=1)
        except Exception as e:
            self.logger.error(f"Error removing over-missing columns: {e}", exc_info=True)
            raise ValueError(f"Error removing over-missing columns: {e}")

    def knn_imputer(
        self,
        data: pd.DataFrame,
        dummy_cat_columns: list,
        n_neighbors: int, 
        ordinal_cat_columns: Optional[List] = None,
        add_indicators: bool = True
    ) -> pd.DataFrame:
        """Impute missing values using the K-Nearest Neighbors (KNN) algorithm.

        Args:
            data: Input DataFrame to impute.
            dummy_cat_columns: List of dummy categorical column names.
            n_neighbors: Number of neighbors for imputation.
            ordinal_cat_columns: Optional list of ordinal categorical column names.
            add_indicators: Add indicator columns for Nan

        Returns:
            DataFrame with missing values imputed.

        Raises:
            TypeError: If `data` is not a pandas DataFrame or column lists are invalid.
            ValueError: If specified columns are not in the DataFrame or imputation fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        if not isinstance(dummy_cat_columns, list):
            self.logger.error("dummy_cat_columns must be a list")
            raise TypeError("dummy_cat_columns must be a list")
        ordinal_cat_columns = ordinal_cat_columns or []
        if not isinstance(ordinal_cat_columns, list):
            self.logger.error("ordinal_cat_columns must be a list")
            raise TypeError("ordinal_cat_columns must be a list")
        try:
            self.logger.debug(f"Starting KNN imputation with {n_neighbors} neighbors")
            dummy_cat_features_dict = {}
            nan_dummy_features = []
            # Create a dictionary to hold dummy categorical features
            for dummy_cat_feature in dummy_cat_columns:
                for column in data.columns:
                    if column.startswith(dummy_cat_feature):
                        dummy_cat_features_dict[dummy_cat_feature] = dummy_cat_features_dict.get(
                            dummy_cat_feature, []
                        ) + [column]
            # Check for NaN dummy columns and handle them
            NAN_SUFFIX = "_nan"
            for dummy_cat_feature, dummy_columns in dummy_cat_features_dict.items():
                for column in dummy_columns:
                    if column.endswith(NAN_SUFFIX):
                        nan_dummy_features.append(column)
            # Refill np.nan to dummy categorical features
            index_dict = {}
            for key, value in dummy_cat_features_dict.items():
                num_type_cat_feature = len(value) - 1
                index_dict[key] = []
                for row_i in data.index:
                    if np.array_equal(
                        data.loc[row_i, dummy_cat_features_dict[key]].values,
                        np.array([0] * num_type_cat_feature + [1]),
                    ):
                        data.loc[row_i, dummy_cat_features_dict[key]] = [
                            np.nan
                        ] * num_type_cat_feature + [1]
                        index_dict[key].append(row_i)
            #Remove NaN dummy columns from the DataFrame
            if len(nan_dummy_features) > 0:
                self.logger.debug(f"Dropping NaN dummy columns: {nan_dummy_features}")
                data = data.drop(nan_dummy_features, axis=1)
            #Use KNN imputer to fill missing values
            imputer = KNNImputer(n_neighbors=n_neighbors, weights="distance", add_indicator=add_indicators)
            data_imputed = pd.DataFrame(
                imputer.fit_transform(data), columns=imputer.get_feature_names_out(), index=data.index
            )
            # Post-process the imputed data
            data_imputed[ordinal_cat_columns] = data_imputed[ordinal_cat_columns].round()
            for key, value in index_dict.items():
                features = dummy_cat_features_dict[key][0:-1]
                argmax_index = np.argmax(
                    data_imputed.loc[value, features].values, axis=1
                )
                for i in range(len(value)):
                    data_imputed.loc[value[i], features] = [0] * len(features)
                    data_imputed.loc[value[i], features[argmax_index[i]]] = 1

            # Combine duplicate missing indicators for dummy variables
            indicator_cols = [col for col in data_imputed.columns if col.startswith("missingindicator_")]
            # Map: dummy feature -> list of indicator columns
            indicator_map = {}
            for col in indicator_cols:
                for dummy_cat_feature in dummy_cat_columns:
                    if col.startswith(f"missingindicator_{dummy_cat_feature}"):
                        indicator_map.setdefault(dummy_cat_feature, []).append(col)
            # For each dummy feature, keep only one indicator column (since all are identical)
            for dummy_cat_feature, cols in indicator_map.items():
                if len(cols) > 1:
                    # Keep the first column, drop the rest, and rename to standard name
                    combined_col = f"missingindicator_{dummy_cat_feature}"
                    data_imputed[combined_col] = data_imputed[cols[0]]
                    data_imputed.drop(columns=cols, inplace=True)
                elif len(cols) == 1:
                    # Rename to standard name if needed
                    col = cols[0]
                    combined_col = f"missingindicator_{dummy_cat_feature}"
                    if col != combined_col:
                        data_imputed.rename(columns={col: combined_col}, inplace=True)
            return data_imputed
        except Exception as e:
            self.logger.error(f"Error in KNN imputation: {e}", exc_info=True)
            raise ValueError(f"Error in KNN imputation: {e}")

    def encode_dummy_cat_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Perform dummy encoding on categorical features.

        Args:
            data: Input DataFrame containing categorical features.

        Returns:
            DataFrame with categorical features dummy-encoded.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If encoding fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            self.logger.info(f"Dummy encoding {data.shape[1]} features")
            cat_data_encoded = pd.get_dummies(
                data, dtype="int64", dummy_na=True, columns=data.columns
            )
            return cat_data_encoded
        except Exception as e:
            self.logger.error(f"Error encoding categorical features: {e}", exc_info=True)
            raise ValueError(f"Error encoding categorical features: {e}")

    def encode_ordinal_cat_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Perform ordinal encoding on ordinal categorical features.

        Args:
            data: Input DataFrame containing ordinal categorical features.

        Returns:
            DataFrame with ordinal categorical features encoded.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If encoding fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            self.logger.info(f"Ordinal encoding {data.shape[1]} features")
            self.oe = OrdinalEncoder()
            encoded_values = self.oe.fit_transform(data)
            df_ordinal_encoded = pd.DataFrame(encoded_values, columns=data.columns, index = data.index)
            return df_ordinal_encoded
        except Exception as e:
            self.logger.error(f"Error encoding ordinal categorical features: {e}", exc_info=True)
            raise ValueError(f"Error encoding ordinal categorical features: {e}")

    def standardization(self, data: pd.DataFrame, scaler: str) -> pd.DataFrame:
        """Normalize numerical features using the specified scaler.

        Args:
            data: Input DataFrame to normalize.
            scaler: Type of scaler to use ('standard', 'minmax', or 'robust').

        Returns:
            Normalized DataFrame.

        Raises:
            ValueError: If `scaler` is invalid or `data` is not a pandas DataFrame.
            RuntimeError: If normalization fails.
        """
        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
        }
        if scaler not in scalers:
            self.logger.error("Scaler must be 'standard', 'minmax', or 'robust'")
            raise ValueError("Scaler must be 'standard', 'minmax', or 'robust'")
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            self.logger.info(f"Using scaler: {scaler}")
            self.logger.info(f"Normalizing {data.shape[1]} numerical features")  # Fixed 'infor' typo
            self.scaler = scalers[scaler]
            return pd.DataFrame(
                self.scaler.fit_transform(data), columns=data.columns, index=data.index
            )
        except Exception as e:
            self.logger.error(f"Error in standardization: {e}", exc_info=True)
            raise RuntimeError(f"Error in standardization: {e}")

    def extract_missingindicator_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract columns indicating missing values from the DataFrame.

        Args:
            data: Input DataFrame to extract missing indicator columns from.

        Returns:
            DataFrame containing only the missing indicator columns.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If no missing indicator columns are found.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            missing_indicator_cols = [col for col in data.columns if col.startswith("missingindicator_")]
            self.logger.info(f"Found {len(missing_indicator_cols)} missing indicator columns")
            return data[missing_indicator_cols]
        except Exception as e:
            self.logger.error(f"Error extracting missing indicator columns: {e}", exc_info=True)
            raise ValueError(f"Error extracting missing indicator columns: {e}")

    def inverse_dummy_cat_features(self, data: pd.DataFrame, dummy_cat_columns: list) -> pd.DataFrame:
        """Perform inverse encoding on dummy categorical features.

        Args:
            data: DataFrame containing encoded categorical features.
            dummy_cat_columns: List of original categorical column names.

        Returns:
            DataFrame with categorical features inverse-encoded.

        Raises:
            TypeError: If `data` is not a pandas DataFrame or `dummy_cat_columns` is not a list.
            ValueError: If inverse encoding fails or `dummy_cat_columns` is empty.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input data must be a pandas DataFrame")
            raise TypeError("Input data must be a pandas DataFrame")
        if not isinstance(dummy_cat_columns, list) or not dummy_cat_columns:
            self.logger.error("dummy_cat_columns must be a non-empty list of column names")
            raise TypeError("dummy_cat_columns must be a non-empty list of column names")
        try:
            self.logger.debug("Inverse encoding dummy categorical features")
            cat_features_dict = {}
            for cat_feature in dummy_cat_columns:
                for column in data.columns:
                    if column.startswith(cat_feature):
                        cat_features_dict[cat_feature] = cat_features_dict.get(
                            cat_feature, []
                        ) + [column]
            for feature, cols in cat_features_dict.items():
                data[feature] = np.array(cols)[data[cols].to_numpy().argmax(axis=1)]
                data[feature] = data[feature].str.replace(f"{feature}_", "")
                data.drop(columns=cols, inplace=True)
            data = data[dummy_cat_columns].astype("category")
            return data
        except Exception as e:
            self.logger.error(f"Error in inverse encoding categorical features: {e}", exc_info=True)
            raise ValueError(f"Error in inverse encoding categorical features: {e}")

    def inverse_ordinal_cat_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Perform inverse ordinal encoding on categorical features.

        Args:
            data: DataFrame containing ordinal-encoded categorical features.

        Returns:
            DataFrame with categorical features inverse-encoded.

        Raises:
            AttributeError: If the ordinal encoder has not been initialized.
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If inverse encoding fails.
        """
        if not hasattr(self, "oe"):
            self.logger.error("Ordinal encoder not initialized. Run encode_ordinal_cat_features first")
            raise AttributeError("Ordinal encoder not initialized. Run encode_ordinal_cat_features first")
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input data must be a pandas DataFrame")
            raise TypeError("Input data must be a pandas DataFrame")
        try:
            self.logger.debug("Inverse encoding ordinal categorical features")
            data_round = data.round()
            return pd.DataFrame(self.oe.inverse_transform(data_round), columns=data.columns, index = data.index)
        except Exception as e:
            self.logger.error(f"Error in inverse ordinal encoding: {e}", exc_info=True)
            raise ValueError(f"Error in inverse ordinal encoding: {e}")

    def inverse_normalization(self, data: pd.DataFrame) -> pd.DataFrame:
        """Perform inverse normalization for numerical features.

        Args:
            data: DataFrame to inverse normalize.

        Returns:
            Inverse-normalized DataFrame.

        Raises:
            AttributeError: If no scaler has been initialized.
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If inverse normalization fails.
        """
        if not hasattr(self, "scaler"):
            self.logger.error("Scaler not initialized")
            raise AttributeError("Scaler not initialized")
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        try:
            self.logger.debug("Performing inverse normalization")
            data_inverse_normalized = pd.DataFrame(
                self.scaler.inverse_transform(data),
                columns=data.columns,
                index=data.index,
            )
            return data_inverse_normalized.astype("float64")
        except Exception as e:
            self.logger.error(f"Error in inverse normalization: {e}", exc_info=True)
            raise ValueError(f"Error in inverse normalization: {e}")

    def data_imputation(
        self,
        data: pd.DataFrame,
        dummy_cat_columns: Optional[List] = None,
        ordinal_cat_columns: Optional[List] = None,
        numerical_columns: Optional[List] = None,
        scaler: str = "minmax",
        n_neighbors: int = 5,
        add_indicators: bool = True
    ) -> pd.DataFrame:
        """Impute missing values with a pipeline of preprocessing, imputation, and postprocessing.

        Args:
            data: Input DataFrame to process.
            dummy_cat_columns: List of dummy categorical column names (default: None).
            ordinal_cat_columns: List of ordinal categorical column names (default: None).
            numerical_columns: List of numerical column names (default: None).
            scaler: Scaler type for numerical features ('standard', 'minmax', 'robust'; default: 'minmax').
            n_neighbors: Number of neighbors for KNN imputation (default: 5).

        Returns:
            Imputed and decoded DataFrame.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If specified columns are not in the DataFrame or processing fails.
        """
        dummy_cat_columns = dummy_cat_columns or []
        ordinal_cat_columns = ordinal_cat_columns or []
        numerical_columns = numerical_columns or []

        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")

        all_cols = dummy_cat_columns + ordinal_cat_columns + numerical_columns
        if not all(col in data.columns for col in all_cols):
            missing_cols = [col for col in all_cols if col not in data.columns]
            self.logger.error(f"Some specified columns not in dataset: {missing_cols}")
            raise ValueError(f"Some specified columns not in dataset: {missing_cols}")

        try:
            self.logger.info("Starting preprocessing for imputation")
            preprocessed_parts = []

            if ordinal_cat_columns:
                self.logger.info("Encoding ordinal categorical features")
                ordinal_data = data[ordinal_cat_columns]
                ordinal_encoded = self.encode_ordinal_cat_features(ordinal_data)
                preprocessed_parts.append(ordinal_encoded)

            if dummy_cat_columns:
                self.logger.info("Encoding dummy categorical features")
                dummy_data = data[dummy_cat_columns]
                dummy_encoded = self.encode_dummy_cat_features(dummy_data)
                preprocessed_parts.append(dummy_encoded)

            if numerical_columns:
                self.logger.info("Standardizing numerical features")
                numerical_data = data[numerical_columns]
                numerical_normalized = self.standardization(numerical_data, scaler=scaler)
                preprocessed_parts.append(numerical_normalized)

            if not preprocessed_parts:
                self.logger.error("No columns specified for processing")
                raise ValueError("No columns specified for processing")

            data_preprocessed = pd.concat(preprocessed_parts, axis=1)

            self.logger.info("Initializing KNN imputer")
            data_imputed = self.knn_imputer(
                data_preprocessed,
                dummy_cat_columns=dummy_cat_columns,
                ordinal_cat_columns=ordinal_cat_columns,
                n_neighbors=n_neighbors,
                add_indicators = add_indicators
            )
    
            missing_indicator_cols = [
                col for col in data_imputed.columns if col.startswith("missingindicator_")
            ]
            postprocessed_parts = []
            self.logger.info("Postprocessing: decoding and inverse normalization")
            
            
            if ordinal_cat_columns:
                self.logger.info("Decoding ordinal categorical features")
                ordinal_imputed = data_imputed[ordinal_cat_columns]
                ordinal_decoded = self.inverse_ordinal_cat_features(ordinal_imputed)
                postprocessed_parts.append(ordinal_decoded)

            if dummy_cat_columns:
                self.logger.info("Decoding dummy categorical features")
                dummy_cols_after_encoding = [
                    col for col in data_imputed.columns
                    if any(col.startswith(cat) for cat in dummy_cat_columns)
                ]
                dummy_imputed = data_imputed[dummy_cols_after_encoding]
                dummy_decoded = self.inverse_dummy_cat_features(dummy_imputed, dummy_cat_columns)
                postprocessed_parts.append(dummy_decoded)

            if numerical_columns:
                self.logger.info("Inverse normalizing numerical features")
                numerical_imputed = data_imputed[numerical_columns]
                numerical_denormalized = self.inverse_normalization(numerical_imputed)
                postprocessed_parts.append(numerical_denormalized)
            #Extract missing indicator columns
            self.logger.info("Extracting missing indicator columns")
            missing_indicator_cols = self.extract_missingindicator_columns(data_imputed)
            postprocessed_parts.append(missing_indicator_cols)

            data_final = pd.concat(postprocessed_parts, axis=1)
            self.logger.info("Data imputation completed")
            return data_final
        except Exception as e:
            self.logger.error(f"Error in data imputation: {e}", exc_info=True)
            raise ValueError(f"Error in data imputation: {e}")

    def feature_engineering(
        self,
        data: pd.DataFrame,
        data_type: str,
        overmissing_threshold: float = 50,
        ordinal_cat_columns: Optional[List] = None,
        unique_threshold: int = 10, 
        scaler: str = "minmax",
        n_neighbors: int = 5
    ) -> tuple:
        """Feature engineering pipeline including removal of over-missing features, type classification, and imputation.

        Args:
            data: Input DataFrame to process.
            data_type: Transcriptomics or Clinical data.
            overmissing_threshold: Maximum percentage of missing values allowed (default: 50).
            ordinal_cat_columns: List of ordinal categorical column names (default: None).
            scaler: Scaler type for numerical features ('standard', 'minmax', 'robust'; default: 'minmax').
            n_neighbors: Number of neighbors for KNN imputation (default: 5).

        Returns:
            Processed DataFrame with engineered features.

        Raises:
            TypeError: If `data` is not a pandas DataFrame.
            ValueError: If specified columns are invalid or processing fails.
        """
        if not isinstance(data, pd.DataFrame):
            self.logger.error("Input must be a pandas DataFrame")
            raise TypeError("Input must be a pandas DataFrame")
        ordinal_cat_columns = ordinal_cat_columns or []
        if not all(col in data.columns for col in ordinal_cat_columns):
            missing_cols = [col for col in ordinal_cat_columns if col not in data.columns]
            self.logger.error(f"Some ordinal categorical columns not in dataset: {missing_cols}")
            raise ValueError(f"Some ordinal categorical columns not in dataset: {missing_cols}")
        if data_type not in ["transcriptomics","clinical"]:
            self.logger.error("Data type must be 'transcriptomics', or 'clinical'")
            raise ValueError("Data type must be 'transcriptomics', or 'clinical'")
        try:
            self.logger.info(f"Removing features with missing percentages > {overmissing_threshold}")
            removed_overmissing_df = self.remove_overmissing_features(data=data, threshold=overmissing_threshold)
            if data_type == "clinical":
                self.logger.info("Classifying feature types in clinical data.")
                dummy_cat_features, num_features = self.classify_features_types(
                    data=removed_overmissing_df,
                    threshold_unique_values=unique_threshold,
                    ordinal_features=ordinal_cat_columns
                )
                self.logger.info(f"There are {len(dummy_cat_features)} dummy categorical features")
                self.logger.info(f"There are {len(num_features)} numerical features")
                self.logger.info(f"There are {len(ordinal_cat_columns)} ordinal categorical features defined")
            else:
                self.logger.info("All gene expression features are numerical features.")
                dummy_cat_features = []
                num_features = removed_overmissing_df.columns.to_list() 
                self.logger.info(f"There are {len(dummy_cat_features)} dummy categorical features")
                self.logger.info(f"There are {len(num_features)} numerical features")
                self.logger.info(f"There are {len(ordinal_cat_columns)} ordinal categorical features defined")

            self.logger.info("Imputing missing features")
            processed_features_df = self.data_imputation(
                data=removed_overmissing_df,
                dummy_cat_columns=dummy_cat_features,
                ordinal_cat_columns=ordinal_cat_columns,
                numerical_columns=num_features,
                scaler=scaler,
                n_neighbors=n_neighbors
            )
            self.logger.info("Feature engineering completed")
            return processed_features_df, num_features, dummy_cat_features
        except Exception as e:
            self.logger.error(f"Error in feature engineering: {e}", exc_info=True)
            raise ValueError(f"Error in feature engineering: {e}")