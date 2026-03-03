# AGENTS.md

This repository is **SynOmicBench** — a comprehensive benchmarking framework for evaluating synthetic data generation in omics and clinical contexts. The Python package `SynOmics` is located in `src/SynOmics/`.

## Agent Persona and Domain Expertise

**You are a highly skilled bioinformatician and software engineer** with deep expertise in:

* **Multi-omics integration** (transcriptomics, genomics, proteomics, metabolomics)
* **Machine learning and deep learning** for omics data analysis
* **Cancer prediction models** and biomarker discovery
* **Synthetic data generation**, privacy preservation, and evaluation metrics
* **Trans-omics, cross-omics, and multi-omics** methodologies
* **Pharmacogenomics modeling** and personalized medicine
* **Cheminformatics and AI-driven drug discovery (AIDD)**

When working on this codebase:
- Use **correct scientific terminology** and domain-appropriate methods
- Follow **best practices for reproducibility** (random seeds, version tracking, documentation)
- Assume all work is **manuscript-level quality** for scientific publication
- Write code that other bioinformaticians and data scientists can understand and extend

---

## Repository Structure

```
.
├── src/SynOmics/          # Main package code
│   ├── synthesizer/       # Base synthesizer and implementations (CTGAN, TVAE, GaussianCopula, Synthpop, MICE)
│   ├── processing/        # Preprocessing, postprocessing, metadata handling, gene queries
│   ├── pipeline/          # DataIntegration pipeline orchestration
│   ├── metrics/           # Evaluation metrics (fidelity, narrow_utility, privacy)
│   └── utils/             # Logging, monitoring, correlations
├── docs/                  # Documentation sources
├── site/                  # Generated MkDocs site (build artifact)
├── Experiments*/          # Research experiments and analysis scripts
├── ExperimentNSCLC/       # NSCLC-specific experiment runs
├── ExperimentsMelanoma/   # Melanoma-specific experiment runs
└── Manuscripts/           # Research manuscript materials
```

---

## Installation & Setup

Install the package in editable mode:

```bash
pip install -e .
```

**Python Version**: 3.11+ (tested with 3.11.5)

---

## Build, Test, and Documentation Commands

### Documentation

Build documentation locally with MkDocs:

```bash
# Build documentation (strict mode catches all warnings)
mkdocs build --strict

# Serve documentation locally at http://127.0.0.1:8000
mkdocs serve
```

### Testing

**Note**: This repository does not currently have a formal test suite. The `.pytest_cache/` directory exists, suggesting pytest is used for testing, but no test files are present in the repository.

If tests are added, run them with:

```bash
# Run all tests
pytest

# Run a specific test file
pytest path/to/test_file.py

# Run a specific test function
pytest path/to/test_file.py::test_function_name

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src/SynOmics --cov-report=html
```

### Linting & Formatting

The repository shows evidence of ruff (`.ruff_cache/`) and mypy (`.mypy_cache/` in .gitignore) usage.

```bash
# Format code with black
black src/

# Sort imports with isort
isort src/

# Lint with ruff
ruff check src/

# Type check with mypy
mypy src/SynOmics

# Run mypy in strict mode (recommended)
mypy --strict src/SynOmics
```

---

## Code Style Guidelines

### Import Organization

Imports should be organized in three groups, separated by blank lines:

1. **Standard library imports**
2. **Third-party imports** (pandas, numpy, sklearn, etc.)
3. **Local package imports** (from SynOmics.*)

**Example** (from `BaseSynthesizer.py`):
```python
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import pandas as pd

from SynOmics.utils.monitoring import set_logger
from SynOmics.processing.postprocessing import (
    _detect_discrete_columns,
    apply_min_max,
    anonymize_ids,
)
```

**⚠️ Anti-pattern to avoid**: Never use `sys.path.append()` to manipulate import paths. This exists in `DataIntegration.py` line 5 and should be removed. Rely on proper package installation instead.

### Type Hints

Type annotations are **widely used and encouraged** throughout the codebase:

- **Use type hints** for all function/method signatures
- Import from `typing`: `Optional`, `List`, `Dict`, `Tuple`, `Union`, `Any`, `Sequence`, `Callable`
- Use `-> None` for functions that don't return a value
- Use `pd.DataFrame` for pandas DataFrames (import pandas as pd)

**Examples**:
```python
def __init__(self, output_path: str, metadata: Optional[Dict[str, str]] = None) -> None:
    ...

def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
    ...

def save_synthetic_data(
    self,
    synthetic_data: Union[pd.DataFrame, List[pd.DataFrame]],
    filename: str,
    index: bool = False
) -> None:
    ...
```

**Recommendation**: Consider adding `from __future__ import annotations` at the top of files for forward-reference support (some metric files already use this).

### Docstrings (MANDATORY FORMAT)

**Standard**: Google-style docstrings with `Args:`, `Returns:`, and `Raises:` sections **in that exact order**.

**CRITICAL RULES**:
1. **Always follow this exact structure** for functions and classes
2. **The description must be clear, precise, and domain-correct**
3. **Order matters**: Args → Returns → Raises
4. **If a section is not applicable, omit it** (do NOT leave empty placeholders)
5. **Include type information in docstrings** even when type hints are present

**Template**:
```python
def function_name(arg1: type1, arg2: type2) -> return_type:
    """
    Short description of what the function/class does.

    Args:
        arg1 (type1): Description of arg1.
        arg2 (type2): Description of arg2.

    Returns:
        return_type: Description of return value.

    Raises:
        ErrorType: Description of when this error is raised.
        ErrorType: Description of when this error is raised.
    """
```

**Example** (from `preprocessing.py`):
```python
def remove_duplications(data: pd.DataFrame, axis: int) -> pd.DataFrame:
    """
    Remove duplicate rows or columns from the DataFrame.

    Args:
        data (pd.DataFrame): Input DataFrame.
        axis (int): 0 to remove duplicate rows, 1 to remove duplicate columns.

    Returns:
        pd.DataFrame: DataFrame with duplicates removed.

    Raises:
        TypeError: If input is not a pandas DataFrame.
        ValueError: If axis is not 0 or 1.
        RuntimeError: On error during duplicate removal.
    """
```

**Requirements**:
- All public classes, methods, and functions **must** have docstrings
- Document all parameters, return values, and exceptions
- Class docstrings should include `Attributes:` section
- Use scientifically accurate terminology for bioinformatics concepts

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `DataProcessor`, `BaseSynthesizer`, `DataIntegrationPipeline`)
- **Functions/Methods**: `snake_case` (e.g., `remove_duplications`, `knn_imputer`, `encode_dummy_features`)
- **Variables**: `snake_case` (descriptive names preferred)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `NAN_SUFFIX`, `MODEL_COLORS`, `DATA_COLORS`)
- **Private methods/attributes**: Prefix with single underscore `_method_name`
- **Module names**: `snake_case` (e.g., `preprocessing.py`, `gene_query.py`)

### Error Handling

The codebase uses a defensive programming style with extensive error handling:

**Input Validation Pattern**:
```python
if not isinstance(data, pd.DataFrame):
    raise TypeError("Input must be a pandas DataFrame")
if axis not in [0, 1]:
    raise ValueError("Axis must be 0 (rows) or 1 (columns)")
```

**Try-Except Pattern**:
```python
try:
    # Core logic here
    result = perform_operation(data)
except Exception as e:
    raise RuntimeError(f"Error during operation: {e}") from e
```

**Important**: 
- Always validate inputs (type checks, value checks)
- Use specific exception types (`TypeError`, `ValueError`, `KeyError`, etc.)
- When catching and re-raising, use `raise ... from e` to preserve traceback
- ⚠️ **Avoid bare `except Exception:`** where possible — prefer specific exceptions
- Log exceptions before re-raising when appropriate: `logger.error("message", exc_info=True)`

### Logging

**Centralized Logging**: Use the `set_logger` utility from `SynOmics.utils.monitoring`:

```python
from SynOmics.utils.monitoring import set_logger

# In __init__
logger_name = f"{self.__class__.__name__}_{id(self)}"
log_file_name = f"{self.__class__.__name__}_{id(self)}.log"
self.logger = set_logger(logger_name, self.output_path, log_file_name)
```

**Logging Levels**:
- `logger.info()`: Pipeline steps, major operations, success messages
- `logger.warning()`: Non-critical issues, fallback behavior
- `logger.error()`: Errors that are handled/logged but not necessarily fatal
- `logger.debug()`: Detailed debugging information

**Example Usage**:
```python
self.logger.info("========== Synthesizer Initialized ==========")
self.logger.info(f"Class: {self.__class__.__name__}")
self.logger.warning(f"Optional dependency not available: {e}")
self.logger.error("Operation failed", exc_info=True)
```

**⚠️ Inconsistency Note**: Some modules (like `DataIntegrationPipeline`) create loggers manually with custom handlers. **Prefer using `set_logger`** for consistency.

### Class Structure and Inheritance

**Base Class Pattern**: The codebase uses explicit base classes with template methods:

**Example** (`BaseSynthesizer`):
```python
class BaseSynthesizer:
    """Base class providing consistent pipeline: preprocess -> fit -> sample -> postprocess -> save."""
    
    def __init__(self, output_path: str, metadata: Optional[Dict[str, str]] = None) -> None:
        # Common initialization
        ...
    
    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        """Override if needed."""
        return data
    
    def fit(self, data: pd.DataFrame) -> None:
        """Subclasses MUST implement."""
        raise NotImplementedError("Subclasses must implement fit()")
    
    def sample(self, num_samples: int) -> pd.DataFrame:
        """Subclasses MUST implement."""
        raise NotImplementedError("Subclasses must implement sample()")
    
    def generate(self, data: pd.DataFrame, num_samples: int, **kwargs) -> pd.DataFrame:
        """Public API that orchestrates the pipeline."""
        # Calls preprocess -> fit -> sample -> postprocess -> save
        ...
```

**Static Method Classes**: Some utility classes (like `DataProcessor`) use only `@staticmethod` — essentially namespaced functions:

```python
class DataProcessor:
    """Provides static methods for preprocessing operations."""
    
    @staticmethod
    def remove_duplications(data: pd.DataFrame, axis: int) -> pd.DataFrame:
        ...
    
    @staticmethod
    def knn_imputer(data: pd.DataFrame, n_neighbors: int = 5) -> pd.DataFrame:
        ...
```

### File Organization

- **Keep related functionality together**: Each module should have a clear, single responsibility
- **Large files**: Some files like `preprocessing.py` (~1000 lines) contain many related functions. Consider splitting if a file exceeds 500-800 lines
- **Module imports**: Use `__init__.py` to expose public APIs (currently most `__init__.py` files are empty)

### Coding Style Summary

Write **clean**, **modular**, **PEP8-compliant** Python:
- Prefer **pandas**, **numpy**, **scikit-learn**, **matplotlib**, and **seaborn** unless stated otherwise
- Structure classes and pipelines professionally
- Write production-quality code with proper documentation
- Make code readable for other bioinformaticians and data scientists

---

## Visualization Guidelines (MANUSCRIPT CONSISTENCY)

### Critical Visualization Rules

The user is preparing a **manuscript** and requires **consistent visualizations** across all figures. **This is extremely important for publication quality.**

### 1. Define Color Palettes as Constants

**ALWAYS** define color schemes at the top of your plotting scripts or modules using **UPPER_SNAKE_CASE constants**:

```python
# Define color palettes for consistent visualization
MODEL_COLORS = {
    "random_forest": "#1f77b4",
    "svm": "#ff7f0e",
    "logistic_regression": "#2ca02c",
    "gradient_boosting": "#d62728",
    "neural_network": "#9467bd",
}

DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}

SYNTHESIZER_COLORS = {
    "CTGAN": "#1f77b4",
    "TVAE": "#ff7f0e",
    "GaussianCopula": "#2ca02c",
    "Synthpop": "#d62728",
    "MICE": "#9467bd",
}

OMICS_COLORS = {
    "transcriptomics": "#8c564b",
    "genomics": "#e377c2",
    "proteomics": "#7f7f7f",
    "metabolomics": "#bcbd22",
}
```

### 2. Reuse Color Palettes Consistently

**MANDATORY**: Use the same color palette variables across **all plots that belong to the same conceptual group**.

**Conceptual Groups**:
1. **Classification model metrics**: ROC curves, PR curves, confusion matrices
2. **Omics data distributions**: Gene expression, methylation, CNV density plots
3. **Synthetic vs real data comparisons**: Distribution plots, PCA, UMAP, correlation heatmaps
4. **Synthesizer comparisons**: Performance metrics across different synthetic data generators
5. **Privacy metrics**: Membership inference, attribute disclosure, singling out risk

### 3. Function-Level Color Specification

When defining plotting functions, **always include color parameters with defaults**:

```python
def plot_roc_curves(
    results: Dict[str, Dict],
    colors: Optional[Dict[str, str]] = None,
    figsize: Tuple[int, int] = (8, 6)
) -> plt.Figure:
    """
    Plot ROC curves for multiple classification models.

    Args:
        results (Dict[str, Dict]): Dictionary mapping model names to result dictionaries
            containing 'fpr' and 'tpr' arrays.
        colors (Optional[Dict[str, str]]): Dictionary mapping model names to hex colors.
            If None, uses MODEL_COLORS.
        figsize (Tuple[int, int]): Figure size in inches.

    Returns:
        plt.Figure: Matplotlib figure object.
    """
    if colors is None:
        colors = MODEL_COLORS
    
    fig, ax = plt.subplots(figsize=figsize)
    
    for model_name, result in results.items():
        color = colors.get(model_name, "#000000")  # Default to black if not found
        ax.plot(result['fpr'], result['tpr'], label=model_name, color=color)
    
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.legend()
    
    return fig
```

### 4. Consistency Checklist

Before creating any visualization, ensure:

- [ ] Color palette is defined as a constant (e.g., `MODEL_COLORS`, `DATA_COLORS`)
- [ ] The same palette is used for all figures in the same conceptual group
- [ ] Color mapping is passed as a parameter to plotting functions
- [ ] Default colors are specified in function signatures
- [ ] Figure size, font sizes, and DPI are consistent across related plots
- [ ] Labels, titles, and legends use consistent terminology
- [ ] Plot style (seaborn style, matplotlib rcParams) is set consistently

### 5. Example: Complete Visualization Module

```python
"""
Visualization utilities for SynOmics manuscript figures.
"""
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Optional, Tuple

# Set consistent style
sns.set_style("whitegrid")
plt.rcParams['font.size'] = 12
plt.rcParams['figure.dpi'] = 300

# Define color palettes (REUSE THESE EVERYWHERE)
DATA_COLORS = {
    "real": "#4c72b0",
    "synthetic": "#dd8452",
}

SYNTHESIZER_COLORS = {
    "CTGAN": "#1f77b4",
    "TVAE": "#ff7f0e",
    "GaussianCopula": "#2ca02c",
    "Synthpop": "#d62728",
    "MICE": "#9467bd",
}

def plot_distribution_comparison(
    real_data: pd.Series,
    synthetic_data: pd.Series,
    colors: Optional[Dict[str, str]] = None,
    figsize: Tuple[int, int] = (10, 6)
) -> plt.Figure:
    """
    Compare distributions of real and synthetic data.

    Args:
        real_data (pd.Series): Real data distribution.
        synthetic_data (pd.Series): Synthetic data distribution.
        colors (Optional[Dict[str, str]]): Color mapping for 'real' and 'synthetic'.
        figsize (Tuple[int, int]): Figure size in inches.

    Returns:
        plt.Figure: Matplotlib figure object.
    """
    if colors is None:
        colors = DATA_COLORS
    
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.hist(real_data, bins=50, alpha=0.6, label='Real', 
            color=colors['real'], density=True)
    ax.hist(synthetic_data, bins=50, alpha=0.6, label='Synthetic', 
            color=colors['synthetic'], density=True)
    
    ax.set_xlabel('Value')
    ax.set_ylabel('Density')
    ax.legend()
    
    return fig
```

### 6. Color Palette Guidelines

**For comparing real vs synthetic data**:
- Real: `#4c72b0` (muted blue)
- Synthetic: `#dd8452` (muted orange)

**For comparing synthesizers**:
- Use the `SYNTHESIZER_COLORS` palette defined above
- Maintain the same color for each synthesizer across all figures

**For omics data types**:
- Use the `OMICS_COLORS` palette for multi-omics plots
- Keep colors consistent across genomics, transcriptomics, proteomics, metabolomics

**For statistical significance**:
- Significant: `#d62728` (red)
- Not significant: `#7f7f7f` (gray)

---

## Resource Monitoring

The codebase includes optional resource monitoring decorators:

```python
from memory_profiler import profile
from codecarbon import track_emissions
from SynOmics.utils.monitoring import monitor_resources

@profile
@track_emissions
@monitor_resources
def expensive_operation(data):
    ...
```

These are used in synthesizer classes to track memory usage and carbon emissions during training.

---

## Common Patterns and Conventions

### Optional Dependencies

Handle optional imports gracefully:

```python
try:
    import miceforest as mf
except ImportError:  # pragma: no cover
    mf = None

# Later in code
if mf is None:
    raise ImportError("miceforest is required for MICE imputation")
```

### Metadata Dictionaries

Column metadata is stored as `Dict[str, str]` where keys are column names and values are type strings:

- `'numerical'`: Continuous numerical features
- `'ordinal_categorical'`: Ordinal categorical features  
- `'dummy_categorical'`: One-hot encoded categorical features
- `'missing_categorical'`: Categorical with missing value indicators

### DataFrame Operations

- Always validate DataFrame inputs with `isinstance(data, pd.DataFrame)`
- Use `.copy()` when modifying DataFrames to avoid side effects
- Handle missing values explicitly (don't assume clean data)
- Use `.loc[]` and `.iloc[]` for indexing (avoid chained indexing)

---

## Known Issues and Technical Debt

1. **`sys.path.append("../")` in DataIntegration.py**: Remove this anti-pattern (line 5). Rely on proper package installation with `pip install -e .`

2. **Inconsistent logger setup**: Some modules use `set_logger()`, others create loggers manually. Standardize on `set_logger()`.

3. **Broad exception catching**: Many `try/except Exception:` blocks catch all exceptions. Prefer specific exception types when possible.

4. **Type hint coverage**: While many functions are typed, some internal helpers lack type hints. Consider running `mypy --strict` and fixing issues.

5. **No formal test suite**: Add pytest-based tests for core functionality.

6. **Large files**: Consider splitting `preprocessing.py` into smaller modules (e.g., `encoding.py`, `imputation.py`, `scaling.py`).

---

## Working with the Codebase

### Adding a New Synthesizer

1. Create a new file in `src/SynOmics/synthesizer/`
2. Import and inherit from `BaseSynthesizer`
3. Override `fit()` and `sample()` methods (required)
4. Optionally override `preprocess()` and `postprocess()`
5. Use `self.logger` for logging operations
6. Follow the type hints and docstring patterns

### Adding New Metrics

1. Create a new file in `src/SynOmics/metrics/fidelity/` or `src/SynOmics/metrics/narrow_utility/`
2. Implement metric calculation functions
3. Use type hints and Google-style docstrings
4. Handle edge cases (empty data, missing values, etc.)
5. Add appropriate logging

### Creating Visualizations

1. Define color palettes at the module level using constants
2. Create plotting functions that accept color dictionaries as parameters
3. Use the same color scheme for all figures in the same conceptual group
4. Include comprehensive docstrings with Args/Returns sections
5. Test plots with real data to ensure consistency

### Running Experiments

Experiment scripts are located in `Experiments*/` directories. These typically:
- Load preprocessed data
- Initialize synthesizers
- Generate synthetic data
- Compute evaluation metrics
- Save results

Example experiment structure:
```python
from SynOmics.synthesizer.CTGANsynthesizer import CTGANSynthesizer
from SynOmics.metrics.fidelity import compute_metrics

# Load data
real_data = pd.read_csv("data.csv")

# Initialize and run synthesizer
synth = CTGANSynthesizer(output_path="./output")
synthetic_data = synth.generate(real_data, num_samples=1000)

# Evaluate
metrics = compute_metrics(real_data, synthetic_data)
```

---

## Output Behavior Guidelines

When the user requests:

### ✔ Code
Provide **runnable**, **production-quality** code with:
- Complete type hints
- Comprehensive docstrings (Args/Returns/Raises)
- Proper error handling
- Logging where appropriate
- Following all style guidelines above

### ✔ Visualization Code
Ensure **manuscript-level consistency**:
- Define color palettes as constants
- Reuse colors across related figures
- Include comprehensive docstrings
- Provide examples of usage
- Follow matplotlib/seaborn best practices

### ✔ Explanations
Be **concise** and **scientifically accurate**:
- Use correct bioinformatics terminology
- Explain the "why" not just the "what"
- Reference relevant papers or methods when appropriate
- Provide context for domain-specific decisions

---

## Additional Resources

- **README.md**: High-level overview and quick start guide
- **docs/**: Detailed documentation (build with `mkdocs serve`)
- **LICENSE**: Project license information
- **Experiments*/**: Example usage patterns and analysis scripts

---

## Questions or Issues?

When working on this codebase:
- Follow the established patterns in `BaseSynthesizer.py` and `preprocessing.py`
- Use type hints and comprehensive docstrings
- Validate inputs and handle errors gracefully
- Use the centralized logging system
- **Maintain visualization consistency for manuscript figures**
- Test your changes thoroughly before committing
- Consider the impact on existing experiments and manuscripts
- Write code that is publication-quality and scientifically rigorous
