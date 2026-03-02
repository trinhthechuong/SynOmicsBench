import os
os.environ["R_HOME"] = "/opt/R/4.4.1/lib/R"
import rpy2.robjects as robjects
from rpy2.robjects import conversion, default_converter
from rpy2.robjects.pandas2ri import converter as pandas2ri_converter
from typing import Optional, Union
import subprocess
import re
import pandas as pd
import logging
import warnings
import sys
sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.processing.postprocessing import apply_min_max, apply_rounding, _detect_min_max_values, _detect_rounding_digits, anonymize_ids, load_metadata

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning)

class SynthpopSynthesizer:
    def __init__(
        self,
        output_path: str,
    ):
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Set the default log level to DEBUG

        # Create file handler for logging
        log_path = os.path.join(self.output_path, "SynthpopSynthesizer.log")
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)

        # Create formatter and add it to the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)

        # Add the handler to the logger (avoid duplicates)
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def _get_library_dir(self, R_terminal: str = "R") -> str:
        try:
            result = subprocess.run(
                [R_terminal, "-e", ".libPaths()"], capture_output=True, text=True
            )
            output = result.stdout
            match = re.search(r"\"(\/[^\"]+)\"", output)
            if match:
                lib_path = match.group(1)
                return str(lib_path)
            else:
                self.logger.error("No directory found in R output")
                raise ValueError("No directory found in R output.")
        except Exception as e:
            self.logger.error(f'Cannot find the library directory {e}')
            raise ValueError(f"Cannot find the library directory {e}")

    def generate_synthetic_data(self,
                                data: pd.DataFrame,
                                metadata_path: str,
                                R_terminal: str = "R",
                                data_ids: Optional[list] = None,
                                discrete_columns: Optional[list] = None,
                                numerical_columns: Optional[list] = None,
                                seed: int = 42,
                                enforce_rounding: bool = True,
                                enforce_min_max: bool = True,
                                method: str = 'cart',
                                minimumlevels: int = 3,
                                proper: bool = False,
                                n_datasets: int = 1, 
                                n_samples: Optional[Union[int, str]] = 'auto',
                                visit_sequence: Optional[list] = None,
                                cont_na: Optional[dict] = None,
                                verbose: bool = True,
                                predictor_matrix: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        # Validate input
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Input data must be a pandas DataFrame.")
        if not isinstance(data_ids, (list, type(None))):
            raise ValueError("data_ids must be a list or None.")
        if not isinstance(seed, int):
            raise ValueError("Seed must be an integer.")
        if not isinstance(enforce_rounding, bool):
            raise ValueError("enforce_rounding must be a boolean.")
        if not isinstance(enforce_min_max, bool):
            raise ValueError("enforce_min_max must be a boolean.")
        if not (isinstance(minimumlevels, int) and minimumlevels >= 1):
            raise ValueError("minimumlevels must be a positive integer.")
        if n_samples != 'auto' and (not isinstance(n_samples, int) or n_samples <= 0):
            raise ValueError("n_samples must be a positive integer or 'auto'.")
        if not isinstance(proper, bool):
            raise ValueError("proper must be a boolean.")
        if not (isinstance(n_datasets, int) and n_datasets >= 1):
            raise ValueError("n_datasets must be a positive integer.")
        if visit_sequence is not None and not isinstance(visit_sequence, list):
            raise ValueError("visit_sequence must be a list or None.")
        if cont_na is not None and not isinstance(cont_na, dict):
            raise ValueError("cont_na must be a dictionary or None.")
        if not os.path.exists(self.output_path):
            raise ValueError(f"Output path {self.output_path} does not exist. Please create the directory before running the synthesizer.")
        if n_samples == 'auto':
            n_samples = data.shape[0]

        # Validate metadata path
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found at {metadata_path}. Please run classify_feature_type function in Preprocess module.")
        self.logger.info(f"Loading metadata from {metadata_path}")

        # # Load metadata from the specified path
        # metadata = load_metadata(metadata_path)
        # self.logger.info("Metadata loaded successfully")

        # # Detect discrete columns
        # discrete_columns = _detect_discrete_columns(data, metadata)
        # self.logger.info(f"Detected discrete columns: {discrete_columns}")

        try:
            # Extended R code to accept predictorMatrix
            r_code = """
            library(dplyr)
            library(synthpop)
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

            r_lib_dir = f'.libPaths("{self._get_library_dir(R_terminal)}")'
            robjects.r(r_lib_dir)
            self.logger.info("Loaded R library")
            robjects.r(r_code)
            self.logger.info("Loaded R code")
            r_func = robjects.globalenv['create_synthetic_data']

            # Convert discrete_columns to R vector
            r_discrete_columns = robjects.StrVector(discrete_columns)
            # Convert visit_sequence to R vector or NULL
            r_visit_sequence = robjects.StrVector(visit_sequence) if visit_sequence else robjects.NULL
            # Convert cont_na to R list or NULL
            r_cont_na = robjects.ListVector(cont_na) if cont_na else robjects.NULL
            # Convert pandas DataFrame to R DataFrame
            with conversion.localconverter(default_converter + pandas2ri_converter):
                r_data = conversion.py2rpy(data)

            # Convert method to R string
            r_method = robjects.StrVector([method])
            # Convert proper to R logical
            r_proper = robjects.BoolVector([proper])
            # Convert verbose
            r_verbose = robjects.BoolVector([verbose])

            # Convert predictor matrix to R matrix (if provided)
            # --- Correct predictor matrix conversion ---
            if predictor_matrix is not None:
                if not isinstance(predictor_matrix, pd.DataFrame):
                    raise ValueError("predictor_matrix must be a pandas DataFrame if provided.")
                if not all(predictor_matrix.columns == data.columns) or not all(predictor_matrix.index == data.columns):
                    raise ValueError("predictor_matrix must have the same columns and index as the data DataFrame.")
                
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
                        None: robjects.StrVector(row_names),  # Row names
                        None: robjects.StrVector(col_names)   # Column names
                    })
                )
                
                r_predictor_matrix = r_matrix
            else:
                r_predictor_matrix = robjects.NULL
            # --- End predictor matrix conversion ---

            self.logger.info(f"Starting to synthesize {n_datasets} dataset(s) by Synthpop with method={method}, proper={proper}, minnumlevels={minimumlevels}")
            r_synthetic_data = r_func(
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
                predictorMatrix=r_predictor_matrix
            )

            # Handle single or multiple datasets
            if n_datasets == 1:
                with conversion.localconverter(default_converter + pandas2ri_converter):
                    synthetic_data = conversion.rpy2py(r_synthetic_data)
                if data_ids:
                    self.logger.info("Anonymizing IDs in synthetic data")
                    synthetic_data = anonymize_ids(ids=data_ids[:n_samples], 
                                                    synthetic_data=synthetic_data,
                                                    output_path=self.output_path)
                else:
                    self.logger.warning("No data IDs provided for anonymization. Skipping ID anonymization.")
                if enforce_min_max or enforce_rounding:
                    # numerical_columns = _detect_numerical_columns(data, metadata)
                    if enforce_rounding:
                        self.logger.info("Applying rounding to synthetic data")
                        rounding_digits = _detect_rounding_digits(data, numerical_columns)
                        synthetic_data = apply_rounding(synthetic_data, numerical_columns, rounding_digits)
                    if enforce_min_max:
                        self.logger.info("Detecting min-max values for numerical columns")
                        min_values, max_values = _detect_min_max_values(data, numerical_columns)
                        synthetic_data = apply_min_max(synthetic_data, numerical_columns, min_values, max_values)
                synthetic_data_path = os.path.join(
                    self.output_path, f"Synthpop_synthetic_data_{method}_proper_{proper}.csv"
                )
                synthetic_data.to_csv(synthetic_data_path, index=False)
                self.logger.info(f"Synthetic data generated by Synthpop using {method} method and proper={proper} saved at {synthetic_data_path}")
                return synthetic_data
            else:
                synthetic_data_list = []
                for i, synth_data in enumerate(r_synthetic_data):
                    with conversion.localconverter(default_converter + pandas2ri_converter):
                        synth_data_df = conversion.rpy2py(synth_data)
                    if data_ids:
                        self.logger.info(f"Anonymizing IDs in synthetic data {i+1}")
                        synth_data_df = anonymize_ids(ids=data_ids[:n_samples], 
                                                       synthetic_data=synth_data_df,
                                                       output_path=self.output_path)
                    else:
                        self.logger.warning("No data IDs provided for anonymization. Skipping ID anonymization.")
                    if enforce_min_max or enforce_rounding:
                        # numerical_columns = _detect_numerical_columns(data, metadata)
                        if enforce_rounding:
                            self.logger.info(f"Applying rounding to synthetic data {i+1}")
                            rounding_digits = _detect_rounding_digits(data, numerical_columns)
                            synth_data_df = apply_rounding(synth_data_df, numerical_columns, rounding_digits)
                        if enforce_min_max:
                            self.logger.info(f"Detecting min-max values for numerical columns in synthetic data {i+1}")
                            min_values, max_values = _detect_min_max_values(data, numerical_columns)
                            synth_data_df = apply_min_max(synth_data_df, numerical_columns, min_values, max_values)
                    synth_data_path = os.path.join(
                        self.output_path, f"Synthpop_synthetic_data_{method}_proper_{proper}_{i+1}.csv"
                    )
                    synth_data_df.to_csv(synth_data_path, index=False)
                    self.logger.info(f"Synthetic data {i+1} generated by Synthpop using {method} method and proper={proper} saved at {synth_data_path}")
                    synthetic_data_list.append(synth_data_df)
                return synthetic_data_list

        except Exception as e:
            self.logger.error(f"Error in generating synthetic data with Synthpop using {method} method and proper={proper}: {e}")
            raise ValueError(f"Error in generating synthetic data with Synthpop using {method} method and proper={proper}: {e}")