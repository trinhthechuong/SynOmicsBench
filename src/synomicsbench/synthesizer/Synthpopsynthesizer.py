import os
from typing import List, Optional, Union
import pandas as pd
import warnings
# os.environ["R_HOME"] = "/opt/R/4.4.1/lib/R"
from rpy2.robjects import conversion, default_converter
import rpy2.robjects as robjects
from rpy2.robjects.pandas2ri import converter as pandas2ri_converter

from synomicsbench.synthesizer.BaseSynthesizer import BaseSynthesizer

warnings.filterwarnings("ignore", category=UserWarning)


class SynthpopSynthesizer(BaseSynthesizer):
    """
    SynthpopSynthesizer for generating synthetic data using Synthpop (R) via rpy2.

    This implementation aligns with BaseSynthesizer:
      - preprocess: pass-through by default
      - fit: stores the training DataFrame for the R call
      - sample: calls R's synthpop::syn, returns a DataFrame or list of DataFrames (for m > 1)
      - postprocess: anonymize IDs, rounding, min-max; works for single or multiple datasets via BaseSynthesizer.generate

    Args:
        output_path (str): Directory where outputs are saved.
        metadata (dict, optional): Column-type metadata. Keys are column names, values are
            one of 'dummy_categorical', 'ordinal_categorical', 'missing_categorical', or a numeric type string.
        r_home (str, optional): Path to R_HOME. If provided, sets os.environ['R_HOME'] at init.
        r_terminal (str, optional): R executable name or path used to configure library search paths. Default 'R'.
    """

    def __init__(
        self,
        output_path: str,
        metadata: Optional[dict] = None,
        r_home: Optional[str] = None,
        r_terminal: str = "R",
    ) -> None:
        super().__init__(output_path=output_path, metadata=metadata)
        if r_home:
            os.environ["R_HOME"] = r_home
            self.logger.info(f"R_HOME set to: {r_home}")
        self.r_terminal = r_terminal
        self._train_df: Optional[pd.DataFrame] = None

    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess input data for Synthpop (default: pass-through).

        Args:
            data (pd.DataFrame): Input data.

        Returns:
            pd.DataFrame: Preprocessed data (unchanged).
        """
        return data

    def fit(self, data: pd.DataFrame, seed: int = 42, **kwargs) -> None:
        """
        Store the training data for later use in sample().

        Args:
            data (pd.DataFrame): Preprocessed training data.
            **kwargs: Unused; for API compatibility.

        Returns:
            None
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Input 'data' must be a non-empty pandas DataFrame.")
        seed = seed
        self._train_df = data.copy()
        self.logger.info(f"Stored training data for Synthpop with shape {self._train_df.shape}")

    def _ensure_r_libpath(self) -> None:
        """
        Ensure R library path is available in the current session by forwarding .libPaths().
        """
        # If user provides a custom lib path (via R), we can augment here by querying from R.
        # Many environments work without overriding .libPaths(), so we keep this minimal.
        try:
            robjects.r(".libPaths()")  # no-op, ensures R is alive
        except Exception as e:
            self.logger.warning(f"Could not query R library paths: {e}")

    def sample(
        self,
        n_samples: Union[int, str] = "auto",
        seed: int = 42,
        *,
        discrete_columns: Optional[List[str]] = None,
        method: str = "cart",
        minimumlevels: int = 3,
        proper: bool = False,
        n_datasets: int = 1,
        visit_sequence: Optional[List[str]] = None,
        cont_na: Optional[dict] = None,
        verbose: bool = True,
        predictor_matrix: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> Union[pd.DataFrame, List[pd.DataFrame]]:
        """
        Call R's synthpop::syn to generate synthetic data.

        Args:
            n_samples (int or 'auto'): Number of rows to synthesize; 'auto' uses training size.
            discrete_columns (list[str], optional): categorical columns.
            method (str): Synthpop synthesis method (e.g., 'cart', 'parametric', ...).
            minimumlevels (int): Minimum levels for categorical variables.
            proper (bool): Proper synthesis flag.
            n_datasets (int): Number of synthetic datasets (m).
            visit_sequence (list[str], optional): Variable visit sequence.
            cont_na (dict, optional): Settings for NA handling of continuous variables.
            seed (int): Random seed for reproducibility on the R side.
            verbose (bool): Verbosity for R synthpop.
            predictor_matrix (pd.DataFrame, optional): Square 0/1 matrix restricting predictors.
                Must have the same index and columns as training data columns.
            

        Returns:
            pd.DataFrame or list[pd.DataFrame]: Synthetic dataset(s).

        Raises:
            RuntimeError: If R synthesis fails.
            ValueError: If fit() has not been called or inputs are invalid.
        """
        if self._train_df is None:
            raise ValueError("Call fit(data) before sample().")
        df = self._train_df.reset_index(drop=True)

        # Resolve n_samples
        if n_samples == "auto":
            n_samples = df.shape[0]
        if not isinstance(n_samples, int) or n_samples <= 0:
            raise ValueError("n_samples must be a positive integer or 'auto'.")

        # Resolve discrete columns
        # disc_cols = self._build_discrete_columns(df, override=discrete_columns)

        # Validate predictor_matrix
        r_predictor_matrix = robjects.NULL
        if predictor_matrix is not None:
            if not isinstance(predictor_matrix, pd.DataFrame):
                raise ValueError("predictor_matrix must be a pandas DataFrame if provided.")
            if list(predictor_matrix.columns) != list(df.columns) or list(predictor_matrix.index) != list(df.columns):
                raise ValueError("predictor_matrix must have the same columns and index as the training DataFrame.")
                # Extract row and column names
            row_names = list(predictor_matrix.index)
            col_names = list(predictor_matrix.columns)
            
            # Extract matrix values and convert to R-compatible format
            pm_np = predictor_matrix.values.astype(int)
            nr, nc = pm_np.shape
            r_values = robjects.IntVector(pm_np.flatten(order='F'))
            
            # Create the R matrix
            r_matrix = robjects.r['matrix'](r_values, nrow=nr, ncol=nc)
            
            # Assign dimnames (row and column names) to the matrix
            r_matrix.do_slot_assign(
                "dimnames",
                robjects.ListVector({
                    "row.names": robjects.StrVector(row_names),
                    "col.names": robjects.StrVector(col_names)
                })
            )
            
            r_predictor_matrix = r_matrix
        else:
            r_predictor_matrix = robjects.NULL
            
        # R helper for synthesis
        r_code = """
        suppressPackageStartupMessages(library(synthpop))
        library(dplyr)
        create_synthetic_data <- function(data, seed, discrete_columns, minnumlevels, 
                                       method, proper, m, k, visit_sequence, cont_na, verbose, predictorMatrix = NULL) {
                cat_features <- discrete_columns
                cat_features <- trimws(cat_features)
                data[cat_features] <- lapply(data[cat_features], factor)

                if (is.null(visit_sequence)) {
                    visit_seq <- colnames(data)
                } else {
                    visit_seq <- trimws(visit_sequence)
                }

                if (is.null(cont_na)) {
                    cont_na <- NULL
                }

                set.seed(seed)
                synthpop_clinical_res <- syn(
                    data, 
                    minnumlevels = minnumlevels,
                    method = method,
                    proper = proper,
                    m = m,
                    k = if (is.null(k)) nrow(data) else k,
                    visit.sequence = visit_seq,
                    cont.na = cont_na,
                    print.flag = verbose,
                    predictor.matrix = predictorMatrix
                )

                if (m > 1) {
                    synth_data <- synthpop_clinical_res$syn
                } else {
                    synth_data <- synthpop_clinical_res$syn
                }

                # Convert factors to characters before returning to Python
                if (m > 1) {
                    synth_data <- lapply(synth_data, function(df) {
                        df[] <- lapply(df, function(x) {
                            if (is.factor(x)) as.character(x) else x
                        })
                        return(df)
                    })
                } else {
                    synth_data[] <- lapply(synth_data, function(x) {
                        if (is.factor(x)) as.character(x) else x
                    })
                }
                return(synth_data)
            }
            """

        try:
            # Ensure R lib path callable (no-op if not needed)
            self._ensure_r_libpath()

            # Load helper into R
            robjects.r(r_code)
            r_func = robjects.globalenv["create_synthetic_data"]

            # Prepare R args
            r_discrete_columns = robjects.StrVector(discrete_columns)
            r_visit_sequence = robjects.StrVector(visit_sequence) if visit_sequence else robjects.NULL
            r_cont_na = robjects.ListVector(cont_na) if cont_na else robjects.NULL

            with conversion.localconverter(default_converter + pandas2ri_converter):
                r_data = conversion.py2rpy(df)

            r_method = robjects.StrVector([method])
            r_proper = robjects.BoolVector([proper])
            r_verbose = robjects.BoolVector([verbose])

            self.logger.info(
                f"Running Synthpop (method={method}, proper={proper}, m={n_datasets}, k={n_samples}, "
                f"minnumlevels={minimumlevels}, seed={seed})"
            )

            r_out = r_func(
                r_data,
                seed=seed,
                discrete_columns=r_discrete_columns,
                minnumlevels=minimumlevels,
                method=r_method,
                proper=r_proper,
                m=n_datasets,
                k=n_samples,
                visit_sequence=r_visit_sequence,
                cont_na=r_cont_na,
                verbose=r_verbose,
                predictorMatrix=r_predictor_matrix,
            )

            if n_datasets == 1:
                with conversion.localconverter(default_converter + pandas2ri_converter):
                    synthetic_df = conversion.rpy2py(r_out)
                self.logger.info(f"Synthpop generated 1 dataset with shape {synthetic_df.shape}")
                return synthetic_df
            else:
                out_list: List[pd.DataFrame] = []
                for i, r_df in enumerate(r_out, start=1):
                    with conversion.localconverter(default_converter + pandas2ri_converter):
                        pdf = conversion.rpy2py(r_df)
                    self.logger.info(f"Synthpop dataset {i}/{n_datasets} shape: {pdf.shape}")
                    out_list.append(pdf)
                return out_list

        except Exception as e:
            raise RuntimeError(f"Synthpop synthesis failed: {e}")

    # def postprocess(
    #     self,
    #     synthetic_data: Union[pd.DataFrame, List[pd.DataFrame]],
    #     original_data: pd.DataFrame,
    #     data_ids: Optional[List[str]] = None,
    #     enforce_rounding: bool = True,
    #     enforce_min_max: bool = True,
    #     masking: bool = False,
    # ) -> Union[pd.DataFrame, List[pd.DataFrame]]:
    #     """
    #     Postprocess Synthpop outputs (single DataFrame or list):
    #       - anonymize IDs (optional),
    #       - apply rounding/min-max constraints for numerical columns inferred from metadata,
    #       - optional masking hook.

    #     Args:
    #         synthetic_data (DataFrame or list[DataFrame]): Synthetic data to process.
    #         original_data (DataFrame): Original data used to derive constraints.
    #         data_ids (list[str], optional): If provided, will anonymize IDs in outputs.
    #         enforce_rounding (bool): Apply rounding to numeric columns.
    #         enforce_min_max (bool): Clip numeric columns to min/max from original_data.
    #         masking (bool): If True and mask_func provided, apply mask_func(df) -> df.
    #         mask_func (callable, optional): Masking function applied after constraints.

    #     Returns:
    #         DataFrame or list[DataFrame]: Postprocessed synthetic data.
    #     """
    #     def _process_one(df: pd.DataFrame) -> pd.DataFrame:
    #         sdf = df.copy()

    #         # Anonymize IDs
    #         if data_ids:
    #             print("Debugging")
    #             self.logger.info("Anonymizing IDs in synthetic data")
    #             sdf = self.anonymize_ids(data_ids[: len(sdf)], sdf)
    #         else:
    #             self.logger.info("No data IDs provided. Skipping ID anonymization.")

    #         # Numeric constraints based on metadata
    #         if self.metadata is not None and (enforce_rounding or enforce_min_max):
    #             num_cols = self.detect_numerical_columns(original_data)
    #             if num_cols:
    #                 if enforce_rounding:
    #                     rounding_digits = self.detect_rounding_digits(original_data, num_cols)
    #                     sdf = self.apply_rounding(sdf, num_cols, rounding_digits)
    #                 if enforce_min_max:
    #                     min_vals, max_vals = self.detect_min_max_values(original_data, num_cols)
    #                     sdf = self.apply_min_max(sdf, num_cols, min_vals, max_vals)

    #         # Optional masking
    #         if masking:
    #             try:
    #                 sdf = post_masking(sdf)
    #             except Exception as e:
    #                 self.logger.warning(f"Masking function failed: {e}")

    #         # Align to original column order when possible
    #         common_cols = [c for c in original_data.columns if c in sdf.columns]
    #         if common_cols:
    #             sdf = sdf[common_cols]
    #         return sdf

    #     if isinstance(synthetic_data, list):
    #         return [_process_one(df) for df in synthetic_data]
    #     else:
    #         return _process_one(synthetic_data)