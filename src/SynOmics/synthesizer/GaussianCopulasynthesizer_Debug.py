import pandas as pd
import numpy as np
import os 
import logging
import json
from datetime import datetime
from sklearn.preprocessing import OrdinalEncoder
# from SynOmics.synthesizer.GaussianMultivariate_Parallel import GaussianMultivariate_Parallel
from copulas.multivariate import GaussianMultivariate

from SynOmics.utils.monitoring import set_logger
from SynOmics.synthesizer.BaseSynthesizer import BaseSynthesizer
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
import pickle

class GaussianCopulasynthesizer(BaseSynthesizer):
    """
    GaussianCopulasynthesizer for generating synthetic data using a Gaussian Copula model.

    This refactor aligns the class with BaseSynthesizer:
      - preprocess: encodes categorical variables (dummy + ordinal) and keeps numerical/missing indicators
      - fit: trains GaussianMultivariate_Parallel on preprocessed data
      - sample: draws synthetic samples
      - postprocess: decodes categorical variables, enforces constraints, anonymizes IDs

    Notes:
      - Metadata must be provided as a dictionary to the constructor or via set_metadata():
          {
              "col_name": "ordinal_categorical" | "dummy_categorical" | "missing_categorical" | <other for numerical>
          }
      - Ordinal variables are encoded using sklearn's OrdinalEncoder (0..n_levels-1).
        During postprocess, synthetic ordinal columns are rounded and clipped to valid ranges
        derived from encoder categories, then inverse-transformed.
    """

    def encode_dummy_cat_features(self,data: pd.DataFrame) -> pd.DataFrame:
        """
        One-hot encode the provided categorical columns (no drop-first, no dummy for NaN).
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrecame")
        try:
            # self.logger.info(f"Dummy encoding {data.shape[1]} features")
            cat_data_encoded = pd.get_dummies(
                data, dtype="int64", dummy_na=False, columns=data.columns
            )
            return cat_data_encoded
        except Exception as e:
            raise ValueError(f"Error encoding categorical features: {e}")

    def encode_ordinal_cat_features(self, data: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")
        try:
            # self.logger.info(f"Ordinal encoding {data.shape[1]} features")
            self._ordinal_encoder = OrdinalEncoder()
            encoded_values = self._ordinal_encoder.fit_transform(data)
            df_ordinal_encoded = pd.DataFrame(encoded_values, columns=data.columns, index = data.index)
            self._ordinal_valid_max = {
                col: len(cats) - 1 for col, cats in zip(data.columns, self._ordinal_encoder.categories_)
            }
            return df_ordinal_encoded
        except Exception as e:
            raise ValueError(f"Error encoding ordinal categorical features: {e}")
    
            
    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess input data for Gaussian Copula synthesizer.

        - Splits columns by type using self.metadata
        - One-hot encodes dummy categorical columns
        - Ordinal-encodes ordinal categorical columns
        - Keeps numerical and missing indicator columns unchanged

        Args:
            data (pd.DataFrame): The input DataFrame.

        Returns:
            pd.DataFrame: Preprocessed DataFrame.

        Raises:
            ValueError: If metadata is not set.
        """
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before preprocessing.")

        # Identify columns by type from metadata and present in data
        self._dummy_cat_cols: List[str] = [
            col for col, typ in self.metadata.items() if typ == "dummy_categorical" and col in data.columns
        ]
        self._ordinal_cat_cols: List[str] = [
            col for col, typ in self.metadata.items() if typ == "ordinal_categorical" and col in data.columns
        ]
        self._missing_indicator_cols: List[str] = [
            col for col, typ in self.metadata.items() if typ == "missing_categorical" and col in data.columns
        ]
        # Everything else present in data is considered numerical
        self._num_cols: List[str] = [
            col for col in data.columns
            if col not in set(self._dummy_cat_cols + self._ordinal_cat_cols + self._missing_indicator_cols)
        ]

        # Encode dummy categorical features
        if self._dummy_cat_cols:
            dummy_cat_encoded_df = self.encode_dummy_cat_features(data[self._dummy_cat_cols])
        else:
            dummy_cat_encoded_df = pd.DataFrame(index=data.index)

        # Encode ordinal categorical features
        if self._ordinal_cat_cols:
            ordinal_cat_cols_encoded_df = self.encode_ordinal_cat_features(data[self._ordinal_cat_cols])
        else:
            ordinal_cat_cols_encoded_df = pd.DataFrame(index=data.index)
            self._ordinal_encoder = None
            self._ordinal_valid_max = {}

        # Keep other columns (numerical and missing indicators)
        drop_cols = self._dummy_cat_cols + self._ordinal_cat_cols
        num_missing_indicators_df = data.drop(columns=drop_cols) if drop_cols else data.copy()

        # Concatenate all processed columns
        processed_data = pd.concat(
            [num_missing_indicators_df, dummy_cat_encoded_df, ordinal_cat_cols_encoded_df], axis=1
        )

        self.logger.info(
            f"Preprocess summary: num={len(self._num_cols)}, dummy={len(self._dummy_cat_cols)}, "
            f"ordinal={len(self._ordinal_cat_cols)}, missing_ind={len(self._missing_indicator_cols)}. "
            f"Processed shape: {processed_data.shape}"
        )
        return processed_data
        
    def fit(self, 
            data: pd.DataFrame,
            seed: Optional[int] = None,
            n_jobs: int = 8, 
            chunk_size: int = 20, 
            **kwargs) -> None:
        """
        Train the Gaussian Copula model on preprocessed data.

        Args:
            data (pd.DataFrame): Preprocessed DataFrame (output of preprocess()).
            n_jobs (int): Number of parallel worker threads.
            chunk_size (int): Chunk size for parallel fitting.
            **kwargs: Extra GaussianMultivariate_Parallel parameters.

        Returns:
            None
        """
        self.logger.info(
            f"Starting fitting Gaussian Copula Synthesizer by {n_jobs} threads with chunk size {chunk_size}"
        )
        nested = kwargs.pop("kwargs", None)
        if nested is not None:
            if not isinstance(nested, dict):
                self.logger.warning("The 'kwargs' entry in fit_params is not a dict and will be ignored.")
            else:
                # Merge nested kwargs with top-level kwargs. Nested keys override top-level ones.
                kwargs = {**kwargs, **nested}
                
        # self.model = GaussianMultivariate_Parallel(n_jobs=n_jobs, chunk_size=chunk_size, **kwargs)
        self.model = GaussianMultivariate()
        self.model.fit(data)

        # Save model to disk
        model_path = os.path.join(self.output_path, "GaussianCopula_model.pkl")
        try:
            with open(model_path, "wb") as f:
                pickle.dump(self.model, f)
            self.logger.info(f"Saved Gaussian Copula model to {model_path}")
        except Exception as e:
            self.logger.warning(f"Could not save Gaussian Copula model: {e}")

    def sample(self, 
               n_samples: int = 10, 
               seed: Optional[int] = None, 
               **kwargs) -> pd.DataFrame:
        """
        Generate synthetic samples from fitted Gaussian Copula model.

        Args:
            n_samples (int): Number of samples to generate.
            seed (int): Random seed for reproducibility.
            **kwargs: Extra parameters for model.sample().

        Returns:
            pd.DataFrame: Synthetic samples.

        Raises:
            ValueError: If model is not fitted.
        """
        if not hasattr(self, "model") or self.model is None:
            self.logger.error("Model is not fitted. Call fit() first.")
            raise ValueError("Model is not fitted. Call fit() first.")
        try:
            self.model.set_random_state(seed)
        except Exception:
            pass
        synthetic_data = self.model.sample(num_rows=n_samples, **kwargs)
        self.logger.info(f"Generated {n_samples} synthetic samples with Gaussian Copula")
        return synthetic_data
        
    def inverse_dummy_cat_features(self, data: pd.DataFrame, dummy_cat_columns: list) -> pd.DataFrame:
        """
        Inverse-transform one-hot encoded dummy categorical columns back to single categorical columns.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input data must be a pandas DataFrame")
        if not isinstance(dummy_cat_columns, list) or not dummy_cat_columns:
            raise TypeError("dummy_cat_columns must be a non-empty list of column names")
        try:
            # self.logger.debug("Inverse encoding dummy categorical features")
            out = data.copy()
            cat_features_dict = {}
            for cat_feature in dummy_cat_columns:
                for column in data.columns:
                    if column.startswith(cat_feature):
                        cat_features_dict[cat_feature] = cat_features_dict.get(
                            cat_feature, []
                        ) + [column]
            for feature, cols in cat_features_dict.items():
                out[feature] = np.array(cols)[out[cols].to_numpy().argmax(axis=1)]
                out[feature] = out[feature].str.replace(f"{feature}_", "")
                out.drop(columns=cols, inplace=True)
            out = out[dummy_cat_columns].astype("category")
            return out
        except Exception as e:
            raise ValueError(f"Error in inversing encoding categorical features: {e}")

    def inverse_ordinal_cat_features(self, data: pd.DataFrame, ordinal_cat_columns: list) -> pd.DataFrame:
        """
        Perform inverse ordinal encoding on categorical features.
        """
        if not hasattr(self, "_ordinal_encoder") or self._ordinal_encoder is None:
            raise AttributeError("Ordinal encoder not initialized. Run encode_ordinal_cat_features first")
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input data must be a pandas DataFrame")
        try:
            # self.logger.debug("Inverse encoding ordinal categorical features")
            df = data.copy()
            for col in ordinal_cat_columns:
                df[col] = np.round(df[col]).astype(int)
                # Clip to valid range [0, n_levels-1] based on fitted encoder
                vmax = self._ordinal_valid_max.get(col, None)
                if vmax is not None:
                    df[col] = df[col].clip(lower=0, upper=vmax)
            
            inv = pd.DataFrame(
            self._ordinal_encoder.inverse_transform(df[ordinal_cat_columns]),
            columns=ordinal_cat_columns,
            index=df.index,
        )  
            return inv
        except Exception as e:
            raise ValueError(f"Error in inversing ordinal encoding: {e}")

    def inverse_missing_indicators(self, data: pd.DataFrame, missing_indicators: List[str]) -> pd.DataFrame:
        """
        Threshold missing indicator columns at 0.5 and cast to float.
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Input data must be a pandas DataFrame")
        if not isinstance(missing_indicators, list):
            raise TypeError("missing_indicators must be a list of column names")
        try:
            out = data.copy()
            for col in missing_indicators:
                if col in out.columns:
                    out[col] = (out[col] > 0.5).astype(float)
            return out
        except Exception as e:
            raise ValueError(f"Error in inversing missing indicators: {e}")
     
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
        Inverse the encodings back to original space, then delegate anonymization, rounding,
        min-max clipping, and optional masking to BaseSynthesizer.postprocess.
        """
        try:
            sdf = synthetic_data.copy()

            # 1) Inverse dummy categorical features
            if getattr(self, "_dummy_cat_cols", []):
                dummy_prefixes = [f"{c}_" for c in self._dummy_cat_cols]
                dummy_cols_present = [c for c in sdf.columns if any(c.startswith(p) for p in dummy_prefixes)]
                inv_dummy_df = (
                    self.inverse_dummy_cat_features(sdf[dummy_cols_present], self._dummy_cat_cols)
                    if dummy_cols_present
                    else pd.DataFrame(index=sdf.index)
                )
            else:
                inv_dummy_df = pd.DataFrame(index=sdf.index)

            # 2) Inverse ordinal categorical features
            if getattr(self, "_ordinal_cat_cols", []) and getattr(self, "_ordinal_encoder", None) is not None:
                ord_slice = (
                    sdf[self._ordinal_cat_cols].copy()
                    if set(self._ordinal_cat_cols).issubset(sdf.columns)
                    else pd.DataFrame(index=sdf.index)
                )
                ord_slice = ord_slice.reindex(columns=self._ordinal_cat_cols, fill_value=0)
                inv_ord_df = self.inverse_ordinal_cat_features(ord_slice, self._ordinal_cat_cols)
            else:
                inv_ord_df = pd.DataFrame(index=sdf.index)

            # 3) Inverse missing indicators
            if getattr(self, "_missing_indicator_cols", []):
                miss_slice = (
                    sdf[self._missing_indicator_cols].copy()
                    if set(self._missing_indicator_cols).issubset(sdf.columns)
                    else pd.DataFrame(index=sdf.index)
                )
                miss_slice = miss_slice.reindex(columns=self._missing_indicator_cols, fill_value=0.0)
                inv_miss_df = self.inverse_missing_indicators(miss_slice, self._missing_indicator_cols)
            else:
                inv_miss_df = pd.DataFrame(index=sdf.index)

            # 4) Numeric slice
            num_slice_cols = [c for c in getattr(self, "_num_cols", []) if c in sdf.columns]
            num_slice = sdf[num_slice_cols].copy() if num_slice_cols else pd.DataFrame(index=sdf.index)

            # 5) Concatenate back to "original space"
            inverse_full = pd.concat([num_slice, inv_miss_df, inv_ord_df, inv_dummy_df], axis=1)

            # Reorder columns to match original_data first, then append any extras
            common_cols = [col for col in original_data.columns if col in inverse_full.columns]
            inverse_full = inverse_full.reindex(
                columns=common_cols + [c for c in inverse_full.columns if c not in common_cols]
            )

            # Delegate rounding/min-max/anonymization/masking to the base class
            processed = super().postprocess(
                synthetic_data=inverse_full,
                original_data=original_data,
                data_ids=data_ids,
                enforce_rounding=enforce_rounding,
                enforce_min_max=enforce_min_max,
                masking=masking,
            )
            return processed
        except Exception as e:
            raise ValueError(f"Error in post-processing synthetic data: {e}")


            


    
