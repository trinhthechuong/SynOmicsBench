import pandas as pd
import numpy as np
import os
import json
import warnings

warnings.filterwarnings("ignore")
from typing import Optional, List, Dict, Any, Tuple
from sklearn.impute import MissingIndicator
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.base import BaseEstimator
from sklearn.preprocessing import OrdinalEncoder
from sklearn.impute import KNNImputer
from SynOmics.processing.metadata import MetaData

# Optional dependency: miceforest (MICE imputation)
try:
    import miceforest as mf
except ImportError:  # pragma: no cover
    mf = None


class DataProcessor:
    """
    DataProcessor provides static methods for preprocessing, encoding, imputing, and engineering features
    in omics or clinical datasets.

    This class enables duplicate removal, missing value filtering, encoding of categorical features,
    normalization, KNN imputation, and feature engineering classification.

    Methods are tailored for pandas DataFrame workflows in bioinformatics and genomics.

    """

    def __init__(self):
        pass

    @staticmethod
    def remove_duplications(data: pd.DataFrame, axis: int) -> pd.DataFrame:
        """
        Remove duplicate rows or columns from the DataFrame.

        Args:
            data (pd.DataFrame): Input DataFrame.
            axis (int): 0 to remove duplicate rows, 1 to remove duplicate columns.

        Returns:
            pd.DataFrame: DataFrame with duplicates removed.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: If axis is not 0 or 1.
            RuntimeError: On error during duplicate removal.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if axis not in [0, 1]:
            raise ValueError("Axis must be 0 (rows) or 1 (columns)")
        try:
            if axis == 0:
                return data.drop_duplicates()
            elif axis == 1:
                return data.loc[:, ~data.columns.duplicated()]
        except Exception as e:
            raise RuntimeError(f"Error removing duplicates: {e}")

    @staticmethod
    def remove_unknown_entities(data: pd.DataFrame, id_column: str) -> pd.DataFrame:
        """
        Remove rows where the identifier column contains missing values.

        Args:
            data (pd.DataFrame): Input DataFrame.
            id_column (str): Name of the identifier column.

        Returns:
            pd.DataFrame: Filtered DataFrame.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            KeyError: If id_column is not in DataFrame.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Data input must be a pandas DataFrame")
        if id_column not in data.columns:
            raise KeyError(f"ID column '{id_column}' not in DataFrame")
        return data.dropna(subset=[id_column])

    @staticmethod
    def remove_overmissing_entities(
        data: pd.DataFrame, threshold: float
    ) -> pd.DataFrame:
        """
        Remove rows (entities) with missing value percentage above a threshold.

        Args:
            data (pd.DataFrame): Input DataFrame.
            threshold (float): Percentage threshold (0-100).

        Returns:
            pd.DataFrame: DataFrame with over-missing entities removed.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: If threshold is not between 0 and 100.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if not 0 <= threshold <= 100:
            raise ValueError("Threshold must be between 0 and 100")
        try:
            # Calculate the percentage of missing values per row
            missing_percentage = data.isnull().mean(axis=1) * 100
            # Keep rows where missing percentage is <= threshold
            keep_rows = missing_percentage <= threshold
            return data[keep_rows].copy()
        except Exception as e:
            raise ValueError(f"Error removing over-missing samples: {e}")

    @staticmethod
    def find_missing_percent(data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the percentage of missing values for each column.

        Args:
            data (pd.DataFrame): Input DataFrame.

        Returns:
            pd.DataFrame: DataFrame with columns 'ColumnName' and 'PercentMissing'.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            RuntimeError: On error during calculation.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Data input must be a pandas DataFrame")
        try:
            return (
                (data.isnull().sum() / len(data) * 100)
                .reset_index()
                .rename(columns={0: "PercentMissing", "index": "ColumnName"})
            )
        except Exception as e:
            raise RuntimeError(f"Error calculating missing percentages: {e}")

    @staticmethod
    def remove_overmissing_features(
        data: pd.DataFrame, threshold: float
    ) -> pd.DataFrame:
        """
        Remove columns (features) with missing value percentage above a threshold.

        Args:
            data (pd.DataFrame): Input DataFrame.
            threshold (float): Percentage threshold (0-100).

        Returns:
            pd.DataFrame: DataFrame with over-missing features removed.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: If threshold is not between 0 and 100.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if not 0 <= threshold <= 100:
            raise ValueError("Threshold must be between 0 and 100")
        try:
            miss_df = (
                (data.isnull().sum() / len(data) * 100)
                .reset_index()
                .rename(columns={0: "PercentMissing", "index": "ColumnName"})
            )
            drop_cols = miss_df[miss_df["PercentMissing"] > threshold][
                "ColumnName"
            ].tolist()
            return data.drop(drop_cols, axis=1)
        except Exception as e:
            raise ValueError(f"Error removing over-missing columns: {e}")

    @staticmethod
    def remove_low_expression_genes(
        data: pd.DataFrame,
        gene_id_column: str = "gene_id",
        variance_threshold: float = 0.0005,
    ) -> pd.DataFrame:
        """
        Remove low-expressed genes from transcriptomics expression data.

        This utility supports two common transcriptomics orientations:
        - Genes as rows and samples as columns (optionally with a `gene_id` column).
        - Samples as rows and genes as columns (pipeline convention in SynOmics).

        A gene is removed if either:
        - Total expression equals 0 across all samples, OR
        - Variance is <= `variance_threshold` across all samples.

        Args:
            data (pd.DataFrame): Expression DataFrame.
            gene_id_column (str): Column containing gene IDs when genes are rows.
            variance_threshold (float): Near-zero variance threshold.

        Returns:
            pd.DataFrame: Filtered DataFrame in the same orientation as the input.

        Raises:
            TypeError: If data is not a pandas DataFrame.
            ValueError: If variance_threshold is negative or data contains non-numeric columns.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if variance_threshold < 0:
            raise ValueError("variance_threshold must be >= 0")

        # Orientation: genes are rows (optionally with a gene_id column).
        if gene_id_column in data.columns:
            expression_matrix = data.set_index(gene_id_column)
            numeric = expression_matrix.apply(pd.to_numeric, errors="coerce")
            non_numeric_cols = numeric.columns[
                numeric.notna().sum(axis=0) == 0
            ].tolist()
            if non_numeric_cols:
                raise ValueError(
                    "Non-numeric sample columns found in expression matrix: "
                    f"{non_numeric_cols}"
                )

            sum_expression = numeric.sum(axis=1)
            zero_genes = sum_expression[sum_expression == 0].index.tolist()

            variances_expression = numeric.var(axis=1)
            near_zero_var = variances_expression[
                variances_expression <= variance_threshold
            ].index.tolist()

            remove_genes = set(zero_genes) | set(near_zero_var)
            filtered = expression_matrix.drop(index=list(remove_genes), errors="ignore")
            return filtered.reset_index()

        # Orientation: samples are rows, genes are columns.
        numeric = data.apply(pd.to_numeric, errors="coerce")
        non_numeric_cols = numeric.columns[numeric.notna().sum(axis=0) == 0].tolist()
        if non_numeric_cols:
            raise ValueError(
                "Non-numeric gene columns found in expression matrix: "
                f"{non_numeric_cols}"
            )

        sum_expression = numeric.sum(axis=0)
        zero_genes = sum_expression[sum_expression == 0].index.tolist()

        variances_expression = numeric.var(axis=0)
        near_zero_var = variances_expression[
            variances_expression <= variance_threshold
        ].index.tolist()

        remove_genes = set(zero_genes) | set(near_zero_var)
        return data.drop(columns=list(remove_genes), errors="ignore")

    ### Prepare for Imputation ###
    @staticmethod
    def encode_dummy_features(data: pd.DataFrame) -> pd.DataFrame:
        """
        Encode categorical features into dummy/one-hot columns.

        Args:
            data (pd.DataFrame): DataFrame with categorical features.

        Returns:
            pd.DataFrame: Dummy-encoded DataFrame.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: If encoding fails.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            cat_data_encoded = pd.get_dummies(
                data, dtype="int64", dummy_na=True, columns=data.columns
            )
            return cat_data_encoded
        except Exception as e:
            raise ValueError(f"Error encoding categorical features: {e}")

    @staticmethod
    def encode_ordinal_features(
        data: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, OrdinalEncoder]:
        """
        Encode ordinal categorical features using OrdinalEncoder.

        Args:
            data (pd.DataFrame): DataFrame with ordinal categorical features.

        Returns:
            Tuple[pd.DataFrame, OrdinalEncoder]: Encoded DataFrame and fitted encoder.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: If encoding fails.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            oe = OrdinalEncoder()
            encoded_values = oe.fit_transform(data)
            df_ordinal_encoded = pd.DataFrame(
                encoded_values, columns=data.columns, index=data.index
            )
            return df_ordinal_encoded, oe
        except Exception as e:
            raise ValueError(f"Error encoding ordinal categorical features: {e}")

    @staticmethod
    def standardization(
        data: pd.DataFrame, scaler: str
    ) -> Tuple[pd.DataFrame, BaseEstimator]:
        """
        Standardize numerical features using specified scaler.

        Args:
            data (pd.DataFrame): DataFrame with numerical features.
            scaler (str): Scaler type ('standard', 'minmax', or 'robust').

        Returns:
            Tuple[pd.DataFrame, BaseEstimator]: Scaled DataFrame and scaler object.

        Raises:
            ValueError: If scaler type is invalid.
            TypeError: If input is not a pandas DataFrame.
            RuntimeError: If scaling fails.
        """
        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
        }
        if scaler not in scalers:
            raise ValueError("Scaler must be 'standard', 'minmax', or 'robust'")
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            scaler_obj = scalers[scaler]
            scaled_data = pd.DataFrame(
                scaler_obj.fit_transform(data), columns=data.columns, index=data.index
            )
            return scaled_data, scaler_obj
        except Exception as e:
            raise RuntimeError(f"Error in standardization: {e}")

    @staticmethod
    def _add_indicators(data: pd.DataFrame) -> pd.DataFrame:
        """
        Append missingness indicators only for columns that have missing values.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        mi = MissingIndicator(features="missing-only", error_on_new=False)
        mask = mi.fit_transform(data)  # shape: (n_samples, n_missing_cols)
        missing_cols = data.columns[mi.features_]  # Only columns with missingness
        ind_cols = [f"missingindicator_{c}" for c in missing_cols]
        indicators_df = pd.DataFrame(
            mask.astype(np.int8), columns=ind_cols, index=data.index
        )
        return indicators_df

    @staticmethod
    def mice_imputation(
        data: pd.DataFrame,
        *,
        random_state: int = 42,
        iterations: int = 20,
        n_estimators: int = 300,
        add_indicators: bool = True,
        verbose: bool = True,
        **mice_kwargs: Any,
    ) -> pd.DataFrame:
        """
        Impute with miceforest and optionally append missing indicators.
        Additional miceforest arguments can be passed via **mice_kwargs (e.g., variable_schema).
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")

        if mf is None:
            raise ImportError(
                "miceforest is required for MICE imputation. Install it or use imputer='knn'."
            )

        out = data.copy()

        # Cast object to category so miceforest can treat them as categorical if present
        for c in out.select_dtypes(include=["object"]).columns:
            out[c] = out[c].astype("category")

        kernel = mf.ImputationKernel(
            data=out,
            num_datasets=1,  # miceforest uses `datasets`
            random_state=random_state,
            **mice_kwargs,
        )

        kernel.mice(iterations=iterations, n_estimators=n_estimators, verbose=verbose)

        df_imputed = kernel.complete_data(dataset=0)

        if add_indicators:
            df_ind = DataProcessor._add_indicators(
                data
            )  # build indicators from original
            df_imputed = pd.concat([df_imputed, df_ind], axis=1)

        return df_imputed

    @staticmethod
    def impute_router(
        data: pd.DataFrame,
        method: str = "mice",
        *,
        add_indicators: bool = True,
        knn_params: Optional[Dict[str, Any]] = None,
        mice_params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Dispatch imputation to KNN or MICE with method-specific parameters.

        Args:
            data (pd.DataFrame): Input frame (already preprocessed if needed).
            method (str): 'knn' or 'mice'.
            add_indicators (bool): Whether to append missing indicators.
            knn_params (dict): Passed to knn_imputer (n_neighbors, etc.).
            mice_params (dict): Passed to mice_imputation (iterations, n_estimators, etc.).

        Returns:
            pd.DataFrame: Imputed dataframe (with indicators if requested).
        """
        method = method.lower()
        knn_params = knn_params or {}
        mice_params = mice_params or {}

        if method == "knn":
            # Expecting this low-level utility to receive an already-encoded/normalized frame.
            # If you want the full pipeline, keep using knn_imputation (the full pipeline) elsewhere.
            return DataProcessor.knn_imputer(
                data=data,
                dummy_cat_columns=knn_params.pop("dummy_cat_columns", []),
                ordinal_cat_columns=knn_params.pop("ordinal_cat_columns", []),
                n_neighbors=knn_params.pop("n_neighbors", 5),
                add_indicators=add_indicators,
                **knn_params,
            )
        elif method == "mice":
            return DataProcessor.mice_imputation(
                data=data, add_indicators=add_indicators, **mice_params
            )
        else:
            raise ValueError("method must be 'knn' or 'mice'")

    @staticmethod
    def knn_imputer(
        data: pd.DataFrame,
        dummy_cat_columns: list,
        ordinal_cat_columns: Optional[List] = None,
        n_neighbors: int = 5,
        add_indicators: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Impute missing values using KNNImputer, with special handling for dummy and ordinal features.

        Args:
            data (pd.DataFrame): Preprocessed DataFrame.
            dummy_cat_columns (list): List of dummy categorical feature names.
            ordinal_cat_columns (List, optional): List of ordinal categorical feature names.
            n_neighbors (int): Number of neighbors for KNN.
            add_indicators (bool, optional): Whether to add missing indicators.
            **kwargs: Additional KNNImputer arguments.

        Returns:
            pd.DataFrame: DataFrame with imputed values and indicators.

        Raises:
            TypeError: On invalid input types.
            ValueError: On imputation errors.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if not isinstance(dummy_cat_columns, list):
            raise TypeError("dummy_cat_columns must be a list")
        ordinal_cat_columns = ordinal_cat_columns or []
        if not isinstance(ordinal_cat_columns, list):
            raise TypeError("ordinal_cat_columns must be a list")
        try:
            dummy_cat_features_dict = {}
            nan_dummy_features = []
            # Create a dictionary to hold dummy categorical features
            for dummy_cat_feature in dummy_cat_columns:
                for column in data.columns:
                    if column.startswith(dummy_cat_feature):
                        dummy_cat_features_dict[dummy_cat_feature] = (
                            dummy_cat_features_dict.get(dummy_cat_feature, [])
                            + [column]
                        )
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
            # Remove NaN dummy columns from the DataFrame
            if len(nan_dummy_features) > 0:
                data = data.drop(nan_dummy_features, axis=1)
            # Use KNN imputer to fill missing values
            imputer = KNNImputer(
                n_neighbors=n_neighbors,
                weights="distance",
                add_indicator=add_indicators,
                **kwargs,
            )
            data_imputed = pd.DataFrame(
                imputer.fit_transform(data),
                columns=imputer.get_feature_names_out(),
                index=data.index,
            )
            # Post-process the imputed data
            data_imputed[ordinal_cat_columns] = data_imputed[
                ordinal_cat_columns
            ].round()
            for key, value in index_dict.items():
                features = dummy_cat_features_dict[key][0:-1]
                argmax_index = np.argmax(
                    data_imputed.loc[value, features].values, axis=1
                )
                for i in range(len(value)):
                    data_imputed.loc[value[i], features] = [0] * len(features)
                    data_imputed.loc[value[i], features[argmax_index[i]]] = 1

            # Combine duplicate missing indicators for dummy variables
            if add_indicators:
                indicator_cols = [
                    col
                    for col in data_imputed.columns
                    if col.startswith("missingindicator_")
                ]
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
                            data_imputed.rename(
                                columns={col: combined_col}, inplace=True
                            )
            return data_imputed
        except Exception as e:
            raise ValueError(f"Error in KNN imputation: {e}")

    @staticmethod
    def extract_missingindicator_columns(data: pd.DataFrame) -> pd.DataFrame:
        """
        Extract columns indicating missingness from imputed DataFrame.

        Args:
            data (pd.DataFrame): DataFrame after imputation.

        Returns:
            pd.DataFrame: DataFrame with only missing indicator columns.

        Raises:
            TypeError: If input is not a pandas DataFrame.
            ValueError: On extraction errors.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            missing_indicator_cols = [
                col for col in data.columns if col.startswith("missingindicator_")
            ]
            return data[missing_indicator_cols]
        except Exception as e:
            raise ValueError(f"Error extracting missing indicator columns: {e}")

    ### Processing after imputation ###
    @staticmethod
    def inverse_dummy_features(
        data: pd.DataFrame, dummy_cat_columns: list
    ) -> pd.DataFrame:
        """
        Decode dummy-encoded categorical features back to original categories.

        Args:
            data (pd.DataFrame): DataFrame with dummy-encoded features.
            dummy_cat_columns (list): List of dummy categorical feature names.

        Returns:
            pd.DataFrame: DataFrame with decoded categorical columns.

        Raises:
            TypeError: On invalid input types or empty list.
            ValueError: On decoding errors.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input data must be a pandas DataFrame")
        if not isinstance(dummy_cat_columns, list) or not dummy_cat_columns:
            raise TypeError(
                "dummy_cat_columns must be a non-empty list of column names"
            )
        try:
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
            raise ValueError(f"Error in inverse encoding categorical features: {e}")

    @staticmethod
    def inverse_ordinal_features(
        data: pd.DataFrame, encoder: OrdinalEncoder
    ) -> pd.DataFrame:
        """
        Decode ordinal categorical features from encoded values back to original categories.

        Args:
            data (pd.DataFrame): DataFrame with encoded ordinal features.
            encoder (OrdinalEncoder): Fitted ordinal encoder.

        Returns:
            pd.DataFrame: Decoded ordinal categorical features.

        Raises:
            AttributeError: If encoder is not initialized.
            TypeError: If input is not a DataFrame.
            ValueError: On decoding errors.
        """
        if not isinstance(encoder, OrdinalEncoder):
            raise AttributeError(
                "Ordinal encoder not initialized. Run encode_ordinal_features first"
            )
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input data must be a pandas DataFrame")
        try:
            data_round = data.round()
            return pd.DataFrame(
                encoder.inverse_transform(data_round),
                columns=data.columns,
                index=data.index,
            )
        except Exception as e:
            raise ValueError(f"Error in inverse ordinal encoding: {e}")

    @staticmethod
    def inverse_standardization(
        data: pd.DataFrame, scaler: BaseEstimator
    ) -> pd.DataFrame:
        """
        Undo normalization/standardization on numerical features.

        Args:
            data (pd.DataFrame): DataFrame with normalized features.
            scaler (BaseEstimator): Fitted scaler.

        Returns:
            pd.DataFrame: DataFrame with original scale restored.

        Raises:
            AttributeError: If scaler is not initialized.
            TypeError: If input is not a DataFrame.
            ValueError: On inverse normalization errors.
        """
        if not isinstance(scaler, BaseEstimator):
            raise AttributeError("Scaler not initialized. Run standardization first")
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            data_inverse_normalized = pd.DataFrame(
                scaler.inverse_transform(data),
                columns=data.columns,
                index=data.index,
            )
            return data_inverse_normalized.astype("float64")
        except Exception as e:
            raise ValueError(f"Error in inverse normalization: {e}")

    @staticmethod
    def knn_imputation(
        data: pd.DataFrame,
        dummy_cat_columns: Optional[List] = None,
        ordinal_cat_columns: Optional[List] = None,
        numerical_columns: Optional[List] = None,
        scaler: str = "minmax",
        n_neighbors: int = 5,
        add_indicators: bool = True,
        verbose: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Perform full preprocessing and KNN imputation, including encoding, normalization, and postprocessing.

        Args:
            data (pd.DataFrame): Input DataFrame.
            dummy_cat_columns (List, optional): Dummy categorical columns.
            ordinal_cat_columns (List, optional): Ordinal categorical columns.
            numerical_columns (List, optional): Numerical columns.
            scaler (str, optional): Scaler type ('minmax', 'standard', 'robust').
            n_neighbors (int, optional): KNN neighbors.
            add_indicators (bool, optional): Add missing indicators.
            verbose (bool, optional): Print progress.
            **kwargs: Additional KNNImputer arguments.

        Returns:
            pd.DataFrame: DataFrame after imputation and decoding.

        Raises:
            TypeError: On invalid input.
            ValueError: On missing columns or errors.
        """
        dummy_cat_columns = dummy_cat_columns or []
        ordinal_cat_columns = ordinal_cat_columns or []
        numerical_columns = numerical_columns or []

        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")

        all_cols = dummy_cat_columns + ordinal_cat_columns + numerical_columns
        if not all(col in data.columns for col in all_cols):
            missing_cols = [col for col in all_cols if col not in data.columns]
            raise ValueError(f"Some specified columns not in dataset: {missing_cols}")

        try:
            if verbose:
                print("IMPUTATION: Starting preprocessing")
            preprocessed_parts = []

            or_encoder: Optional[OrdinalEncoder] = None
            scaler_obj: Optional[BaseEstimator] = None

            if ordinal_cat_columns:
                if verbose:
                    print(
                        "IMPUTATION-PREPROCESSING: Encoding ordinal categorical features"
                    )
                ordinal_data = data[ordinal_cat_columns]
                ordinal_encoded, or_encoder = DataProcessor.encode_ordinal_features(
                    ordinal_data
                )
                preprocessed_parts.append(ordinal_encoded)

            if dummy_cat_columns:
                if verbose:
                    print(
                        "IMPUTATION-PREPROCESSING: Encoding dummy categorical features"
                    )
                dummy_data = data[dummy_cat_columns]
                dummy_encoded = DataProcessor.encode_dummy_features(dummy_data)
                preprocessed_parts.append(dummy_encoded)

            if numerical_columns:
                if verbose:
                    print("IMPUTATION-PREPROCESSING: Standardizing numerical features")
                numerical_data = data[numerical_columns]
                numerical_normalized, scaler_obj = DataProcessor.standardization(
                    numerical_data, scaler=scaler
                )
                preprocessed_parts.append(numerical_normalized)

            if not preprocessed_parts:
                raise ValueError("No columns specified for processing")

            data_preprocessed = pd.concat(preprocessed_parts, axis=1)

            if verbose:
                print("IMPUTATION: Initializing KNN imputer")
            data_imputed = DataProcessor.knn_imputer(
                data_preprocessed,
                dummy_cat_columns=dummy_cat_columns,
                ordinal_cat_columns=ordinal_cat_columns,
                n_neighbors=n_neighbors,
                add_indicators=add_indicators,
                **kwargs,
            )

            missing_indicator_cols = [
                col
                for col in data_imputed.columns
                if col.startswith("missingindicator_")
            ]
            postprocessed_parts = []
            if verbose:
                print("IMPUTATION: Starting postprocessing")

            if ordinal_cat_columns:
                if verbose:
                    print(
                        "IMPUTATION-POSTPROCESSING: Decoding ordinal categorical features"
                    )
                ordinal_imputed = data_imputed[ordinal_cat_columns]
                if or_encoder is None:
                    raise RuntimeError("Ordinal encoder is not initialized")
                ordinal_decoded = DataProcessor.inverse_ordinal_features(
                    ordinal_imputed, or_encoder
                )
                postprocessed_parts.append(ordinal_decoded)

            if dummy_cat_columns:
                if verbose:
                    print(
                        "IMPUTATION-POSTPROCESSING: Decoding dummy categorical features"
                    )
                dummy_cols_after_encoding = [
                    col
                    for col in data_imputed.columns
                    if any(col.startswith(cat) for cat in dummy_cat_columns)
                ]
                dummy_imputed = data_imputed[dummy_cols_after_encoding]
                dummy_decoded = DataProcessor.inverse_dummy_features(
                    dummy_imputed, dummy_cat_columns
                )
                postprocessed_parts.append(dummy_decoded)

            if numerical_columns:
                if verbose:
                    print(
                        "IMPUTATION-POSTPROCESSING: Inverse normalizing numerical features"
                    )
                numerical_imputed = data_imputed[numerical_columns]
                if scaler_obj is None:
                    raise RuntimeError("Scaler is not initialized")
                numerical_denormalized = DataProcessor.inverse_standardization(
                    numerical_imputed, scaler_obj
                )
                postprocessed_parts.append(numerical_denormalized)
            # Extract missing indicator columns
            if verbose:
                print("IMPUTATION-POSTPROCESSING: Extracting missing indicator columns")
            missing_indicator_cols = DataProcessor.extract_missingindicator_columns(
                data_imputed
            )
            postprocessed_parts.append(missing_indicator_cols)

            data_final = pd.concat(postprocessed_parts, axis=1)
            if verbose:
                print("IMPUTATION: Data imputation completed")
            return data_final
        except Exception as e:
            raise ValueError(f"Error in data imputation: {e}")

    @staticmethod
    def feature_engineering(
        data: pd.DataFrame,
        data_type: str,
        overmissing_threshold: float = 50,
        imputer: str = "mice",
        ordinal_cat_columns: Optional[List[str]] = None,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        imputer_params: Optional[Dict[str, Any]] = None,
        add_indicators: bool = True,
        verbose: bool = True,
    ) -> tuple:
        """
        Perform feature engineering and imputation using a chosen method with its specific params.

        Args:
            data (pd.DataFrame): Input DataFrame.
            data_type (str): 'transcriptomics' or 'clinical'.
            overmissing_threshold (float): Drop features with missingness > threshold.
            imputer (str): 'mice' or 'knn'.
            ordinal_cat_columns (List[str], optional): Known ordinal categorical columns.
            unique_threshold (int): Threshold for classifying dummy features (clinical).
            scaler (str): 'minmax' | 'standard' | 'robust'.
            imputer_params (dict, optional): Method-specific params.
                - For 'knn': pass keys as in knn_imputer (e.g., n_neighbors, dummy_cat_columns, ordinal_cat_columns)
                - For 'mice': pass keys as in mice_imputation (e.g., iterations, n_estimators, random_state, verbose, …)
            add_indicators (bool): Append missing indicators.
            verbose (bool): Print progress.

        Returns:
            tuple: (processed_df, numerical_features, dummy_categorical_features)
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        if data_type not in ["transcriptomics", "clinical"]:
            raise ValueError("Data type must be 'transcriptomics' or 'clinical'")
        imputer_params = imputer_params or {}
        ordinal_cat_columns = ordinal_cat_columns or []

        if verbose:
            print(
                f"FEATURE ENGINEERING - OVERMISSING: Removing features with missing > {overmissing_threshold}%"
            )
        x = DataProcessor.remove_overmissing_features(
            data=data, threshold=overmissing_threshold
        )

        if data_type == "clinical":
            if verbose:
                print(
                    "FEATURE ENGINEERING - METADATA: Classifying feature types for clinical data"
                )
            dummy_cat_features, num_features = MetaData.classify_features_types(
                data=x,
                threshold_unique_values=unique_threshold,
                ordinal_features=ordinal_cat_columns,
            )
            if verbose:
                print(
                    f"  Dummy categorical: {len(dummy_cat_features)} | Numerical: {len(num_features)} | Ordinal: {len(ordinal_cat_columns)}"
                )
        else:
            if verbose:
                print("FEATURE ENGINEERING - METADATA: Transcriptomics → all numerical")
            dummy_cat_features = []
            num_features = x.columns.tolist()

        if verbose:
            print(f"FEATURE ENGINEERING - IMPUTATION: Using {imputer.upper()}")

        try:
            from lightgbm.basic import LightGBMError  # type: ignore

            _mice_excs = (ValueError, IndexError, LightGBMError)
        except Exception:
            _mice_excs = (ValueError, IndexError)

        if imputer.lower() == "knn":
            # Keep existing full KNN pipeline (encode→scale→impute→decode)
            processed_df = DataProcessor.knn_imputation(
                data=x,
                dummy_cat_columns=dummy_cat_features,
                ordinal_cat_columns=ordinal_cat_columns,
                numerical_columns=num_features,
                scaler=scaler,
                add_indicators=add_indicators,
                verbose=verbose,
                **imputer_params,  # method-specific extras go here
            )

        elif imputer.lower() == "mice":
            try:
                # For MICE, assume you've already preprocessed externally OR want to impute raw mixed df.
                # If you want to enforce encoding rules first, you can plug a preprocessing step here.
                processed_df = DataProcessor.mice_imputation(
                    data=x,
                    add_indicators=add_indicators,
                    verbose=verbose,
                    **imputer_params,  # iterations, n_estimators, random_state, verbose, etc.
                )
            except _mice_excs as e:
                print(x.columns)
                verbose = False
                n_fallback = 5
                processed_df = DataProcessor.knn_imputation(
                    data=x,
                    dummy_cat_columns=dummy_cat_features,
                    ordinal_cat_columns=ordinal_cat_columns,
                    numerical_columns=num_features,
                    scaler=scaler,
                    add_indicators=add_indicators,
                    verbose=verbose,
                    n_neighbors=5,  # method-specific extras go here
                )
                print(
                    f"\nMICE failed ({e.__class__.__name__}: {e}). Falling back to KNN (n_neighbors={n_fallback})."
                )
        else:
            raise ValueError("Imputer must be 'mice' or 'knn'")

        if verbose:
            print("FEATURE ENGINEERING: Completed")
        return processed_df, num_features, dummy_cat_features
