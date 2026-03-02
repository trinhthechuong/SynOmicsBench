import rpy2.robjects as robjects
from rpy2.robjects import conversion, default_converter
from rpy2.robjects.pandas2ri import converter as pandas2ri_converter
from typing import Optional, Union
import subprocess
import re
import os
import logging
import pandas as pd
import warnings
from .post_processing import _detect_discrete_columns, _detect_numerical_columns, apply_min_max, apply_rounding, _detect_min_max_values, _detect_rounding_digits, anonymize_ids, load_metadata

#Supressi specific warnings
warnings.filterwarnings("ignore", category=UserWarning)

class MICESynthesizer:
    def __init__(self,
                 output_path: str,
                 ):

        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)

        #Intialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        #Create file handler for logging
        log_path = os.path.join(self.output_path, "MICESynthesizer.log")
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)

        #Create formatter and add it to the handler
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)

        #Add the handler to the logger (avoid duplicates)
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
    
    def _get_library_dir(self, R_terminal: str)->str:
        try: 
            result = subprocess.run(
                [R_terminal, "-e", ".libPaths()"], capture_output=True, text=True
            )
            #The output of the command
            output = result.stdout
            #Extract the library path
            match = re.search(r"\"(\/[^\"]+)\"", output)
            if match:
                library_dir = match.group(1)
                return library_dir
            else:
                self.logger.error*("No directpry found in R output")
                raise ValueError("No directpry found in R output")
        except Exception as e:
            self.logger.error(f"Error getting library directory: {e}")
            raise ValueError(f"Error getting library directory: {e}")
    
    def generate_synthetic_data(self,
                                data: pd.DataFrame,
                                metadata_path: str, 
                                R_terminal: str = "R441",
                                data_ids: Optional[list] = None,
                                seed: int = 42,
                                enforce_rounding: bool = True,
                                enforce_min_max: bool = True,
                                method: str = "auto",
                                n_datasets: int = 1,
                                maxit: int = 5,
                                visit_sequence: Optional[list] = None,
                                verbose: bool = True,
                                n_cores: Optional[int] = None
                                ):
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
        if not isinstance(n_datasets, int) or n_datasets < 1:
            raise ValueError("n_datasets must be a positive integer.")
        if visit_sequence is not None and not isinstance(visit_sequence, list):
            raise ValueError("visit_sequence must be a list or None.")
        if not os.path.exists(self.output_path):
            raise ValueError(f"Output path {self.output_path} does not exist. Please create the directory before running the synthesizer.")


        if n_cores is None:
            n_cores = os.cpu_count() - 1

        # Validate metadata path
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found at {metadata_path}. Please run classify_feature_type function in Preprocess module.")
        self.logger.info(f"Loading metadata from {metadata_path}")

        # Load metadata from the specified path
        metadata = load_metadata(metadata_path)
        self.logger.info("Metadata loaded successfully")

        # Detect discrete columns
        discrete_columns = _detect_discrete_columns(data, metadata)
        self.logger.info(f"Detected discrete columns: {discrete_columns}")        
        
        
        try:
            r_code = """
            library(mice)
            library(dplyr)
            library(base)
            # library(future)
            # library(parlmice)

            create_synthetic_data <- function(data, seed, discreter_columns, 
                                            method, n_datasets, maxit, visit_sequence, n_cores, verbose) {
                
                cat_features <- discreter_columns
                cat_features <- trimws(cat_features)
                
                # Convert to factors
                data[cat_features] <- lapply(data[cat_features], factor)
                
                
                # Handle visit sequence
                if (is.null(visit_sequence)) {
                    visit_sequence <- colnames(data)
                } else {
                    visit_sequence <- trimws(visit_sequence)
                }
                
                where <- make.where(data, "all")
                
                # Choose method
                if (method == "auto") {
                    method <- make.method(data, where = where)
                }
                
                # Run futuremice
                syn_param <- mice(data, 
                                m = n_datasets, 
                                maxit = maxit,
                                method = method,
                                where = where,
                                seed = seed,
                                visitSequence = visit_sequence,
                                # n.core = n_cores,
                                printFlag = verbose)
        
                # Handle output
                if (n_datasets == 1) {
                    synthetic_data <- complete(syn_param, 1)
                    synthetic_data[] <- lapply(synthetic_data, function(x) {
                        if (is.factor(x)) as.character(x) else x
                    })
                    return(synthetic_data)
                } else {
                    synthetic_list <- lapply(1:n_datasets, function(i) {
                        df <- complete(syn_param, i)
                        df[] <- lapply(df, function(x) {
                            if (is.factor(x)) as.character(x) else x
                        })
                        return(df)
                    })
                    return(synthetic_list)
                }
            }
            """
            #load the library directory
            r_lib_dir = f'.libPaths("{self._get_library_dir(R_terminal)}")'
            robjects.r(r_lib_dir)
            self.logger.info("Loaded R library")
            robjects.r(r_code)
            self.logger.info("Loaded R code")
            r_func = robjects.globalenv["create_synthetic_data"]

            #Convert discrete columns to R vector
            r_discrete_columns = robjects.StrVector(discrete_columns)
            #Convert visit sequence to R vector if provided
            if visit_sequence is not None:
                r_visit_sequence = robjects.StrVector(visit_sequence)
            else:
                r_visit_sequence = robjects.NULL
            #Convert method to R string
            r_method = robjects.StrVector([method])

            r_verbose = robjects.BoolVector([verbose])

            self.logger.info(f"Starting to synthesize {n_datasets} dataset(s) by MICE with method={method}, maxit={maxit}")
            #Convert data to R DataFrame
            with conversion.localconverter(robjects.default_converter + pandas2ri_converter):
                r_data = conversion.py2rpy(data)
            

            r_synthetic_data = r_func(
                r_data,
                seed = seed,
                discreter_columns = r_discrete_columns,
                method = r_method,
                n_datasets = n_datasets,
                maxit = maxit,
                visit_sequence = r_visit_sequence,
                n_cores = robjects.IntVector([n_cores]),
                verbose = r_verbose
            )

            # Handle single or multiple datasets
            if n_datasets == 1:
                with conversion.localconverter(default_converter + pandas2ri_converter):
                    synthetic_data = conversion.rpy2py(r_synthetic_data)
                if data_ids:
                    self.logger.info("Anonymizing IDs in synthetic data")
                    synthetic_data = anonymize_ids(ids=data_ids, 
                                                    synthetic_data=synthetic_data,
                                                    output_path=self.output_path)
                else:
                    self.logger.warning("No data IDs provided for anonymization. Skipping ID anonymization.")
                if enforce_min_max or enforce_rounding:
                    numerical_columns = _detect_numerical_columns(data, metadata)
                    if enforce_rounding:
                        self.logger.info("Applying rounding to synthetic data")
                        rounding_digits = _detect_rounding_digits(data, numerical_columns)
                        synthetic_data = apply_rounding(synthetic_data, numerical_columns, rounding_digits)
                    if enforce_min_max:
                        self.logger.info("Detecting min-max values for numerical columns")
                        min_values, max_values = _detect_min_max_values(data, numerical_columns)
                        synthetic_data = apply_min_max(synthetic_data, numerical_columns, min_values, max_values)
                synthetic_data_path = os.path.join(
                    self.output_path, f"Synthpop_synthetic_data_{method}.csv"
                )
                synthetic_data.to_csv(synthetic_data_path, index=False)
                self.logger.info(f"Synthetic data generated by Synthpop using {method} method saved at {synthetic_data_path}")
                return synthetic_data
            else:
                synthetic_data_list = []
                for i, synth_data in enumerate(r_synthetic_data):
                    with conversion.localconverter(default_converter + pandas2ri_converter):
                        synth_data_df = conversion.rpy2py(synth_data)
                    if data_ids:
                        self.logger.info(f"Anonymizing IDs in synthetic data {i+1}")
                        synth_data_df = anonymize_ids(ids=data_ids, 
                                                       synthetic_data=synth_data_df,
                                                       output_path=self.output_path)
                    else:
                        self.logger.warning("No data IDs provided for anonymization. Skipping ID anonymization.")
                    if enforce_min_max or enforce_rounding:
                        numerical_columns = _detect_numerical_columns(data, metadata)
                        if enforce_rounding:
                            self.logger.info(f"Applying rounding to synthetic data {i+1}")
                            rounding_digits = _detect_rounding_digits(data, numerical_columns)
                            synth_data_df = apply_rounding(synth_data_df, numerical_columns, rounding_digits)
                        if enforce_min_max:
                            self.logger.info(f"Detecting min-max values for numerical columns in synthetic data {i+1}")
                            min_values, max_values = _detect_min_max_values(data, numerical_columns)
                            synth_data_df = apply_min_max(synth_data_df, numerical_columns, min_values, max_values)
                    synth_data_path = os.path.join(
                        self.output_path, f"Synthpop_synthetic_data_{method}_{i+1}.csv"
                    )
                    synth_data_df.to_csv(synth_data_path, index=False)
                    self.logger.info(f"Synthetic data {i+1} generated by Synthpop using {method} method saved at {synth_data_path}")
                    synthetic_data_list.append(synth_data_df)
                return synthetic_data_list
            
        except Exception as e:
            self.logger.error(f"Error in generating synthetic data with MICE: {e}")
            raise ValueError(f"Error in generating synthetic data with MICE: {e}")