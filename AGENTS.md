# AGENTS.md - SynOmicBench Developer Guide

Guidelines for AI agents working on the SynOmicBench codebase.

---

## Project Structure

```
SynOmicBench/
├── src/SynOmics/           # Main package
│   ├── processing/         # Data preprocessing & pipeline
│   ├── metrics/            # Evaluation metrics (fidelity, utility, privacy)
│   ├── synthesizer/        # SDG method implementations
│   └── utils/              # Utilities
├── test/                   # Unit tests (pytest)
├── docs/                   # Documentation (MkDocs)
└── README.md
```

---

## Build, Lint & Test Commands

### Running Tests

```bash
cd /Users/thechuongtrinh/Workspace/SynOmicBench

# Run all tests
python -m pytest

# Run specific test file
python -m pytest test/test_processing.py

# Run single test
python -m pytest test/test_processing.py::TestDataProcessor::test_remove_duplications_rows -v

# Run tests matching pattern
python -m pytest -k "test_remove"

# Run with coverage
python -m pytest --cov=src/SynOmics --cov-report=term-missing
```

### Code Quality

```bash
# Type checking
python -m mypy src/SynOmics

# Linting
python -m ruff check src/SynOmics
# or
python -m flake8 src/SynOmics

# Format code
python -m black src/SynOmics
```

### Documentation

```bash
mkdocs build   # Build docs
mkdocs serve   # Serve locally
```

---

## Code Style Guidelines

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `gene_query.py` |
| Classes | PascalCase | `DataIntegrationPipeline` |
| Functions | snake_case | `remove_duplications()` |
| Variables | snake_case | `processed_data` |
| Constants | UPPER_SNAKE | `DEFAULT_THRESHOLD` |
| Private methods | prefix `_` | `_internal_method()` |

### Type Hints

Use type hints for all function signatures:

```python
from typing import Optional, Dict, List, Any

def process_data(
    data: pd.DataFrame,
    config: Dict[str, Any],
    threshold: Optional[float] = None,
) -> pd.DataFrame:
```

### Import Organization

Order imports in three sections (separate with blank lines):

1. **Standard library** - `os`, `sys`, `json`, `time`, `typing`
2. **Third-party** - `pandas`, `numpy`, `scipy`, `sklearn`
3. **Local/Project** - `from SynOmics.processing...`

```python
# Standard library
import os
import json
from typing import Optional, Dict

# Third-party
import pandas as pd
import numpy as np
from tqdm import tqdm

# Local
from SynOmics.processing.preprocessing import DataProcessor
from SynOmics.utils.monitoring import set_logger
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def process_data(
    data: pd.DataFrame,
    threshold: float = 50.0,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Process raw data with configurable filtering.

    Args:
        data: Input DataFrame to process.
        threshold: Missingness threshold (0-100).
        verbose: Print progress messages.

    Returns:
        Processed DataFrame with filtered rows.

    Raises:
        TypeError: If data is not a pandas DataFrame.
        ValueError: If threshold is outside valid range.
    """
```

### Error Handling

- Use **specific exception types** (`KeyError`, `TypeError`, `ValueError`)
- Provide **informative error messages** with context
- **Rethrow with context** when catching and re-raising:

```python
try:
    result = DataProcessor.process(data)
except KeyError as e:
    raise KeyError(f"Missing required column: {e}") from e
```

Avoid:
- Bare `except:` clauses
- Empty catch blocks (`except: pass`)
- Suppressing errors without logging

### Logging

Use the project's logging utility:

```python
from SynOmics.utils.monitoring import set_logger

logger = set_logger("MyClass", output_dir="./logs")
logger.info("Processing started")
logger.warning("Skipping step X")
logger.error(f"Failed: {error}")
```

### Data Handling

- **Never modify input data in place** - always use `.copy()`:
  ```python
  data = data.copy()  # Before modifications
  ```
- **Use descriptive variable names** - avoid single letters except in tight loops

### Testing Guidelines

- Test file naming: `test_<module>.py`
- Test class naming: `Test<ClassName>`
- Test function naming: `test_<description>()`
- Use pytest fixtures for shared setup
- Test one thing per test function

```python
class TestDataProcessor:
    """Smoke tests for DataProcessor static methods."""

    def test_remove_duplications_rows(self, original_data):
        result = DataProcessor.remove_duplications(original_data, axis=0)
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= len(original_data)
```

---

## Common Patterns

### Configuration Dictionaries

```python
steps_config = {
    "remove_undefined": True,
    "remove_duplicates": True,
    "feature_engineering": True,
}
```

### Return Types

Multiple return values use dictionaries:

```python
return {
    "processed_clinical": processed_clinical,
    "processed_transcriptomics": processed_transcriptomics,
    "integrated_data": integrated_data,
}
```

---

## Key Dependencies

- **pandas/numpy** - Data manipulation
- **scikit-learn** - ML utilities
- **sdmetrics** - Statistical similarity metrics
- **scipy** - Statistical tests
- **matplotlib/seaborn** - Visualization
