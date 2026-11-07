# Vendored Anonymeter singling-out evaluator (polars)

Source: the polars implementation of Anonymeter's `SinglingOutEvaluator`
(https://github.com/statice/anonymeter, Clear BSD licence, see `LICENSE.md`), in the version
that produced the published SynOmicsBench singling-out results.

`singling_out_evaluator.py` is copied without modification (md5 `d636fc0b23bc04470094914674f0ef36`).
It replaces the pandas evaluator of anonymeter 1.0.0, which is too slow on cohorts with tens of
thousands of columns. `__init__.py` is empty and only makes the directory importable.

Reproducibility: `univariate_singling_out_queries` collects rare values with polars
`group_by` without `maintain_order`, so the order of the candidate queries, and hence which
10,000 are kept, can change between runs with the same `seed`. The univariate success count
then varies by a few attacks out of 10,000; the multivariate attack is not affected.
