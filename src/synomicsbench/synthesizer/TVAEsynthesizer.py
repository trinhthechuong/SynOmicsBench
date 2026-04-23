import pandas as pd
import os
from ctgan import TVAE
from synomicsbench.synthesizer.BaseSynthesizer import BaseSynthesizer
import random
import numpy as np
from typing import Optional


class TVAEsynthesizer(BaseSynthesizer):
    """
    TVAEsynthesizer for generating synthetic data using TVAE.

    Args:
        output_path (str): Path to save outputs.
        metadata (dict, optional): Metadata dictionary containing column type information.

    Methods:
        fit: Train the TVAE model.
        sample: Generate synthetic samples.
        postprocess: Apply postprocessing (anonymize IDs, rounding, scaling).
        generate: Orchestrate data synthesis pipeline.
    """

    def _seed_all(self, seed: Optional[int] = None, use_cuda: bool = False) -> None:
        """Seed Python, NumPy, and Torch (if available) to improve reproducibility."""
        if seed is None:
            return
        random.seed(seed)
        np.random.seed(seed)
        try:
            import torch
            torch.manual_seed(seed)
            if use_cuda and torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except Exception:
            # Torch not installed or not available; ignore
            pass

    def fit(self, 
            data: pd.DataFrame, 
            seed:  Optional[int] = None,
            *,
            epochs: int = 100, 
            verbose: bool = True, 
            cuda: bool = True, 
            **kwargs):
        """
        Train the TVAE model on provided data.

        Args:
            data (pd.DataFrame): DataFrame for training.
            epochs (int): Number of training epochs.
            verbose (bool): Verbosity flag.
            cuda (bool): Use GPU if True.
            seed (int, optional): Random seed for reproducibility.
            **kwargs: Extra TVAE parameters.

        Returns:
            None

        Raises:
            ValueError: If metadata is not set, input is invalid, or fitting fails.
        """
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before fitting the model.")
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Input 'data' must be a non-empty pandas DataFrame.")

        discrete_columns = self.detect_discrete_columns(data)
        self.logger.info(f"Detected discrete columns: {discrete_columns}")
        self.logger.info(f"Starting TVAE training (epochs={epochs}, cuda={cuda}, verbose={verbose}, seed={seed})")

        nested = kwargs.pop("kwargs", None)
        if nested is not None:
            if not isinstance(nested, dict):
                self.logger.warning("The 'kwargs' entry in fit_params is not a dict and will be ignored.")
            else:
                # Merge nested kwargs with top-level kwargs. Nested keys override top-level ones.
                kwargs = {**kwargs, **nested}
        # Seed everything we can
        self._seed_all(seed, use_cuda=cuda)

        self.model = TVAE(
            epochs=epochs,
            verbose=verbose,
            cuda=cuda,
            **kwargs
        )

        # Some TVAE builds support setting RNG state before training
        try:
            if seed is not None and hasattr(self.model, "set_random_state"):
                self.model.set_random_state(seed)
        except Exception:
            pass

        self.model.fit(data, discrete_columns=discrete_columns)
        self.logger.info("TVAE training completed")

        model_path = os.path.join(self.output_path, "TVAE_model.pkl")
        try:
            self.model.save(model_path)
            self.logger.info(f"Saved TVAE model to {model_path}")
        except Exception as e:
            self.logger.warning(f"Could not save TVAE model: {e}")

    def sample(self, n_samples: int = 10, 
               seed: Optional[int] = None, 
               **kwargs) -> pd.DataFrame:
        """
        Generate synthetic samples from fitted TVAE model.

        Args:
            n_samples (int): Number of samples to generate.
            seed (int): Random seed for reproducibility during sampling.
            **kwargs: Extra parameters for model.sample().

        Returns:
            pd.DataFrame: Synthetic samples.

        Raises:
            ValueError: If model not fitted or sampling fails.
        """
        if not hasattr(self, "model") or self.model is None:
            self.logger.error("Model is not fitted. Call fit() first.")
            raise ValueError("Model is not fitted. Call fit() first.")

        # Seed all relevant RNGs
        self._seed_all(seed, use_cuda=getattr(self.model, "cuda", False))

        # Also try to set model RNG if supported
        try:
            if hasattr(self.model, "set_random_state"):
                self.model.set_random_state(seed)
        except Exception:
            pass

        synthetic_data = self.model.sample(n_samples, **kwargs)
        self.logger.info(f"Generated {n_samples} synthetic samples")
        return synthetic_data