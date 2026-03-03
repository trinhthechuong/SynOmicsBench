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

### Lint / typecheck / tests

- No dedicated lint/typecheck/test suite is configured.
- Validation = `mkdocs build`.
- Single test (if added later): `pytest path/to/test_file.py::test_name`.

**CI** (`.github/workflows/docs.yml`): On push to `main` (paths: `docs/**`, `mkdocs.yml`),
installs `mkdocs-material` and runs `mkdocs gh-deploy --force`.

**Python**: 3.11+ required for the `src/SynOmics` package.

**No test suite exists** — verify changes with `mkdocs build` (exit 0 = success).

### Known Build Warnings

- **griffe** missing type annotations — warnings only.
- Some docs may have broken image links (fix paths if you touch those pages).

## Documentation Style Guide

### Markdown Conventions

- Use headings `# / ## / ###`.
- Use relative links and keep images under `docs/assets/figures/`.
- Use admonitions (`!!! note`) and collapsibles (`??? note`) when helpful.
- Always language-tag code blocks.

### Navigation

Exactly **6 top-level tabs** in `mkdocs.yml`. If you add/rename tabs, update `mkdocs.yml`.

### API Documentation (mkdocstrings)

```markdown
::: SynOmics.processing.preprocessing.DataProcessor
```

- Google-style docstrings.
- Imports resolve from `src/`.

### Cursor/Copilot rules

- No Cursor rules found (`.cursor/rules/`, `.cursorrules`).
- No Copilot instructions found (`.github/copilot-instructions.md`).

### Custom Styling

- Brand color: CEA red `#E2001A` in `docs/stylesheets/extra.css`.

## Python Source Code Style (`src/SynOmics/`)

### Docstrings (Google Style)

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

- Absolute imports from `SynOmics.*`; group stdlib → third-party → internal.

### Naming

- Classes: `PascalCase` (e.g., `DataProcessor`)
- Functions/methods: `snake_case`
- Private helpers: `_leading_underscore`
- Constants: `UPPER_SNAKE`
- Files: keep existing conventions in `src/SynOmics/`

### Architecture

- Synthesizers inherit `BaseSynthesizer`.
- Processing utilities are `@staticmethod` helpers (e.g., `DataProcessor`).
- Use `set_logger()` for logs (avoid `print()` in library code).

### Error Handling

```python
if not isinstance(data, pd.DataFrame):
    raise TypeError("Input must be a pandas DataFrame")

try:
    # operation
except Exception as e:
    raise ValueError(f"Error in <operation>: {e}")
```

- Validate inputs early; no silent exceptions.

### Type Annotations

- Type annotate public APIs and returns.

## Quick Reference

- Serve docs: `mkdocs serve`
- Build docs: `mkdocs build`
- Add doc page: create `.md` under `docs/` + add to `mkdocs.yml` nav
- Add API page: add `:::` directive under `docs/api/`
- Add images: `docs/assets/figures/` and reference relatively
