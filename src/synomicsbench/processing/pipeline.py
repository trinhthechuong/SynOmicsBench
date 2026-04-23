import os
import json
import time
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any

from synomicsbench.processing.gene_query import GeneQuery
from synomicsbench.processing.preprocessing import DataProcessor
from synomicsbench.utils.monitoring import set_logger


class DataIntegrationPipeline:
    """
    End-to-end pipeline for processing and integrating clinical and transcriptomics data.

    This pipeline:
    - Cleans data (removes undefined IDs, deduplicates, filters over-missing samples)
    - Performs feature engineering (over-missing feature filtering, type classification, imputation)
    - Optionally maps Ensembl gene IDs to HUGO symbols
    - Integrates processed clinical and transcriptomics data on a common ID
    - Exports a feature metadata JSON and logs detailed progress for easy monitoring

    Args:
        output_dir (str): Directory where logs and outputs (e.g., feature_metadata.json) are saved.
        logger (str): Suffix for the log filename (e.g., Preprocess_{logger}.log).

    Returns:
        None

    Raises:
        OSError: If the output directory cannot be created.
    """

    def __init__(self, output_dir: str, logger: str = ""):
        """
        Initialize the data integration pipeline and configure logging.

        Args:
            output_dir (str): Directory where logs and outputs are stored.
            logger (str): Suffix for the log filename.

        Returns:
            None

        Raises:
            OSError: If the output directory cannot be created.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        logger_name = f"{self.__class__.__name__}_{id(self)}"
        log_file_name = f"Preprocess_{logger}.log"
        self.logger = set_logger(logger_name, self.output_dir, log_file_name)

        # Placeholders set during processing
        self.clinical_num_columns: List[str] = []
        self.clinical_dummy_columns: List[str] = []
        self.transcriptomics_num_columns: List[str] = []

    def process_transcriptomics_data(
        self,
        transcriptomics_data: pd.DataFrame,
        transcriptomics_id_column: str,
        steps_config: Dict,
        overmissing_samples_threshold: float = 50.0,
        overmissing_features_threshold: float = 50.0,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        imputer: str = "mice",
        imputer_params: Optional[Dict[str, Any]] = None,
        low_expression_variance_threshold: float = 0.0005,
        add_indicators: bool = True,
        verbose: bool = True,
    ) -> pd.DataFrame:
        """
        Process raw transcriptomics data with configurable steps.

        Args:
            transcriptomics_data (pd.DataFrame): Raw transcriptomics data.
            transcriptomics_id_column (str): Column name for sample/patient IDs.
            steps_config (dict): Flags controlling which steps to run.
            overmissing_samples_threshold (float): Remove rows with missingness > threshold (0-100).
            overmissing_features_threshold (float): Remove columns with missingness > threshold (0-100).
            unique_threshold (int): Threshold to classify categorical features (not used for transcriptomics).
            scaler (str): Scaler type for numerical features ('minmax', 'standard', 'robust').
            imputer (str): Imputation method to use ('knn' or 'mice').
            imputer_params (dict, optional): Method-specific params. For 'knn': e.g., {'n_neighbors': 5}.
                                            For 'mice': e.g., {'iterations': 20, 'n_estimators': 300}.
            low_expression_variance_threshold (float): Variance cutoff for near-constant genes when
                `remove_low_expression_genes` is enabled.
            add_indicators (bool): Whether to add missingness indicator columns during imputation.
            verbose (bool): Print progress from lower-level utilities.

        Returns:
            pd.DataFrame: Processed transcriptomics data with imputed features and optional indicators.

        Raises:
            KeyError: If transcriptomics_id_column is not found in the input DataFrame.
            TypeError: If transcriptomics_data is not a pandas DataFrame.
            ValueError: On invalid thresholds or processing errors in underlying steps.
        """
        start_total = time.perf_counter()
        if not isinstance(transcriptomics_data, pd.DataFrame):
            raise TypeError("transcriptomics_data must be a pandas DataFrame")
        if transcriptomics_id_column not in transcriptomics_data.columns:
            raise KeyError(
                f"ID column '{transcriptomics_id_column}' not found in transcriptomics data"
            )

        # Initialize gene query helper
        self.gene_querier = GeneQuery(
            fields=["symbol"],
            scopes=["ensemblgene"],
            species=["human"],
            output_dir=self.output_dir,
        )

        data = transcriptomics_data.copy()
        self.logger.info(
            f"[TRANSCRIPTOMICS] Initial shape: rows={data.shape[0]}, cols={data.shape[1]}"
        )

        # Step 1: Remove undefined data (rows with missing IDs)
        if steps_config.get("remove_undefined", True):
            t0 = time.perf_counter()
            before = data.shape[0]
            self.logger.info(
                f"[T1] Removing undefined samples missing ID in '{transcriptomics_id_column}'"
            )
            data = DataProcessor.remove_unknown_entities(
                data=data, id_column=transcriptomics_id_column
            )
            data = data.reset_index(drop=True)
            after = data.shape[0]
            self.logger.info(
                f"[T1] Removed {before - after} rows; new shape: rows={data.shape[0]}, cols={data.shape[1]} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T1] Skipped remove_undefined")

        # Step 2: Remove duplicates (columns then rows)
        if steps_config.get("remove_duplicates", True):
            # Columns
            t0 = time.perf_counter()
            before_cols = data.shape[1]
            self.logger.info("[T2.1] Removing duplicate columns")
            data = DataProcessor.remove_duplications(data=data, axis=1)
            after_cols = data.shape[1]
            self.logger.info(
                f"[T2.1] Removed {before_cols - after_cols} duplicate columns; cols={after_cols} (took {time.perf_counter() - t0:.2f}s)"
            )

            # Rows
            t0 = time.perf_counter()
            before_rows = data.shape[0]
            self.logger.info("[T2.2] Removing duplicate rows")
            data = DataProcessor.remove_duplications(data=data, axis=0)
            data = data.reset_index(drop=True)
            after_rows = data.shape[0]
            self.logger.info(
                f"[T2.2] Removed {before_rows - after_rows} duplicate rows; rows={after_rows} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T2] Skipped remove_duplicates")

        # Step 3: Remove over-missing samples
        if steps_config.get("remove_overmissing_samples", True):
            t0 = time.perf_counter()
            before = data.shape[0]
            self.logger.info(
                f"[T3] Removing samples with missingness > {overmissing_samples_threshold}%"
            )
            data = DataProcessor.remove_overmissing_entities(
                data=data, threshold=overmissing_samples_threshold
            )
            data = data.reset_index(drop=True)
            after = data.shape[0]
            self.logger.info(
                f"[T3] Removed {before - after} rows; new rows={after} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T3] Skipped remove_overmissing_samples")

        # Split into ID and features
        id_data = data[[transcriptomics_id_column]].copy()
        features_data = data.drop(columns=[transcriptomics_id_column])

        # Step 4.0: Remove low-expressed genes (transcriptomics only)
        remove_low_expr = steps_config.get(
            "remove_low_expression_genes",
            steps_config.get("remove_low_expressed_gene", False),
        )
        if remove_low_expr:
            t0 = time.perf_counter()
            before_cols = features_data.shape[1]
            self.logger.info(
                "[T4.0] Removing low-expressed genes (zero-sum or near-zero variance)"
            )
            features_data = DataProcessor.remove_low_expression_genes(
                data=features_data,
                variance_threshold=low_expression_variance_threshold,
            )
            after_cols = features_data.shape[1]
            self.logger.info(
                f"[T4.0] Removed {before_cols - after_cols} gene(s); cols={after_cols} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T4.0] Skipped remove_low_expression_genes")

        # Step 4.1: Check duplicate genes
        if steps_config.get("check_duplicate_genes", True):
            t0 = time.perf_counter()
            self.logger.info(
                "[T4.1] Checking for genes with identical expression profiles"
            )
            self.dup_genes, self.dup_mapped_genes = self.gene_querier.check_duplicates(
                data=features_data
            )
            n_dup = len(self.dup_genes) if self.dup_genes is not None else 0
            self.logger.info(
                f"[T4.1] Found {n_dup} duplicate gene(s) (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T4.1] Skipped check_duplicate_genes")

        # Step 4.2: Map Ensembl IDs to HUGO symbols
        if steps_config.get("mapping_genes", True):
            t0 = time.perf_counter()
            self.logger.info("[T4.2] Mapping Ensembl IDs to HUGO symbols")
            self.gene_info_df = self.gene_querier.convert_genes(data=features_data)
            self.logger.info(
                f"[T4.2] Gene mapping produced shape={getattr(self.gene_info_df, 'shape', None)} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T4.2] Skipped mapping_genes")

        # Step 5: Feature engineering for transcriptomics (all numerical)
        if steps_config.get("feature_engineering", True):
            t0 = time.perf_counter()
            self.logger.info(
                f"[T5] Feature engineering (remove over-missing features > {overmissing_features_threshold}%, impute via {imputer.upper()})"
            )
            features_data, self.transcriptomics_num_columns, _ = (
                DataProcessor.feature_engineering(
                    data=features_data,
                    data_type="transcriptomics",
                    overmissing_threshold=overmissing_features_threshold,
                    ordinal_cat_columns=None,
                    unique_threshold=unique_threshold,
                    scaler=scaler,
                    imputer=imputer,
                    imputer_params=imputer_params or {},
                    add_indicators=add_indicators,
                    verbose=verbose,
                )
            )
            self.logger.info(
                f"[T5] Feature engineering complete; features shape={features_data.shape} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[T5] Skipped feature_engineering")

        processed_data = pd.concat([id_data, features_data], axis=1)
        self.logger.info(
            f"[TRANSCRIPTOMICS] Final shape: rows={processed_data.shape[0]}, cols={processed_data.shape[1]} (total {time.perf_counter() - start_total:.2f}s)"
        )
        return processed_data

    def process_clinical_data(
        self,
        clinical_data: pd.DataFrame,
        clinical_id_column: str,
        steps_config: Dict,
        overmissing_samples_threshold: float = 50.0,
        overmissing_features_threshold: float = 50.0,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        imputer: str = "knn",
        imputer_params: Optional[Dict[str, Any]] = None,
        ordinal_cat_columns: Optional[List[str]] = None,
        add_indicators: bool = True,
        verbose: bool = True,
    ) -> pd.DataFrame:
        """
        Process raw clinical data with configurable steps.

        Args:
            clinical_data (pd.DataFrame): Raw clinical data.
            clinical_id_column (str): Column name for sample/patient IDs.
            steps_config (dict): Flags controlling which steps to run.
            overmissing_samples_threshold (float): Remove rows with missingness > threshold (0-100).
            overmissing_features_threshold (float): Remove columns with missingness > threshold (0-100).
            unique_threshold (int): Unique value threshold to classify categorical features.
            scaler (str): Scaler type for numerical features ('minmax', 'standard', 'robust').
            imputer (str): Imputation method to use ('knn' or 'mice').
            imputer_params (dict, optional): Method-specific params. For 'knn': e.g., {'n_neighbors': 5}.
                                            For 'mice': e.g., {'iterations': 20, 'n_estimators': 300}.
            ordinal_cat_columns (list, optional): Known ordinal categorical columns.
            add_indicators (bool): Whether to add missingness indicator columns during imputation.
            verbose (bool): Print progress from lower-level utilities.

        Returns:
            pd.DataFrame: Processed clinical data with imputed features and indicators.

        Raises:
            KeyError: If clinical_id_column is not found in clinical_data.
            TypeError: If clinical_data is not a pandas DataFrame.
            ValueError: On invalid thresholds or processing errors in underlying steps.
        """
        start_total = time.perf_counter()
        ordinal_cat_columns = ordinal_cat_columns or []

        if not isinstance(clinical_data, pd.DataFrame):
            raise TypeError("clinical_data must be a pandas DataFrame")
        if clinical_id_column not in clinical_data.columns:
            raise KeyError(
                f"ID column '{clinical_id_column}' not found in clinical data"
            )

        data = clinical_data.copy()
        self.logger.info(
            f"[CLINICAL] Initial shape: rows={data.shape[0]}, cols={data.shape[1]}"
        )

        # Step 1: Remove undefined data (rows with missing IDs)
        if steps_config.get("remove_undefined", True):
            t0 = time.perf_counter()
            before = data.shape[0]
            self.logger.info(
                f"[C1] Removing undefined samples missing ID in '{clinical_id_column}'"
            )
            data = DataProcessor.remove_unknown_entities(
                data=data, id_column=clinical_id_column
            )
            data = data.reset_index(drop=True)
            after = data.shape[0]
            self.logger.info(
                f"[C1] Removed {before - after} rows; new shape: rows={after}, cols={data.shape[1]} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[C1] Skipped remove_undefined")

        # Step 2: Remove duplicates (columns then rows)
        if steps_config.get("remove_duplicates", True):
            # Columns
            t0 = time.perf_counter()
            before_cols = data.shape[1]
            self.logger.info("[C2.1] Removing duplicate columns")
            data = DataProcessor.remove_duplications(data=data, axis=1)
            after_cols = data.shape[1]
            self.logger.info(
                f"[C2.1] Removed {before_cols - after_cols} duplicate columns; cols={after_cols} (took {time.perf_counter() - t0:.2f}s)"
            )

            # Rows
            t0 = time.perf_counter()
            before_rows = data.shape[0]
            self.logger.info("[C2.2] Removing duplicate rows")
            data = DataProcessor.remove_duplications(data=data, axis=0)
            data = data.reset_index(drop=True)
            after_rows = data.shape[0]
            self.logger.info(
                f"[C2.2] Removed {before_rows - after_rows} duplicate rows; rows={after_rows} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[C2] Skipped remove_duplicates")

        # Step 3: Remove over-missing samples
        if steps_config.get("remove_overmissing_samples", True):
            t0 = time.perf_counter()
            before = data.shape[0]
            self.logger.info(
                f"[C3] Removing clinical samples with missingness > {overmissing_samples_threshold}%"
            )
            data = DataProcessor.remove_overmissing_entities(
                data=data, threshold=overmissing_samples_threshold
            )
            data = data.reset_index(drop=True)
            after = data.shape[0]
            self.logger.info(
                f"[C3] Removed {before - after} rows; new rows={after} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[C3] Skipped remove_overmissing_samples")

        # Split into ID and features
        id_data = data[[clinical_id_column]].copy()
        features_data = data.drop(columns=[clinical_id_column])

        # Step 4: Feature engineering (classify, remove over-missing features, impute)
        if steps_config.get("feature_engineering", True):
            t0 = time.perf_counter()
            self.logger.info(
                f"[C4] Feature engineering (remove over-missing features > {overmissing_features_threshold}%, classify types, impute via {imputer.upper()})"
            )
            features_data, self.clinical_num_columns, self.clinical_dummy_columns = (
                DataProcessor.feature_engineering(
                    data=features_data,
                    data_type="clinical",
                    overmissing_threshold=overmissing_features_threshold,
                    ordinal_cat_columns=ordinal_cat_columns,
                    unique_threshold=unique_threshold,
                    scaler=scaler,
                    imputer=imputer,
                    imputer_params=imputer_params or {},
                    add_indicators=add_indicators,
                    verbose=verbose,
                )
            )
            self.logger.info(
                f"[C4] Feature engineering complete; features shape={features_data.shape} (took {time.perf_counter() - t0:.2f}s)"
            )
        else:
            self.logger.info("[C4] Skipped feature_engineering")

        processed_data = pd.concat([id_data, features_data], axis=1)
        self.logger.info(
            f"[CLINICAL] Final shape: rows={processed_data.shape[0]}, cols={processed_data.shape[1]} (total {time.perf_counter() - start_total:.2f}s)"
        )
        return processed_data

    def integrate_data(
        self,
        processed_clinical: pd.DataFrame,
        processed_transcriptomics: pd.DataFrame,
        clinical_id_column: str,
        transcriptomics_id_column: str,
        integration_id_column: str,
        steps_config: Dict,
    ) -> Optional[pd.DataFrame]:
        """
        Integrate processed clinical and transcriptomics data on a common ID.

        Args:
            processed_clinical (pd.DataFrame): Processed clinical dataset.
            processed_transcriptomics (pd.DataFrame): Processed transcriptomics dataset.
            clinical_id_column (str): ID column in processed_clinical.
            transcriptomics_id_column (str): ID column in processed_transcriptomics.
            integration_id_column (str): Name for the common ID column after renaming.
            steps_config (dict): Flags controlling whether to integrate.

        Returns:
            pd.DataFrame or None: Integrated dataset if integration is enabled; otherwise None.

        Raises:
            KeyError: If required ID columns are missing in the provided DataFrames.
            TypeError: If inputs are not pandas DataFrames.
        """
        if not isinstance(processed_clinical, pd.DataFrame) or not isinstance(
            processed_transcriptomics, pd.DataFrame
        ):
            raise TypeError(
                "processed_clinical and processed_transcriptomics must be pandas DataFrames"
            )
        if clinical_id_column not in processed_clinical.columns:
            raise KeyError(
                f"ID column '{clinical_id_column}' not found in processed_clinical"
            )
        if transcriptomics_id_column not in processed_transcriptomics.columns:
            raise KeyError(
                f"ID column '{transcriptomics_id_column}' not found in processed_transcriptomics"
            )

        if not steps_config.get("integrate_data", True):
            self.logger.info("[MERGE] Skipping data integration")
            return None

        self.logger.info(
            "[MERGE] Integrating clinical and transcriptomics data by common ID"
        )

        clinical_data = processed_clinical.rename(
            columns={clinical_id_column: integration_id_column}
        )
        transcriptomics_data = processed_transcriptomics.rename(
            columns={transcriptomics_id_column: integration_id_column}
        )

        # Ensure compatible types for join key
        clinical_data[integration_id_column] = clinical_data[
            integration_id_column
        ].astype(str)
        transcriptomics_data[integration_id_column] = transcriptomics_data[
            integration_id_column
        ].astype(str)

        left_count = clinical_data.shape[0]
        right_count = transcriptomics_data.shape[0]
        self.logger.info(f"[MERGE] Left rows={left_count}, Right rows={right_count}")

        integrated_data = pd.merge(
            clinical_data, transcriptomics_data, on=integration_id_column, how="inner"
        )

        matched = integrated_data.shape[0]
        self.logger.info(
            f"[MERGE] Inner join matched rows={matched}; final shape: rows={integrated_data.shape[0]}, cols={integrated_data.shape[1]}"
        )
        return integrated_data

    def run_pipeline(
        self,
        clinical_data: pd.DataFrame,
        transcriptomics_data: pd.DataFrame,
        clinical_id_column: str,
        transcriptomics_id_column: str,
        integration_id_column: str = "PATIENT_ID",
        steps_config: Optional[Dict] = None,
        overmissing_samples_threshold: float = 50.0,
        overmissing_features_threshold: float = 50.0,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        ordinal_cat_columns: Optional[List[str]] = None,
        imputer: str = "mice",
        imputer_params: Optional[Dict[str, Any]] = None,
        low_expression_variance_threshold: float = 0.0005,
        add_indicators: bool = True,
        verbose: bool = True,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Run the full pipeline across transcriptomics and clinical data and optionally integrate them.

        Args:
            clinical_data (pd.DataFrame): Raw clinical data.
            transcriptomics_data (pd.DataFrame): Raw transcriptomics data.
            clinical_id_column (str): ID column name in clinical_data.
            transcriptomics_id_column (str): ID column name in transcriptomics_data.
            integration_id_column (str): Common ID column name for integration.
            steps_config (dict, optional): Dict specifying which steps to run; defaults enable all steps.
            overmissing_samples_threshold (float): Remove rows with missingness > threshold (0-100).
            overmissing_features_threshold (float): Remove columns with missingness > threshold (0-100).
            unique_threshold (int): Unique value threshold to classify categorical features (clinical).
            scaler (str): Scaler type for numerical features ('minmax', 'standard', 'robust').
            ordinal_cat_columns (list, optional): Ordinal categorical columns in clinical data.
            imputer (str): Imputation method to use ('knn' or 'mice').
            imputer_params (dict, optional): Method-specific params.
            low_expression_variance_threshold (float): Variance cutoff for near-constant genes when
                `remove_low_expression_genes` is enabled.
            add_indicators (bool): Whether to add missingness indicator columns during imputation.
            verbose (bool): Print progress from lower-level utilities.

        Returns:
            dict: Dictionary containing:
                - 'processed_clinical' (pd.DataFrame): Processed clinical data
                - 'processed_transcriptomics' (pd.DataFrame): Processed transcriptomics data
                - 'integrated_data' (pd.DataFrame or None): Integrated dataset if integration enabled

        Raises:
            TypeError: If inputs are not pandas DataFrames.
            KeyError: If required ID columns are missing.
            ValueError: On processing errors in underlying steps.
        """
        self.logger.info("=== STARTING DATA INTEGRATION PIPELINE ===")
        pipeline_start = time.perf_counter()

        default_steps = {
            "remove_undefined": True,
            "remove_duplicates": True,
            "remove_overmissing_samples": True,
            "remove_low_expression_genes": False,
            "check_duplicate_genes": True,
            "mapping_genes": True,
            "feature_engineering": True,
            "integrate_data": True,
        }
        steps_config = {**default_steps, **(steps_config or {})}
        self.logger.info(f"[CONFIG] Steps: {steps_config}")

        # Process transcriptomics
        processed_transcriptomics = self.process_transcriptomics_data(
            transcriptomics_data=transcriptomics_data,
            transcriptomics_id_column=transcriptomics_id_column,
            steps_config=steps_config,
            overmissing_samples_threshold=overmissing_samples_threshold,
            overmissing_features_threshold=overmissing_features_threshold,
            unique_threshold=unique_threshold,
            scaler=scaler,
            imputer=imputer,
            imputer_params=imputer_params,
            low_expression_variance_threshold=low_expression_variance_threshold,
            add_indicators=add_indicators,
            verbose=verbose,
        )

        # Process clinical
        processed_clinical = self.process_clinical_data(
            clinical_data=clinical_data,
            clinical_id_column=clinical_id_column,
            steps_config=steps_config,
            overmissing_samples_threshold=overmissing_samples_threshold,
            overmissing_features_threshold=overmissing_features_threshold,
            unique_threshold=unique_threshold,
            scaler=scaler,
            imputer=imputer,
            imputer_params=imputer_params,
            ordinal_cat_columns=ordinal_cat_columns,
            add_indicators=add_indicators,
            verbose=verbose,
        )

        # Integrate
        integrated_data = self.integrate_data(
            processed_clinical=processed_clinical,
            processed_transcriptomics=processed_transcriptomics,
            clinical_id_column=clinical_id_column,
            transcriptomics_id_column=transcriptomics_id_column,
            integration_id_column=integration_id_column,
            steps_config=steps_config,
        )

        # Build feature metadata regardless of integration outcome
        self.logger.info("[METADATA] Building feature type metadata")
        clinical_features = processed_clinical.drop(
            columns=[clinical_id_column]
        ).columns.tolist()
        transcriptomics_features = processed_transcriptomics.drop(
            columns=[transcriptomics_id_column]
        ).columns.tolist()

        if integrated_data is not None:
            integrated_features = integrated_data.drop(
                columns=[integration_id_column]
            ).columns.tolist()
        else:
            # If not integrated, use union of features for metadata
            integrated_features = sorted(
                set(clinical_features).union(set(transcriptomics_features))
            )

        ordinal_cat_columns = ordinal_cat_columns or []
        clinical_dummy = getattr(self, "clinical_dummy_columns", []) or []
        clinical_num = getattr(self, "clinical_num_columns", []) or []
        transcript_num = getattr(self, "transcriptomics_num_columns", []) or []

        feature_type_meta: Dict[str, str] = {}
        for col in integrated_features:
            if col in clinical_dummy:
                feature_type_meta[col] = "dummy_categorical"
            elif col in clinical_num or col in transcript_num:
                feature_type_meta[col] = "numerical"
            elif col in ordinal_cat_columns:
                feature_type_meta[col] = "ordinal_categorical"
            elif col.startswith("missingindicator_"):
                feature_type_meta[col] = "missing_categorical"
            else:
                feature_type_meta[col] = "unclassified"

        # Log summary
        counts = {
            "numerical": sum(v == "numerical" for v in feature_type_meta.values()),
            "ordinal_categorical": sum(
                v == "ordinal_categorical" for v in feature_type_meta.values()
            ),
            "dummy_categorical": sum(
                v == "dummy_categorical" for v in feature_type_meta.values()
            ),
            "missing_categorical": sum(
                v == "missing_categorical" for v in feature_type_meta.values()
            ),
            "unclassified": sum(
                v == "unclassified" for v in feature_type_meta.values()
            ),
        }
        self.logger.info(f"[METADATA] Counts: {counts}")
        if counts["unclassified"] > 0:
            self.logger.warning(
                f"[METADATA] {counts['unclassified']} unclassified feature(s). Check your metadata or processing configuration."
            )

        # Save metadata JSON
        json_path = os.path.join(self.output_dir, "feature_metadata.json")
        with open(json_path, "w") as f:
            json.dump(feature_type_meta, f, indent=4)
        self.logger.info(f"[METADATA] Saved feature metadata to: {json_path}")

        self.logger.info(
            f"=== PIPELINE COMPLETED in {time.perf_counter() - pipeline_start:.2f}s ==="
        )
        return {
            "processed_clinical": processed_clinical,
            "processed_transcriptomics": processed_transcriptomics,
            "integrated_data": integrated_data,
        }
