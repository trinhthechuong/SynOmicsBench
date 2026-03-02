# BaseSynthesizer API

The `BaseSynthesizer` class is the core component of SynOmicBench. It provides a consistent, unified interface for all data synthesis workflows. By inheriting from this base class, different synthesis algorithms can easily be integrated into the benchmark pipeline.

## Class Definition

`BaseSynthesizer(output_path, metadata=None)`

Provides common methods for logging, metadata handling, column type detection, anonymization, rounding, min-max scaling, model management, and saving synthetic data.

### Arguments

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `output_path` | `str` | *Required* | Path to save metadata, synthesizer models, and synthetic data. |
| `metadata` | `dict` | `None` | Optional column-type metadata dictionary. Keys are column names, values are type strings (e.g., `'numerical'`, `'ordinal_categorical'`). |

## Key Methods

### `__init__`
```python
def __init__(self, output_path: str, metadata: Optional[Dict[str, str]] = None) -> None
```
Initializes the synthesizer, creates the output directory, and sets up logging.

### `generate`
```python
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
    save_index: bool = False
) -> Union[pd.DataFrame, List[pd.DataFrame]]
```
Executes the full generation pipeline: `preprocess` -> `fit` -> `sample` -> `postprocess` -> `save`.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `data` | `pd.DataFrame` | The original input data to learn from. |
| `data_ids` | `list` | Optional list of IDs to anonymize during postprocessing. |
| `enforce_rounding` | `bool` | Whether to round synthetic data to match original precision. |
| `enforce_min_max` | `bool` | Whether to clip synthetic values to original min-max ranges. |
| `n_samples` | `int` | Number of synthetic records to generate. |

### `preprocess`
```python
def preprocess(self, data: pd.DataFrame) -> pd.DataFrame
```
Transforms original data before fitting the model. Subclasses should override this if they require specific data formats (e.g., Gaussian Copula).

### `fit`
```python
def fit(self, *args, **kwargs) -> None
```
*Must be implemented by subclasses.* Trains the synthesizer model on the (preprocessed) data.

### `sample`
```python
def sample(self, *args, **kwargs) -> Union[pd.DataFrame, List[pd.DataFrame]]
```
*Must be implemented by subclasses.* Generates synthetic records from the fitted model.

### `postprocess`
```python
def postprocess(
    self,
    synthetic_data: pd.DataFrame,
    original_data: pd.DataFrame,
    data_ids: Optional[Sequence[Any]] = None,
    enforce_rounding: bool = True,
    enforce_min_max: bool = True,
    masking: bool = False,
) -> pd.DataFrame
```
Applies constraints like rounding, min-max scaling, and ID anonymization to the sampled data.

## Custom Implementation Example

To add a new synthesizer, inherit from `BaseSynthesizer` and implement `fit` and `sample`:

```python
from SynOmics.synthesizer.BaseSynthesizer import BaseSynthesizer
import pandas as pd

class CustomSynthesizer(BaseSynthesizer):
    def fit(self, data, seed=42, **kwargs):
        self.logger.info("Fitting custom model...")
        # Your training logic here
        self.model = "my_trained_model"

    def sample(self, n_samples, seed=42, **kwargs):
        self.logger.info(f"Sampling {n_samples} records...")
        # Your sampling logic here
        return pd.DataFrame(...) # Return synthetic data

# Usage
synth = CustomSynthesizer(output_path="./results")
synth.generate(original_df, n_samples=100)
```

## Utility Methods

The base class also provides several utilities:
- `set_metadata(metadata)`: Update the column-type dictionary.
- `detect_discrete_columns(data)`: Identify discrete columns based on metadata.
- `detect_numerical_columns(data)`: Identify numerical columns based on metadata.
- `save_synthetic_data(synthetic_data, filename)`: Handles saving single DataFrames or lists.
