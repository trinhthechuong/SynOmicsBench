# AGENT.md

This repository is **SynOmicBench** (Python package: `src/SynOmics/`) plus docs, notebooks, and experiment outputs.

## Repo map

- `src/SynOmics/` — library code (pipeline, processing, synthesizers, metrics)
- `docs/` — documentation sources
- `mkdocs.yml` — MkDocs configuration
- `site/` — generated site output (treat as build artifact)
- `Experiments*/`, `ExperimentNSCLC/`, `Manuscripts/` — research material / experiment runs

## Common commands

Install editable (per `README.md`):

```bash
pip install -e .
```

Build docs locally:

```bash
mkdocs build --strict
mkdocs serve
```

## Notes

- No `AGENT.md`/`AGENTS.md` file was present in the git history of this repo at the time of writing; this file is a recreated replacement.
- Large experiment outputs should generally stay out of git unless intentionally curated.
