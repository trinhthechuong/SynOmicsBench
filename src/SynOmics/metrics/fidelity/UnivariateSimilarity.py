import os
import sys
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from tqdm import tqdm

from sdmetrics.reports.single_table._properties import ColumnShapes
from SynOmics.processing.metadata import MetaData
from SynOmics.utils.monitoring import set_logger




class UnivariateSimilarity:
    """
    Compute and validate univariate similarity between original and synthetic data,
    including score computation, logging, result saving, and visualization.

    Args:
        output_dir (str): Directory to save outputs and logs.
        logger_name (str): Logger name
    Attributes:
        output_dir (str): Output directory path.
        column_shapes (ColumnShapes): SDMetrics ColumnShapes property.
        logger (logging.Logger): Logger for this class.
    """

    def __init__(self, output_dir: str, logger_name: str = "UnivariateSimilarity"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = set_logger(logger_name = logger_name, output_path = self.output_dir)
        self.logger_name = logger_name

        
    def get_univariate_score(self, original_data: pd.DataFrame,
                            synthetic_data: pd.DataFrame,
                            metadata: dict,
                            save: bool = True) -> float:
        """
        Compute univariate similarity score between original and synthetic data.

        Args:
            original_data (pd.DataFrame): Original data.
            synthetic_data (pd.DataFrame): Synthetic data.
            metadata_path (str): Path to SDMetrics metadata.
            save (bool): Save score dataframe and score distribution.

        Returns:
            float: Overall univariate similarity score.

        Raises:
            ValueError: If score computation fails.
        """
        try:
            self.logger.info("Starting univariate similarity computation.")
            self.column_shapes = ColumnShapes()
            metadata_sdmetrics = MetaData.metadata_as_SDV(data=original_data, metadata=metadata)
            with tqdm(total=len(metadata_sdmetrics['columns'])) as pbar:
                score = self.column_shapes.get_score(
                    original_data,
                    synthetic_data,
                    metadata_sdmetrics,
                    progress_bar=pbar
                )
            self.logger.info(f"Univariate similarity score: {score}")
            # Save details
            if save:
                details_df = self.get_detail_df()
                details_csv_path = os.path.join(self.output_dir, f"Detail_score_{self.logger_name}.csv")
                details_df.to_csv(details_csv_path, index = False)
                self.logger.info(f"Details DataFrame saved to {details_csv_path}")
                # Save visualization
                fig = self.plot_column_score_histogram(details_df, data_name = self.logger_name)
                fig_path = os.path.join(self.output_dir, f"{self.logger_name}.png")
                fig.savefig(fig_path, dpi=300)
                plt.close(fig)
                self.logger.info(f"Histogram figure saved to {fig_path}")
            return score
        except Exception as e:
            self.logger.error(f"Failed to validate the Univariate Similarity: {e}")
            raise ValueError(f"Failed to validate the Univariate Similarity: {e}")

    def get_detail_df(self):
        """
        Get the DataFrame with column-level univariate similarity details.

        Returns:
            pd.DataFrame: Details DataFrame.

        Raises:
            AttributeError: If column_shapes is not initialized.
        """
        if not hasattr(self, 'column_shapes'):
            raise AttributeError("column_shapes is not initialized. Run get_univariate_score first.")
        return self.column_shapes.details

    def summarize(self):
        """
        Summarize the scores by metric type.

        Returns:
            pd.DataFrame: Grouped summary statistics by metric.
        """
        detail_df = self.get_detail_df()
        return detail_df.groupby('Metric')['Score'].describe()

    def get_visualization(self, plotly: bool = False, data_name: str = "", bins: int = 50):
        """
        Get a visualization of the column shape scores.

        Args:
            plotly (bool): Whether to use Plotly for visualization.

        Returns:
            Figure: Matplotlib or Plotly figure.
        """
        details_df = self.get_detail_df()
        if plotly:
            return self.column_shapes.get_visualization()
        else:
            return self.plot_column_score_histogram(details_df, data_name, bins)

    @staticmethod
    def plot_column_score_histogram(details, data_name: str = "", bins: int = 50):
        """
        Plot a decorated histogram of column shape scores for a set of features.

        Args:
            details (pd.DataFrame): DataFrame containing at least a 'Score' column with numerical values.
            data_name (str): Optional label for the data (for title).
            bins (int): Number of bins for the histogram.

        Returns:
            matplotlib.figure.Figure: Figure object for saving or further manipulation.

        Raises:
            KeyError: If the 'Score' column is not present in the DataFrame.
            TypeError: If details is not a pandas DataFrame.
        """
        if not isinstance(details, pd.DataFrame):
            raise TypeError("details must be a pandas DataFrame.")
        if 'Score' not in details.columns:
            raise KeyError("The 'Score' column must be present in the details DataFrame.")

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot histogram only (no KDE)
        n, bins_, patches = ax.hist(
            details['Score'].dropna(),
            bins=bins,
            color='#4682B4',
            alpha=0.75,
            edgecolor='white',
            linewidth=1.2,
            label='Features'
        )

        # Add vertical lines for key statistics
        mean_score = details['Score'].mean()
        median_score = details['Score'].median()
        ax.axvline(mean_score, color='green', linestyle='--', linewidth=2, label=f'Mean: {mean_score:.2f}')
        ax.axvline(median_score, color='purple', linestyle='-.', linewidth=2, label=f'Median: {median_score:.2f}')

        # Customize ticks and grid
        ax.set_xticks(np.linspace(0, 1, 11))
        ax.tick_params(axis='x', labelsize=12)
        ax.tick_params(axis='y', labelsize=12)
        ax.grid(axis='y', alpha=0.3)

        # Add labels and title with font size and weight
        ax.set_xlabel('Score', fontsize=14, fontweight='bold')
        ax.set_ylabel('Number of Features', fontsize=14, fontweight='bold')
        ax.set_title(f'Distribution of Column Shape Scores {data_name}', fontsize=16, fontweight='bold', pad=20)

        # Add legend
        ax.legend(fontsize=12, frameon=True)

        # Add annotation for total features
        ax.annotate(
            f"Total features: {details['Score'].dropna().shape[0]}",
            xy=(0.99, 0.95), xycoords='axes fraction',
            ha='right', va='top', fontsize=12, color='gray'
        )

        plt.tight_layout()
        return fig