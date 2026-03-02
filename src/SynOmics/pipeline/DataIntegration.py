import pandas as pd
import sys
from typing import Optional

sys.path.append("../")
from SynOmics.processing.gene_query import GeneQuery
from SynOmics.processing.preprocessing import DataProcessor
import os
import logging
import json


class DataIntegrationPipeline:
    """
    A pipeline to preprocess and integrate clinical and transcriptomics data with configurable steps.
    """

    def __init__(self, output_dir: str):
        """
        Initialize the pipeline with an output directory for logs and metadata.

        Args:
            output_dir (str): Directory to save logs and intermediate files.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        # Initialize preprocessing helpers
        self.preprocessor = DataProcessor

        # Set up pipeline logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        log_path = os.path.join(output_dir, "DataIntegrationPipeline.log")
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.info("Data integration pipeline initialized")

    def process_transcriptomics_data(
        self,
        transcriptomics_data: pd.DataFrame,
        transcriptomics_id_column: str,
        steps_config: dict,
        overmissing_samples_threshold: float = 50,
        overmissing_features_threshold: float = 50,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        n_neighbors: int = 5,
        low_expression_variance_threshold: float = 0.0005,
    ) -> pd.DataFrame:
        """
        Process raw transcriptomics data with configurable steps.

        Args:
            transcriptomics_data (pd.DataFrame): Raw transcriptomics data.
            transcriptomics_id_column (str): Column name for patient IDs in transcriptomics data.
            steps_config (dict): Configuration for steps.
            overmissing_samples_threshold: Threshold for removing over-missing samples
            overmissing_features_threshold (float): Threshold for removing over-missing features.
            unique_threshold (int): Threshold for classifying categorical features.
            scaler (str): Scaler type for numerical features.
            n_neighbors (int): Number of neighbors for KNN imputation.
            low_expression_variance_threshold (float): Variance cutoff for near-constant genes when
                `remove_low_expression_genes` is enabled.

        Returns:
            pd.DataFrame: Processed transcriptomics data.
        """
        self.gene_querier = GeneQuery(
            fields=["symbol"],
            scopes=["ensemblgene"],
            species=["human"],
            output_dir=self.output_dir,
        )
        self.logger.info("Processing transcriptomics data")
        data = transcriptomics_data.copy()

        # Step 1 Remove undefined data (rows with missing data)
        if steps_config.get("remove_undefined", True):
            self.logger.info(f"Removing rows with missing: {transcriptomics_id_column}")
            data = self.preprocessor.remove_unknown_entities(
                data=data, id_column=transcriptomics_id_column
            )
        else:
            self.logger.info("Skipping removal of undefined data in transcriptomics")

        # Step 2: Remove duplicates
        if steps_config.get("remove_duplicates", True):
            self.logger.info(
                "Removing duplicate columns (genes) in transcriptomics data"
            )
            data = self.preprocessor.remove_duplications(data=data, axis=1)
            self.logger.info(
                "Removing duplicate rows (samples) in transcriptomics data"
            )
            data = self.preprocessor.remove_duplications(data=data, axis=0)
        else:
            self.logger.info("Skipping duplicate removal in transcriptomics")

        # Step 3: Remove overmissing samples
        if steps_config.get("remove_overmissing_samples", True):
            self.logger.info(
                f"Removing transcriptomics samples with missing values > {overmissing_samples_threshold}%"
            )
            data = self.preprocessor.remove_overmissing_entities(
                data=data, threshold=overmissing_samples_threshold
            )
        else:
            self.logger.info(
                "Skipping removal of overmissing samples in transcriptomics"
            )

        # Step 4: Split into ID and features
        self.logger.info(
            f"Splitting transcriptomics data into ID ('{transcriptomics_id_column}') and features"
        )
        id_data = data[[transcriptomics_id_column]].copy()
        features_data = data.drop(columns=[transcriptomics_id_column])

        # Step 4.0: Remove low-expressed genes (transcriptomics only)
        remove_low_expr = steps_config.get(
            "remove_low_expression_genes",
            steps_config.get("remove_low_expressed_gene", False),
        )
        if remove_low_expr:
            self.logger.info(
                "Removing low-expressed genes (zero-sum or near-zero variance)"
            )
            features_data = self.preprocessor.remove_low_expression_genes(
                data=features_data,
                variance_threshold=low_expression_variance_threshold,
            )
        else:
            self.logger.info("Skipping removal of low-expressed genes")

        # Step 5.1 Check duplicates genes
        if steps_config.get("check_duplicate_genes", True):
            self.logger.info("Checking for duplicate genes based on expression values")
            self.dup_genes, self.dup_mapped_genes = self.gene_querier.check_duplicates(
                data=features_data
            )
            if self.dup_genes:
                self.logger.info("Duplicate genes found and mapped to HUGO symbols")
            else:
                self.logger.info("No duplicate genes found")
        else:
            self.logger.info("Skipping duplicate gene check in transcriptomics")
        # Step 5.2 Mapping Ensemble ID and HUGO ID
        if steps_config.get("mapping_genes", True):
            self.logger.info("Mapping Ensembl IDs to HUGO symbols")
            self.gene_info_df = self.gene_querier.convert_genes(data=features_data)
        else:
            self.logger.info("Skipping Ensembl to HUGO conversion")

        # Step 6: Feature engineering (remove over-missing features, classify types, impute)
        if steps_config.get("feature_engineering", True):
            self.logger.info("Performing feature engineering on transcriptomics data")
            features_data, self.transcriptomics_num_columns, _ = (
                self.preprocessor.feature_engineering(
                    data=features_data,
                    data_type="transcriptomics",
                    overmissing_threshold=overmissing_features_threshold,
                    ordinal_cat_columns=None,
                    unique_threshold=unique_threshold,
                    scaler=scaler,
                    imputer="knn",
                    imputer_params={"n_neighbors": n_neighbors},
                    add_indicators=True,
                    verbose=True,
                )
            )
        else:
            self.logger.info("Skipping feature engineering in transcriptomics")

        # Step 7: Concatenate ID and processed features
        self.logger.info(
            "Concatenating ID column with processed transcriptomics features"
        )
        processed_data = pd.concat([id_data, features_data], axis=1)
        return processed_data

    def process_clinical_data(
        self,
        clinical_data: pd.DataFrame,
        clinical_id_column: str,
        steps_config: dict,
        overmissing_samples_threshold: float = 50,
        overmissing_features_threshold: float = 50,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        n_neighbors: int = 5,
        ordinal_cat_columns: Optional[list] = None,
    ) -> pd.DataFrame:
        """
        Process raw clinical data with configurable steps.

        Args:
            clinical_data (pd.DataFrame): Raw clinical data.
            clinical_id_column (str): Column name for patient IDs in clinical data.
            steps_config (dict): Configuration for steps.
            overmissing_samples_threshold (float): Threshold for removing over-missing samples.
            overmissing_features_threshold (float): Threshold for removing over-missing features.
            unique_threshold (int): Threshold for classifying categorical features.
            scaler (str): Scaler type for numerical features.
            n_neighbors (int): Number of neighbors for KNN imputation.
            ordinal_cat_columns (list, optional): List of ordinal categorical columns.

        Returns:
            pd.DataFrame: Processed clinical data.
        """
        self.logger.info("Processing clinical data")
        data = clinical_data.copy()

        # Step 1: Remove undefined data (rows with missing IDs)
        if steps_config.get("remove_undefined", True):
            self.logger.info(
                f"Removing rows with missing '{clinical_id_column}' in clinical data"
            )
            data = self.preprocessor.remove_unknown_entities(
                data=data, id_column=clinical_id_column
            )
        else:
            self.logger.info("Skipping removal of undefined data in clinical data")

        # Step 2: Remove duplicates
        if steps_config.get("remove_duplicates", True):
            self.logger.info("Removing duplicate columns in clinical data")
            data = self.preprocessor.remove_duplications(data=data, axis=1)
            self.logger.info("Removing duplicate rows in clinical data")
            data = self.preprocessor.remove_duplications(data=data, axis=0)
        else:
            self.logger.info("Skipping duplicate removal in clinical data")

        # Step 3: Remove over-missing sample:
        if steps_config.get("remove_overmissing_samples", True):
            self.logger.info(
                f"Removing clinincal samples with missing values > {overmissing_samples_threshold}%"
            )
            data = self.preprocessor.remove_overmissing_entities(
                data=data, threshold=overmissing_samples_threshold
            )
        else:
            self.logger.info("Skipping removal of overmissing samples in clinical data")

        # Step 4: Split into ID and features
        self.logger.info(
            f"Splitting clinical data into ID ('{clinical_id_column}') and features"
        )
        id_data = data[[clinical_id_column]].copy()
        features_data = data.drop(columns=[clinical_id_column])

        # Step 5: Feature engineering
        if steps_config.get("feature_engineering", True):
            self.logger.info("Performing feature engineering on clinical data")
            features_data, self.clinical_num_columns, self.clinical_dummy_columns = (
                self.preprocessor.feature_engineering(
                    data=features_data,
                    data_type="clinical",
                    overmissing_threshold=overmissing_features_threshold,
                    ordinal_cat_columns=ordinal_cat_columns,
                    unique_threshold=unique_threshold,
                    scaler=scaler,
                    imputer="knn",
                    imputer_params={"n_neighbors": n_neighbors},
                    add_indicators=True,
                    verbose=True,
                )
            )
        else:
            self.logger.info("Skipping feature engineering in clinical data")

        # Step 6: Concatenate ID and processed features
        self.logger.info("Concatenating ID column with processed clinical features")
        processed_data = pd.concat([id_data, features_data], axis=1)
        return processed_data

    def integrate_data(
        self,
        processed_clinical: pd.DataFrame,
        processed_transcriptomics: pd.DataFrame,
        clinical_id_column: str,
        transcriptomics_id_column: str,
        integration_id_column: str,
        steps_config: dict,
    ) -> pd.DataFrame:
        """
        Integrate processed clinical and transcriptomics data if enabled.

        Args:
            processed_clinical (pd.DataFrame): Processed clinical data.
            processed_transcriptomics (pd.DataFrame): Processed transcriptomics data.
            clinical_id_column (str): ID column name in clinical data.
            transcriptomics_id_column (str): ID column name in transcriptomics data.
            integration_id_column (str): Common ID column name for integration.
            steps_config (dict): Configuration for steps.

        Returns:
            pd.DataFrame: Integrated dataset (or None if integration is skipped).
        """
        if steps_config.get("integrate_data", True):
            self.logger.info("Integrating clinical and transcriptomics data")

            # Rename ID columns to a common name for merging
            clinical_data = processed_clinical.rename(
                columns={clinical_id_column: integration_id_column}
            )
            transcriptomics_data = processed_transcriptomics.rename(
                columns={transcriptomics_id_column: integration_id_column}
            )

            # Ensure ID columns are of the same type
            clinical_data[integration_id_column] = clinical_data[
                integration_id_column
            ].astype(str)
            transcriptomics_data[integration_id_column] = transcriptomics_data[
                integration_id_column
            ].astype(str)

            # Merge on the common ID column
            integrated_data = pd.merge(
                clinical_data,
                transcriptomics_data,
                on=integration_id_column,
                how="inner",
            )

            self.logger.info(f"Integrated data shape: {integrated_data.shape}")
            return integrated_data
        else:
            self.logger.info("Skipping data integration")
            return None

    def run_pipeline(
        self,
        clinical_data: pd.DataFrame,
        transcriptomics_data: pd.DataFrame,
        clinical_id_column: str,
        transcriptomics_id_column: str,
        integration_id_column: str = "PATIENT_ID",
        steps_config: Optional[dict] = None,
        overmissing_samples_threshold: float = 50,
        overmissing_features_threshold: float = 50,
        unique_threshold: int = 10,
        scaler: str = "minmax",
        n_neighbors: int = 5,
        low_expression_variance_threshold: float = 0.0005,
        ordinal_cat_columns: Optional[list] = None,
    ) -> dict:
        """
        Run the pipeline with configurable steps and different ID columns.

        Args:
            clinical_data (pd.DataFrame): Raw clinical data.
            transcriptomics_data (pd.DataFrame): Raw transcriptomics data.
            clinical_id_column (str): Column name for patient IDs in clinical data.
            transcriptomics_id_column (str): Column name for patient IDs in transcriptomics data.
            integration_id_column (str): Common ID column name for integration.
            steps_config (dict, optional): Dict specifying which steps to run.
            overmissing_samples_threshold (float): Threshold for removing over-missing samples.
            overmissing_features_threshold (float): Threshold for removing over-missing features.
            unique_threshold (int): Threshold for classifying categorical features.
            scaler (str): Scaler type for numerical features.
            n_neighbors (int): Number of neighbors for KNN imputation.
            low_expression_variance_threshold (float): Variance cutoff for near-constant genes when
                `remove_low_expression_genes` is enabled.
            ordinal_cat_columns (list, optional): List of ordinal categorical columns in clinical data.

        Returns:
            dict: Dictionary containing processed clinical data, transcriptomics data, and integrated data.
        """
        self.logger.info("Starting data integration pipeline")

        # Default steps configuration (all steps enabled)
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

        # Update with user-provided configuration
        steps_config = steps_config or {}
        steps_config = {**default_steps, **steps_config}
        self.logger.info(f"Steps configuration: {steps_config}")

        # Process transcriptomics data
        processed_transcriptomics = self.process_transcriptomics_data(
            transcriptomics_data=transcriptomics_data,
            transcriptomics_id_column=transcriptomics_id_column,
            steps_config=steps_config,
            overmissing_samples_threshold=overmissing_samples_threshold,
            overmissing_features_threshold=overmissing_features_threshold,
            unique_threshold=unique_threshold,
            scaler=scaler,
            n_neighbors=n_neighbors,
            low_expression_variance_threshold=low_expression_variance_threshold,
        )

        # Process clinical data
        processed_clinical = self.process_clinical_data(
            clinical_data=clinical_data,
            clinical_id_column=clinical_id_column,
            steps_config=steps_config,
            overmissing_samples_threshold=overmissing_samples_threshold,
            overmissing_features_threshold=overmissing_features_threshold,
            unique_threshold=unique_threshold,
            scaler=scaler,
            n_neighbors=n_neighbors,
            ordinal_cat_columns=ordinal_cat_columns,
        )

        # Integrate the data
        integrated_data = self.integrate_data(
            processed_clinical=processed_clinical,
            processed_transcriptomics=processed_transcriptomics,
            clinical_id_column=clinical_id_column,
            transcriptomics_id_column=transcriptomics_id_column,
            integration_id_column=integration_id_column,
            steps_config=steps_config,
        )
        # Create meta data
        if integrated_data is None:
            raise ValueError(
                "Integration step was skipped (integrated_data is None). Cannot build feature metadata."
            )

        integrated_features = integrated_data.drop([integration_id_column], axis=1)
        feature_type_meta = {}
        for col in integrated_features.columns.to_list():
            if col in self.clinical_dummy_columns:
                feature_type_meta[col] = "dummy_categorical"
            elif (
                col in self.clinical_num_columns
                or col in self.transcriptomics_num_columns
            ):
                feature_type_meta[col] = "numerical"
            elif col in (ordinal_cat_columns or []):
                feature_type_meta[col] = "ordinal_categorical"
            # missinngindicator
            elif col.startswith("missingindicator_"):
                feature_type_meta[col] = "missing_categorical"
            else:
                feature_type_meta[col] = "unclassified"
        if "unclassified" in feature_type_meta.values():
            count_unclassified = list(feature_type_meta.values()).count("unclassified")
            self.logger.warning(
                f"{count_unclassified} unclassified features. Check the JSON file"
            )
        json_path = os.path.join(self.output_dir, "feature_metadata.json")
        with open(json_path, "w") as file:  # Fixed 'wb' to 'w' for JSON text
            json.dump(feature_type_meta, file, indent=4)
        self.logger.info("Pipeline completed successfully")
        return {
            "processed_clinical": processed_clinical,
            "processed_transcriptomics": processed_transcriptomics,
            "integrated_data": integrated_data,
        }
