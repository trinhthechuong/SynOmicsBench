"""
BaseSynthesizer class for unified synthetic data generation workflows.

Provides common methods for logging, metadata handling, column type detection, anonymization,
rounding, min-max scaling, model management, and saving synthetic data.

Args:
    output_path (str): Path to save metadata, synthesizer, and synthetic data.
    metadata (dict, optional): Column-type metadata dictionary. Keys are column names,
        values are type strings (e.g., 'numerical', 'ordinal_categorical', 'dummy_categorical', 'missing_categorical').

Attributes:
    output_path (str): Output directory for results.
    logger (logging.Logger): Logger for this synthesizer instance.
    model (object): Fitted synthesizer model (set in fit()).
    metadata (dict): Metadata dictionary provided at init or via set_metadata().

Raises:
    ValueError: For invalid input types or errors in processing.
"""

import os
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from synomicsbench.utils.monitoring import set_logger
from synomicsbench.processing.postprocessing import (
    _detect_discrete_columns,
    _detect_numerical_columns,
    apply_min_max,
    apply_rounding,
    _detect_min_max_values,
    _detect_rounding_digits,
    anonymize_ids,
    post_masking
)

# Optional runtime resource monitoring (safe fallback if not available)
try:
    from synomicsbench.utils.monitoring import monitor_resources as _monitor_resources
except Exception:

    def _monitor_resources(func):
        return func


class BaseSynthesizer:
    """
    Base class providing a consistent pipeline: preprocess -> fit -> sample -> postprocess -> save.

    Subclasses should override:
      - preprocess (if they need data transformations before fitting, e.g., Gaussian Copula)
      - fit (required)
      - sample (required)
      - postprocess (optional to extend/override base behavior)
    """

    def __init__(self, output_path: str, metadata: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize the BaseSynthesizer.

        Args:
            output_path (str): Path to save outputs and logs.
            metadata (dict, optional): Metadata dictionary containing column type information.
        """
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)
        logger_name = f"{self.__class__.__name__}_{id(self)}"
        log_file_name = f"{self.__class__.__name__}_{id(self)}.log"
        self.emissions_file_name = f"{self.__class__.__name__}_{id(self)}.csv"
        self.logger = set_logger(logger_name, self.output_path, log_file_name)
        self.model: Any = None
        self.metadata: Optional[Dict[str, str]] = metadata

        # Run-start info
        self.logger.info("========== Synthesizer Initialized ==========")
        self.logger.info(f"Class: {self.__class__.__name__}")
        self.logger.info(f"Output path: {self.output_path}")
        self.logger.info(f"Log file: {os.path.join(self.output_path, log_file_name)}")
        if self.metadata is not None:
            self.logger.info(f"Metadata provided with {len(self.metadata)} columns.")
        else:
            self.logger.info("No metadata dictionary provided at initialization.")
        self.logger.info("============================================")

    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess input data for synthesizer.

        Args:
            data (pd.DataFrame): Input data.

        Returns:
            pd.DataFrame: Preprocessed data (default: returns input unchanged).
        """
        return data  # Override in subclass if needed (e.g., Gaussian Copula)

    def set_metadata(self, metadata: Dict[str, str]) -> None:
        """
        Set or update the metadata dictionary.

        Args:
            metadata (dict): Metadata dictionary containing column type information.

        Returns:
            None
        """
        self.metadata = metadata
        self.logger.info(f"Metadata updated with {len(metadata)} columns.")

    # Column detection utils use self.metadata directly
    def detect_discrete_columns(self, data: pd.DataFrame) -> List[str]:
        """
        Detect discrete columns from data and self.metadata.

        Args:
            data (pd.DataFrame): Input data.

        Returns:
            list: List of discrete column names.

        Raises:
            ValueError: If metadata is not set.
        """
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before detecting discrete columns.")
        return _detect_discrete_columns(data, self.metadata)

    def detect_numerical_columns(self, data: pd.DataFrame) -> List[str]:
        """
        Detect numerical columns from data and self.metadata.

        Args:
            data (pd.DataFrame): Input data.

        Returns:
            list: List of numerical column names.

        Raises:
            ValueError: If metadata is not set.
        """
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before detecting numerical columns.")
        return _detect_numerical_columns(data, self.metadata)

    # Thin wrappers to centralize calls (keeps subclasses tidy)
    def apply_rounding(self, data: pd.DataFrame, numerical_columns: Sequence[str], digits: Dict[str, int]) -> pd.DataFrame:
        return apply_rounding(data, numerical_columns, digits)

    def apply_min_max(
        self, data: pd.DataFrame, numerical_columns: Sequence[str], min_vals: Dict[str, float], max_vals: Dict[str, float]
    ) -> pd.DataFrame:
        return apply_min_max(data, numerical_columns, min_vals, max_vals)

    def detect_min_max_values(self, data: pd.DataFrame, numerical_columns: Sequence[str]):
        return _detect_min_max_values(data, numerical_columns)

    def detect_rounding_digits(self, data: pd.DataFrame, numerical_columns: Sequence[str]) -> Dict[str, int]:
        return _detect_rounding_digits(data, numerical_columns)

    def anonymize_ids(self, ids: Sequence[Any], synthetic_data: pd.DataFrame) -> pd.DataFrame:
        return anonymize_ids(ids, synthetic_data, self.output_path)

    def save_synthetic_data(self, synthetic_data: Union[pd.DataFrame, List[pd.DataFrame]], filename: str, index: bool = False) -> None:
        """
        Save synthetic data to CSV. Supports a single DataFrame or a list (e.g., Synthpop m>1).

        Args:
            synthetic_data (DataFrame or list[DataFrame]): Data to save.
            filename (str): Base filename for saving.
            index (bool): Whether to write DataFrame index.
        """
        if isinstance(synthetic_data, list):
            for i, df in enumerate(synthetic_data, 1):
                out = filename if filename.lower().endswith(".csv") else f"{filename}.csv"
                stem, ext = os.path.splitext(out)
                path = os.path.join(self.output_path, f"{stem}_{i}{ext or '.csv'}")
                df.to_csv(path, index=index)
                self.logger.info(f"Saved synthetic dataset {i} to {path}")
        else:
            out = filename if filename.lower().endswith(".csv") else f"{filename}.csv"
            path = os.path.join(self.output_path, out)
            synthetic_data.to_csv(path, index=index)
            self.logger.info(f"Saved synthetic data to {path}")

    # To be implemented by subclasses
    def fit(self, *args, **kwargs) -> None:
        raise NotImplementedError("fit() must be implemented in subclass.")

    def sample(self, *args, **kwargs) -> Union[pd.DataFrame, List[pd.DataFrame]]:
        raise NotImplementedError("sample() must be implemented in subclass.")

    def postprocess(
        self,
        synthetic_data: pd.DataFrame,
        original_data: pd.DataFrame,
        data_ids: Optional[Sequence[Any]] = None,
        enforce_rounding: bool = True,
        enforce_min_max: bool = True,
        masking: bool = False,
    ) -> pd.DataFrame:
        """
        Postprocess synthetic data, including anonymization, rounding, and min-max scaling.

        Args:
            synthetic_data (pd.DataFrame): Generated synthetic data.
            original_data (pd.DataFrame): Original data for reference.
            data_ids (list, optional): IDs to anonymize.
            enforce_rounding (bool, optional): Apply rounding with digits inferred from original_data.
            enforce_min_max (bool, optional): Clip to min/max observed in original_data.
            masking (bool, optional): If True and mask_func is provided, apply it to introduce missingness.

        Returns:
            pd.DataFrame: Postprocessed synthetic data.

        Raises:
            ValueError: If metadata is not set.
        """
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before postprocessing.")

        sdf = synthetic_data.copy()

        # Anonymize IDs
        if data_ids:
            self.logger.info("Anonymizing IDs in synthetic data")
            sdf = self.anonymize_ids(data_ids[: len(sdf)], sdf)
        else:
            self.logger.info("No data IDs provided for anonymization. Skipping ID anonymization.")

        # Numeric constraints
        if enforce_rounding or enforce_min_max:
            numerical_columns = self.detect_numerical_columns(original_data)
            if numerical_columns:
                if enforce_rounding:
                    self.logger.info("Applying rounding to synthetic data")
                    rounding_digits = self.detect_rounding_digits(original_data, numerical_columns)
                    sdf = self.apply_rounding(sdf, numerical_columns, rounding_digits)
                if enforce_min_max:
                    self.logger.info("Enforcing min-max on synthetic data")
                    min_values, max_values = self.detect_min_max_values(original_data, numerical_columns)
                    sdf = self.apply_min_max(sdf, numerical_columns, min_values, max_values)

        # Optional masking hook
        if masking:
            self.logger.info("Applying masking function to synthetic data")
            try:
                sdf = post_masking(sdf)
            except Exception as e:
                self.logger.warning(f"Masking function failed: {e}")

        return sdf

    @_monitor_resources
    # @track_emissions(output_dir = self.output_path, output_file = self.emissions_file_name)
    # @profile
    def generate(
        self,
        data: pd.DataFrame,
        data_ids: Optional[Sequence[Any]] = None,
        enforce_rounding: bool = True,
        enforce_min_max: bool = True,
        masking: bool = False,
        seed: int = 42,
        n_samples: int = 10,
        fit_params: Optional[Dict[str, Any]] = None,
        sample_params: Optional[Dict[str, Any]] = None,
        output_filename: str = "synthetic_data.csv",
        save_index: bool = False) -> Union[pd.DataFrame, List[pd.DataFrame]]:
        
        fit_params = fit_params or {}
        sample_params = sample_params or {}
        try:
            self.logger.info(
                f"Pipeline started for {self.__class__.__name__} "
                f"(n_samples={n_samples}, fit={fit_params}, sample={sample_params}, "
                f"rounding={enforce_rounding}, minmax={enforce_min_max}, masking={masking})"
            )

            processed_data = self.preprocess(data)
            self.logger.info(f"Preprocessed data shape: {processed_data.shape}")

            # Subclass fit() should consume already-preprocessed data (or ignore if not needed)
            self.fit(processed_data, seed, **fit_params)
            self.logger.info("Model fit complete.")

            # sample() may return DataFrame or list[DataFrame] (e.g., Synthpop for m>1)
            sampled = self.sample(n_samples, seed, **sample_params)
            if isinstance(sampled, list):
                self.logger.info(f"Sampled {len(sampled)} dataset(s).")
                # Postprocess each dataset if a list is returned
                post_list = []
                for i, sdf in enumerate(sampled, 1):
                    self.logger.info(f"Postprocessing dataset {i}")
                    post_list.append(
                        self.postprocess(
                            sdf,
                            original_data=data,  # original (unprocessed) data for constraints
                            data_ids=data_ids,
                            enforce_rounding=enforce_rounding,
                            enforce_min_max=enforce_min_max,
                            masking=masking,
                        )
                    )
                self.save_synthetic_data(post_list, output_filename, index=save_index)
                self.logger.info("Pipeline complete.")
                return post_list
            else:
                self.logger.info(f"Sampled {len(sampled)} rows.")
                processed_synthetic = self.postprocess(
                    sampled,
                    original_data=data,
                    data_ids=data_ids,
                    enforce_rounding=enforce_rounding,
                    enforce_min_max=enforce_min_max,
                    masking=masking,
                )
                self.logger.info(f"Postprocessed synthetic data. Final shape: {processed_synthetic.shape}")
                self.save_synthetic_data(processed_synthetic, output_filename, index=save_index)
                self.logger.info("Pipeline complete.")
                return processed_synthetic

        except Exception as e:
            self.logger.error(f"Error in full pipeline: {e}", exc_info=True)
            raise ValueError(f"Error in generating synthetic data: {e}")