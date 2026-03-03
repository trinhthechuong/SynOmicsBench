# AGENTS.md — SynOmicBench Documentation Site

> **MkDocs documentation site** for SynOmicBench, a benchmark framework for synthetic data
> generation in clinical/transcriptomic cancer data. Python source in `src/SynOmics/` is
> the library being documented via mkdocstrings.

## Repository Layout

```
mkdocs.yml                  # MkDocs Material config (nav, plugins, extensions)
docs/                       # Markdown source
  index.md                  # Home page
  getting-started/          # Installation & quick start
  preprocessing/            # Data integration pipeline
  synthetic-data/           # SDG method descriptions
  evaluation/               # Benchmark results (broad utility, narrow utility, privacy)
    narrow-utility/         # DGE, GSEA, ssGSEA, cell deconv, survival
  api/                      # Auto-generated API reference (mkdocstrings directives)
  stylesheets/extra.css     # Custom CSS (CEA brand colors: #E2001A)
  javascripts/mathjax.js    # MathJax config for LaTeX rendering
  assets/figures/           # Images referenced in docs
src/SynOmics/               # Python library source (documented via mkdocstrings)
  synthesizer/              # BaseSynthesizer + CTGAN, TVAE, GaussianCopula, Synthpop
  processing/               # DataProcessor, MetaData, pipeline, gene_query
  metrics/                  # Fidelity (univariate/pairwise), narrow utility (DGE, GSEA, survival)
  utils/                    # Logging (set_logger), monitoring (monitor_resources), correlations
site/                       # Built output (gitignored, do not edit)
.github/workflows/docs.yml  # CI: deploy to GitHub Pages on push to main
```

## Build & Serve Commands

```bash
pip install mkdocs-material mkdocstrings[python]   # Install dependencies
mkdocs serve                                        # Dev server with live reload
mkdocs build                                        # Build static site to site/
mkdocs gh-deploy --force                            # Deploy to GitHub Pages
```

**CI** (`.github/workflows/docs.yml`): On push to `main` (paths: `docs/**`, `mkdocs.yml`),
installs `mkdocs-material` and runs `mkdocs gh-deploy --force`.

**Python**: 3.11+ required for the `src/SynOmics` package.

**No test suite exists** — verify changes with `mkdocs build` (exit 0 = success).

### Known Build Warnings

- **griffe**: `**kwargs` and return values lacking type annotations — warnings only, non-blocking.
- **Broken image links**: `evaluation/privacy.md` uses `../../assets/figures/` paths; should be
  `../assets/figures/`. Fix if editing that file.
- **MkDocs 2.0**: Material for MkDocs compatibility warning — informational only.

## Documentation Style Guide

### Markdown Conventions

- `#` page title, `##` sections, `###` subsections
- **Bold** key terms/method names on first mention; *italic* for figure captions below images
- Tables: standard pipe tables with alignment (`:---`, `:---:`)
- Math: `$...$` inline, `$$...$$` display (MathJax via `pymdownx.arithmatex`)
- Admonitions: `!!! note`, `!!! warning`, `!!! tip` (pymdownx)
- Code blocks: always specify language (` ```python `, ` ```bash `, ` ```text `)
- Links: relative paths (`../evaluation/index.md`), never absolute URLs
- Images: place in `docs/assets/figures/`, reference as `../assets/figures/filename.png`
- Collapsible sections: `??? note "Title"` (pymdownx.details)
- Tabbed content: `=== "Tab Name"` (pymdownx.tabbed)

### Navigation

Exactly **6 top-level tabs** in `mkdocs.yml`:
Home, Getting Started, Preprocessing Data, Generate Synthetic Data, Evaluation, API.
Do not add/rename top-level tabs without updating `mkdocs.yml`.

### API Documentation (mkdocstrings)

```markdown
::: SynOmics.synthesizer.BaseSynthesizer.BaseSynthesizer
```

- `docstring_style: google` — Python docstrings must use **Google style**
- `paths: [src]` — resolves imports from `src/`
- `show_source: true` — source code displayed alongside docs

### Custom Styling

- Brand color: CEA red `#E2001A` — defined in `docs/stylesheets/extra.css`
- Theme: Material for MkDocs with sticky nav tabs, search, code copy

## Python Source Code Style (`src/SynOmics/`)

### Docstrings (Google Style — mandatory)

```python
def method(self, data: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Brief description.

    Args:
        data (pd.DataFrame): Description of the parameter.
        threshold (float): Description with default noted.

    Returns:
        pd.DataFrame: Description of returned value.

    Raises:
        ValueError: When and why this is raised.
    """
```

### Imports

```python
import os                                           # stdlib first
from typing import Optional, List, Dict, Any

import pandas as pd                                 # third-party
import numpy as np

from SynOmics.utils.monitoring import set_logger    # internal (absolute)
from SynOmics.processing.metadata import MetaData
```

- Always **absolute imports** from `SynOmics.*`
- Group: stdlib → third-party → internal
- Optional deps: `try: import miceforest as mf except ImportError: mf = None`

### Naming Conventions

| Element           | Convention            | Example                              |
|-------------------|-----------------------|--------------------------------------|
| Classes           | PascalCase            | `BaseSynthesizer`, `DataProcessor`   |
| Methods/functions | snake_case            | `get_univariate_score`               |
| Private helpers   | `_leading_underscore` | `_detect_discrete_columns`           |
| Constants         | UPPER_SNAKE           | `MB = 1024 * 1024`                   |
| Files (classes)   | PascalCase            | `BaseSynthesizer.py`                 |
| Files (utilities) | snake_case            | `preprocessing.py`                   |
| Package dirs      | snake_case            | `metrics/fidelity/`, `narrow_utility/` |

### Class Architecture

- **Synthesizers**: inherit `BaseSynthesizer`, override `fit()`, `sample()`,
  optionally `preprocess()` and `postprocess()`
- **Metrics**: standalone classes with `__init__(output_dir)` and computation methods
- **Processing**: `@staticmethod` methods on utility classes (`DataProcessor`, `MetaData`)
- **Logging**: use `set_logger()` from `SynOmics.utils.monitoring` — never raw `print()`

### Error Handling

```python
if not isinstance(data, pd.DataFrame):
    raise TypeError("Input must be a pandas DataFrame")

try:
    # operation
except Exception as e:
    raise ValueError(f"Error in <operation>: {e}")
```

- Validate inputs early with `TypeError` / `ValueError`
- Wrap complex ops in try/except, re-raise as `ValueError` or `RuntimeError`
- Log errors via `self.logger.error(msg, exc_info=True)` before raising
- Never silently swallow exceptions (no empty `except: pass`)
- Optional deps: `try: import X except Exception: <fallback>`

### Type Annotations

- All public method signatures must have type annotations
- Use `typing`: `Optional`, `List`, `Dict`, `Union`, `Sequence`, `Any`, `Tuple`
- Return types annotated (common: `pd.DataFrame`, `float`, `Dict`, `None`)
- Document `**kwargs` accepted keys in the docstring

## Quick Reference

| Task                       | Command / Location                                     |
|----------------------------|--------------------------------------------------------|
| Serve docs locally         | `mkdocs serve`                                         |
| Build docs                 | `mkdocs build`                                         |
| Deploy to GitHub Pages     | `mkdocs gh-deploy --force`                             |
| Add new doc page           | Create `.md` in `docs/`, add to `nav:` in `mkdocs.yml` |
| Add API reference          | Add `::: SynOmics.module.Class` to `docs/api/index.md` |
| Add image                  | Place in `docs/assets/figures/`, use relative link      |
| Edit brand colors          | `docs/stylesheets/extra.css`                           |
| CI workflow                | `.github/workflows/docs.yml`                           |
| Python source for API docs | `src/SynOmics/` (resolved via `paths: [src]`)          |
