"""
Self-contained HTML report of the automatic benchmark.

``report.html`` has no external dependency (inline CSS, SVG and JavaScript) and follows the
SynOmicsBench documentation style. It reads from the summary to the detail:

1. the ranking by meta-score, with each pillar's share of the score;
2. the sensitivity of the ranking to the pillar weights: the ranks under the weighting
   scenarios (``config.scenarios``) and an interactive weight triangle that shows the
   weights and the ranking at the pointer;
3. the value and the rank-derived score of every metric;
4. how the meta-score is computed.

The triangle and the scenario chart are computed in the browser from the unweighted pillar
scores, since the meta-score is their weighted sum.
"""

from __future__ import annotations

import html
import json
import os
from datetime import date
from typing import Dict, List

import numpy as np

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS
from .config import BenchmarkConfig, ALL_DIMS, LOWER_IS_BETTER, PILLARS, SCENARIO_DESCRIPTIONS
from .metascore import pillar_scores

#: Display name of each dimension in the report.
METRIC_LABELS = {
    "Univariate": "Univariate similarity",
    "Bivariate": "Bivariate similarity",
    "Network Preservation": "Network preservation",
    "DGE": "F1-GCS (DGE)",
    "GSEA": "F1-PCS (GSEA)",
    "ssGSEA": "ssGSEA",
    "Cell Deconvolution": "Cell deconvolution",
    "Survival Analysis": "Survival score",
    "Singling-out (uni)": "Singling out, univariate",
    "Singling-out (multi)": "Singling out, multivariate",
    "Linkability": "Linkability",
    "Inference": "Attribute inference",
}
PILLAR_KEYS = {"Statistical fidelity": "stat", "Biological utility": "bio", "Privacy": "priv"}
FALLBACK_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#9c755f", "#76b7b2", "#edc948", "#ff9da7"]


def _esc(x) -> str:
    return html.escape(str(x))


def _method_colors(methods: List[str]) -> Dict[str, str]:
    colors, k = {}, 0
    for m in methods:
        if m in DATASET_COLORS:
            colors[m] = DATASET_COLORS[m]
        else:
            colors[m] = FALLBACK_COLORS[k % len(FALLBACK_COLORS)]
            k += 1
    return colors


def _fmt(v, nd=3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{v:.{nd}f}"


def _risk_digits(values) -> int:
    """Decimals that show small risks (e.g. 0.0014) with two significant digits."""
    vals = [abs(v) for v in values if v is not None and not np.isnan(v) and v != 0]
    if not vals:
        return 3
    return int(min(6, max(3, 1 - np.floor(np.log10(min(vals))))))


def _chip(method: str, color: str) -> str:
    return f'<span class="chip"><i style="background:{color}"></i>{_esc(method)}</span>'


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def _ranking_section(result, config, colors) -> str:
    comp = result.composite.sort_values("Total", kind="stable")
    pillars = [p for p in PILLARS if p in comp.columns]
    weights = dict(zip(PILLARS, config.weights))
    wsum = sum(weights[p] for p in pillars)
    vmax = float(comp["Total"].max()) or 1.0
    rows = []
    for rank, (method, row) in enumerate(comp.iterrows(), start=1):
        segs = "".join(
            f'<span class="seg {PILLAR_KEYS[p]}" style="width:{100 * row[p] / vmax:.2f}%" '
            f'title="{_esc(p)}: {row[p]:.2f}"></span>' for p in pillars)
        rows.append(
            f'<tr><td class="num rank">{rank}</td><td>{_chip(method, colors[method])}</td>'
            f'<td class="num strong">{row["Total"]:.2f}</td>'
            + "".join(f'<td class="num">{row[p]:.2f}</td>' for p in pillars)
            + f'<td class="barcell"><div class="stack">{segs}</div></td></tr>')
    head = ('<tr><th class="num">Rank</th><th>Method</th><th class="num">Meta-score</th>'
            + "".join(f'<th class="num"><span class="key {PILLAR_KEYS[p]}"></span>{_esc(p)} '
                      f'<span class="w">×{weights[p] / wsum:.2f}</span></th>' for p in pillars)
            + "<th>Contribution of each pillar</th></tr>")
    best = comp.index[0]
    missing = [p for p in PILLARS if p not in pillars]
    note = ""
    if missing:
        note = (f'<p class="note">No metric of {", ".join(missing)} was evaluated: the meta-score '
                f'uses {" and ".join(pillars)}, with the weights rescaled to sum to 1.</p>')
    return f"""
<section id="ranking">
  <h2>Ranking</h2>
  <p class="lede"><strong>{_esc(best)}</strong> has the lowest meta-score
  ({comp['Total'].iloc[0]:.2f}). The meta-score is the weighted sum of the pillar scores; a pillar
  score is the mean rank of the method's datasets over the pillar's metrics, so lower is better.</p>
  {note}
  <div class="scroll"><table class="data ranking">{head}{''.join(rows)}</table></div>
</section>"""


def _sensitivity_section(result, config) -> str:
    pillars = pillar_scores(result.metascore)
    if len(pillars.columns) < 2:
        return f"""
<section id="sensitivity">
  <h2>Sensitivity to the pillar weights</h2>
  <p class="lede">Only {_esc(pillars.columns[0])} was evaluated, so the pillar weights do not change
  the ranking.</p>
</section>"""
    has_all = all(p in pillars.columns for p in PILLARS)
    triangle = ""
    if has_all:
        triangle = """
  <h3>All pillar weights</h3>
  <p>Each point of the triangle is a weighting of the three pillars (summing to 1), coloured by the
  method ranked first. Move the pointer over the triangle, or use the sliders, to read the weights
  and the full ranking. Circles mark the scenarios above.</p>
  <div class="tri-wrap">
    <figure class="tri">
      <div class="tri-stage">
        <canvas id="tri-canvas" width="460" height="420" role="img"
          aria-label="Weight triangle coloured by the first-ranked method"></canvas>
        <svg id="tri-svg" viewBox="0 0 460 420" aria-hidden="true"></svg>
      </div>
      <div class="tri-controls">
        <label for="tri-color">Colour by</label>
        <select id="tri-color"></select>
      </div>
      <p class="hint" id="tri-legend"></p>
    </figure>
    <div class="tri-side">
      <div class="readout" aria-live="polite">
        <div class="weights" id="tri-weights"></div>
        <ol class="ranklist" id="tri-ranks"></ol>
      </div>
      <div class="sliders">
        <label for="w-stat">Statistical fidelity <output id="o-stat"></output></label>
        <input type="range" id="w-stat" min="0" max="100" step="1">
        <label for="w-bio">Biological utility <output id="o-bio"></output></label>
        <input type="range" id="w-bio" min="0" max="100" step="1">
        <label for="w-priv">Privacy <output id="o-priv"></output></label>
        <input type="range" id="w-priv" min="0" max="100" step="1">
        <p class="hint">The three weights sum to 1: moving one slider shares the rest between the other two in their current proportion.</p>
      </div>
      <table class="data share" id="tri-share"></table>
    </div>
  </div>"""
    elif len(pillars.columns) > 1:
        triangle = ('<p class="note">The weight triangle needs metrics of the three pillars; '
                    'the scenarios above rescale the weights of the evaluated pillars.</p>')
    described = [(n, SCENARIO_DESCRIPTIONS[n], w) for n, w in (config.scenarios or {}).items()
                 if n in SCENARIO_DESCRIPTIONS]
    desc = ""
    if described:
        items = "".join(
            f"<div><dt>{_esc(n)} <span class=\"wts\">{' / '.join(f'{x:.2f}' for x in w)}</span></dt>"
            f"<dd>{_esc(d)}</dd></div>" for n, d, w in described)
        desc = f'<dl class="scen-desc">{items}</dl>'
    return f"""
<section id="sensitivity">
  <h2>Sensitivity to the pillar weights</h2>
  <p class="lede">The ranking depends on how the three pillars are weighted, and the right weights
  depend on how the synthetic data will be shared. The scenarios below give the ranking for typical
  data-sharing settings; the triangle covers every weighting.</p>
  <h3>Weighting scenarios</h3>
  {desc}
  <div class="scen-wrap">
    <div class="scroll"><table class="data" id="scen-table"></table></div>
    <figure class="bump"><svg id="bump-svg" role="img" aria-label="Rank of each method under each scenario"></svg></figure>
  </div>
  {triangle}
</section>"""


def _metrics_section(result, colors) -> str:
    methods = list(result.composite.sort_values("Total", kind="stable").index)
    dims = [d for d in ALL_DIMS if d in result.per_dim_values]
    blocks = []
    for pillar, pdims in PILLARS.items():
        present = [d for d in pdims if d in dims]
        if not present:
            continue
        head = "<tr><th>Method</th>" + "".join(
            f'<th class="num">{_esc(METRIC_LABELS.get(d, d))}<span class="dir">{"risk, lower is better" if d in LOWER_IS_BETTER else "higher is better"}</span></th>'
            for d in present) + "</tr>"
        stats = {d: result.per_dim_values[d].groupby("Model")["Value"].agg(["mean", "std", "count"]) for d in present}
        digits = {d: (_risk_digits(stats[d]["mean"].tolist()) if d in LOWER_IS_BETTER else 3) for d in present}
        rows = []
        for m in methods:
            cells = []
            for d in present:
                s = stats[d]
                if m not in s.index:
                    cells.append('<td class="num">–</td>')
                    continue
                mean, sd, n = s.loc[m, "mean"], s.loc[m, "std"], s.loc[m, "count"]
                rank = result.metascore[d].get(m, np.nan)
                ranks = sorted(result.metascore[d].values())
                best = rank == ranks[0]
                sd_txt = f'<span class="sd">± {_fmt(sd, digits[d])}</span>' if n > 1 and not np.isnan(sd) else ""
                cells.append(f'<td class="num{" best" if best else ""}">{_fmt(mean, digits[d])}{sd_txt}'
                             f'<span class="r">rank {rank:.1f}</span></td>')
            rows.append(f"<tr><td>{_chip(m, colors[m])}</td>{''.join(cells)}</tr>")
        blocks.append(f'<h3><span class="key {PILLAR_KEYS[pillar]}"></span>{_esc(pillar)}</h3>'
                      f'<div class="scroll"><table class="data metrics">{head}{"".join(rows)}</table></div>')
    missing = ""
    if result.dims_missing:
        errors = getattr(result, "errors", {}) or {}
        items = "".join(f"<li><strong>{_esc(METRIC_LABELS.get(d, d))}</strong>: {_esc(errors.get(d, 'not computed'))}</li>"
                        for d in result.dims_missing)
        missing = f'<div class="missing"><h3>Not evaluated</h3><ul>{items}</ul></div>'
    return f"""
<section id="metrics">
  <h2>Metrics</h2>
  <p class="lede">Mean over the datasets of each method (± standard deviation), and the
  rank-derived score: the mean rank of the method's datasets among all datasets
  (1 = best). The best score of each metric is highlighted.</p>
  {''.join(blocks)}
  {missing}
</section>"""


def _method_section() -> str:
    return """
<section id="method">
  <h2>How the meta-score is computed</h2>
  <ol class="steps">
    <li>Every synthetic dataset (method × seed) is ranked against all the others on each metric:
    rank 1 is the highest score, or the lowest risk for the privacy metrics. Ties share the
    lowest rank.</li>
    <li>The rank-derived score of a method on a metric is the mean rank of its datasets.</li>
    <li>A pillar score is the mean of the rank-derived scores of the pillar's metrics.</li>
    <li>The meta-score is the weighted sum of the pillar scores (weights summing to 1). Lower is
    better.</li>
  </ol>
  <p>Ranks compress the size of the differences: read the metric values alongside the ranking.</p>
</section>"""


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def write_html_report(result, config: BenchmarkConfig, filename: str = "report.html") -> str:
    """Write the self-contained HTML report to ``config.output_dir`` and return its path."""
    os.makedirs(config.output_dir, exist_ok=True)
    path = os.path.join(config.output_dir, filename)
    if result.composite is None or not result.metascore:
        body = '<section><h2>No result</h2><p>No metric was evaluated.</p></section>'
        data = {}
        n_sets = 0
        methods = []
    else:
        methods = list(result.composite.sort_values("Total", kind="stable").index)
        colors = _method_colors(methods)
        pillars = pillar_scores(result.metascore)
        data = {
            "methods": methods,
            "colors": colors,
            "pillars": [p for p in PILLARS if p in pillars.columns],
            "scores": {m: [float(pillars.loc[m, p]) for p in PILLARS if p in pillars.columns] for m in methods},
            "scenarios": [{"name": n, "w": list(map(float, w))} for n, w in (config.scenarios or {}).items()
                          if len(pillars.columns) > 1
                          and sum(x for p, x in zip(PILLARS, w) if p in pillars.columns) > 0],
            "weights": list(map(float, config.weights)),
        }
        body = (_ranking_section(result, config, colors) + _sensitivity_section(result, config)
                + _metrics_section(result, colors) + _method_section())
        n_sets = int(sum(df.shape[0] for df in result.per_dim_values.values()) / max(len(result.per_dim_values), 1))
    seeds = sorted({int(s) for df in result.per_dim_values.values() for s in df["Seed"]}) if result.per_dim_values else []
    meta = (f"{len(methods)} methods · {len(seeds)} seed{'s' if len(seeds) != 1 else ''} · "
            f"{n_sets} synthetic datasets · {len(result.dims_run)} of 12 metrics · {date.today().isoformat()}")
    page = (_PAGE.replace("%%META%%", _esc(meta))
            .replace("%%BODY%%", body)
            .replace("%%DATA%%", json.dumps(data).replace("</", "<\\/")))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>SynOmicsBench Benchmark Report</title>
<style>
/* Layout: one reading column (max 1080px) under a red brand rule, as the SynOmicsBench docs;
   summary first (ranking), then sensitivity, then the metric detail. */
:root {
  --brand: #E2001A;          /* CEA red, docs primary colour */
  --brand-dark: #C10016;
  --bg: #FFFFFF;
  --panel: #F5F7F9;          /* docs light neutral */
  --line: #E0E4E8;           /* docs tab border */
  --ink: #1E2A31;
  --muted: #455A64;          /* docs tab text */
  --faint: #78909C;
  --link: #0D47A1;           /* docs content links */
  --stat: #2F6DB5;           /* pillar colours of the manuscript: blue, purple, red */
  --bio: #7B4FA2;
  --priv: #D2453F;
  --best: #E8F3EC;
  --best-ink: #1B6B3A;
  --font: Roboto, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --mono: "Roboto Mono", "SFMono-Regular", Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --brand: #FF3B4E; --brand-dark: #E2001A; --bg: #151A1E; --panel: #1D2429; --line: #2E383F;
    --ink: #E6ECEF; --muted: #B0BEC5; --faint: #8796A0; --link: #82B1FF;
    --stat: #6FA3E0; --bio: #B08AD6; --priv: #F07068; --best: #18352A; --best-ink: #8FD9A8;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --brand: #FF3B4E; --brand-dark: #E2001A; --bg: #151A1E; --panel: #1D2429; --line: #2E383F;
  --ink: #E6ECEF; --muted: #B0BEC5; --faint: #8796A0; --link: #82B1FF;
  --stat: #6FA3E0; --bio: #B08AD6; --priv: #F07068; --best: #18352A; --best-ink: #8FD9A8;
  color-scheme: dark;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.6 var(--font); }
a { color: var(--link); }
.brandbar { height: 4px; background: var(--brand); }
header.top, main, footer {
  max-width: 1080px; margin: 0 auto;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
}
header.top { padding-block: 28px 8px; border-bottom: 1px solid var(--line); }
.eyebrow { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--brand); font-weight: 700; }
h1 { font-size: 28px; line-height: 1.2; margin: 4px 0 6px; font-weight: 700; text-wrap: balance; }
.meta { color: var(--muted); font-size: 13px; margin: 0 0 12px; font-variant-numeric: tabular-nums; }
nav.toc { display: flex; flex-wrap: wrap; gap: 4px 20px; font-size: 13px; padding-block: 6px 10px; }
nav.toc a { color: var(--muted); text-decoration: none; border-bottom: 2px solid transparent; padding-bottom: 2px; }
nav.toc a:hover, nav.toc a:focus-visible { color: var(--brand); border-bottom-color: var(--brand); outline: none; }
main { padding-block: 8px 40px; }
section { padding-block: 24px 8px; }
section + section { border-top: 1px solid var(--line); }
h2 { font-size: 21px; margin: 0 0 8px; font-weight: 700; text-wrap: balance; }
h3 { font-size: 15px; margin: 24px 0 8px; font-weight: 700; color: var(--ink); display: flex; align-items: center; gap: 8px; }
p { max-width: 70ch; margin: 0 0 10px; }
.lede { color: var(--muted); }
.note { font-size: 13px; color: var(--muted); border-left: 3px solid var(--brand); padding: 6px 10px; background: var(--panel); max-width: none; }
.scroll { overflow-x: auto; }
table.data { border-collapse: collapse; width: 100%; font-size: 13.5px; }
table.data th { text-align: left; font-weight: 500; color: var(--muted); font-size: 12px; padding: 8px 10px;
  border-bottom: 2px solid var(--line); vertical-align: bottom; white-space: nowrap; }
table.data td { padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
table.data tr:last-child td { border-bottom: none; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.data th.num { text-align: right; }
.strong { font-weight: 700; }
.rank { color: var(--faint); width: 3em; }
.chip { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; font-weight: 500; }
.chip i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; flex: none; }
.key { width: 10px; height: 10px; display: inline-block; margin-right: 6px; vertical-align: -1px; flex: none; }
.key.stat, .seg.stat { background: var(--stat); }
.key.bio, .seg.bio { background: var(--bio); }
.key.priv, .seg.priv { background: var(--priv); }
.w { color: var(--faint); font-size: 11px; }
.barcell { width: 32%; min-width: 160px; }
.stack { display: flex; height: 12px; background: var(--panel); }
.seg { display: block; height: 100%; }
.seg + .seg { box-shadow: inset 1px 0 0 var(--bg); }
table.metrics th { white-space: normal; min-width: 110px; }
table.metrics th:first-child { min-width: 0; }
.dir { display: block; color: var(--faint); font-size: 11px; font-weight: 400; }
td .sd { display: block; color: var(--faint); font-size: 11.5px; }
td .r { display: block; color: var(--muted); font-size: 11.5px; }
td.best { background: var(--best); color: var(--best-ink); font-weight: 700; }
td.best .r, td.best .sd { color: var(--best-ink); font-weight: 400; }
.missing ul { margin: 0; padding-left: 20px; color: var(--muted); font-size: 13.5px; }
.scen-wrap { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 24px; align-items: start; }
.scen-wrap > * { min-width: 0; }
#scen-table th { white-space: normal; min-width: 92px; }
#scen-table th .wts { display: block; white-space: nowrap; font-size: 11px; color: var(--faint); font-weight: 400; font-variant-numeric: tabular-nums; }
.scen-desc { margin: 0 0 18px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px 24px; max-width: none; }
.scen-desc dt { font-weight: 600; font-size: 14px; color: var(--ink); }
.scen-desc dt .wts { font-weight: 400; font-size: 12px; color: var(--faint); font-variant-numeric: tabular-nums; margin-left: 4px; }
.scen-desc dd { margin: 2px 0 0; font-size: 13px; color: var(--muted); }
.scen-desc > div { min-width: 0; }
.bump { margin: 0; }
.bump svg { width: 100%; height: auto; display: block; }
.tri-wrap { display: grid; grid-template-columns: minmax(0, 460px) minmax(0, 1fr); gap: 28px; align-items: start; }
.tri-wrap > * { min-width: 0; }
.tri { margin: 0; }
.tri-stage { position: relative; width: 100%; max-width: 460px; aspect-ratio: 460 / 420; }
.tri-stage canvas, .tri-stage svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.tri-stage canvas { cursor: crosshair; touch-action: none; }
.tri-stage svg { pointer-events: none; }
.tri-controls { display: flex; gap: 8px; align-items: center; font-size: 13px; color: var(--muted); margin-top: 8px; }
select, input[type=range] { accent-color: var(--brand); }
select { font: inherit; color: var(--ink); background: var(--bg); border: 1px solid var(--line); padding: 4px 6px; }
select:focus-visible, input:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.readout { background: var(--panel); border-left: 4px solid var(--brand); padding: 12px 14px; }
.weights { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; margin-bottom: 8px; }
.weights b { color: var(--ink); }
.ranklist { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; counter-reset: r; }
.ranklist li { display: grid; grid-template-columns: 1.6em minmax(0, 1fr) auto; align-items: center; gap: 8px; font-size: 14px; }
.ranklist li .n { color: var(--faint); font-variant-numeric: tabular-nums; }
.ranklist li .s { font-variant-numeric: tabular-nums; color: var(--muted); }
.ranklist li:first-child { font-weight: 700; }
.sliders { display: grid; gap: 2px; margin-top: 14px; font-size: 13px; color: var(--muted); }
.sliders input { width: 100%; }
.sliders output { color: var(--ink); font-variant-numeric: tabular-nums; margin-left: 4px; }
.hint { font-size: 13px; margin: 0; }
table.share { margin-top: 14px; }
.steps { padding-left: 20px; max-width: 72ch; }
.steps li { margin-bottom: 6px; }
footer { color: var(--faint); font-size: 12px; padding-block: 16px 32px; border-top: 1px solid var(--line); }
@media (max-width: 820px) {
  .scen-wrap, .tri-wrap, .scen-desc { grid-template-columns: minmax(0, 1fr); }
  .barcell { min-width: 120px; }
}
@media (prefers-reduced-motion: no-preference) { nav.toc a { transition: color .15s, border-color .15s; } }
</style>
</head>
<body>
<div class="brandbar"></div>
<header class="top">
  <div class="eyebrow">SynOmicsBench · Automatic benchmark</div>
  <h1>Benchmark report</h1>
  <p class="meta">%%META%%</p>
  <nav class="toc" aria-label="Sections">
    <a href="#ranking">Ranking</a><a href="#sensitivity">Sensitivity to the weights</a>
    <a href="#metrics">Metrics</a><a href="#method">How it is computed</a>
  </nav>
</header>
<main>
%%BODY%%
</main>
<footer>Generated by SynOmicsBench. Tables of this report are also written as CSV files next to it.</footer>
<script>
(function () {
  "use strict";
  var D = %%DATA%%;
  if (!D.methods) return;
  var M = D.methods, P = D.pillars, S = D.scores, C = D.colors;
  var css = getComputedStyle(document.documentElement);
  function tok(n) { return css.getPropertyValue(n).trim(); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  var ALL = ["Statistical fidelity", "Biological utility", "Privacy"];
  var SHORT = {"Statistical fidelity": "Fidelity", "Biological utility": "Utility", "Privacy": "Privacy"};

  // Meta-score of every method for full (stat, bio, priv) weights, restricted to the evaluated pillars.
  function totals(w3) {
    var w = P.map(function (p) { return w3[ALL.indexOf(p)]; });
    var sum = w.reduce(function (a, b) { return a + b; }, 0) || 1;
    return M.map(function (m) {
      var t = 0;
      for (var i = 0; i < P.length; i++) t += S[m][i] * w[i] / sum;
      return {m: m, t: t};
    });
  }
  function ranked(w3) {
    var tt = totals(w3);
    var order = tt.slice().sort(function (a, b) { return a.t - b.t || M.indexOf(a.m) - M.indexOf(b.m); });
    var rank = {};
    order.forEach(function (o, i) {
      rank[o.m] = (i > 0 && Math.abs(o.t - order[i - 1].t) < 1e-12) ? rank[order[i - 1].m] : i + 1;
    });
    return {order: order, rank: rank};
  }
  function chip(m) { return '<span class="chip"><i style="background:' + C[m] + '"></i>' + esc(m) + '</span>'; }

  // ---- scenario table and bump chart -------------------------------------------------
  var SC = D.scenarios;
  var res = SC.map(function (s) { return ranked(s.w); });
  var tbl = document.getElementById("scen-table");
  if (tbl && SC.length) {
    var h = "<tr><th>Method</th>" + SC.map(function (s) {
      return '<th class="num">' + esc(s.name) + '<span class="wts">' + s.w.map(function (x) { return x.toFixed(2); }).join(" / ") + "</span></th>";
    }).join("") + "</tr>";
    var first = res[0].order.map(function (o) { return o.m; });
    first.forEach(function (m) {
      h += "<tr><td>" + chip(m) + "</td>" + res.map(function (r) {
        var t = r.order.filter(function (o) { return o.m === m; })[0].t;
        return '<td class="num"><b>' + r.rank[m] + '</b> <span style="color:var(--faint)">' + t.toFixed(2) + "</span></td>";
      }).join("") + "</tr>";
    });
    tbl.innerHTML = h + '<tr><td colspan="' + (SC.length + 1) + '" style="color:var(--faint);font-size:12px">Rank, then meta-score. Weights: statistical fidelity / biological utility / privacy.</td></tr>';
  }
  var bump = document.getElementById("bump-svg");
  if (bump && SC.length) {
    var W = 420, H = 40 + 34 * M.length, x0 = 110, x1 = W - 30, y0 = 34;
    var dx = SC.length > 1 ? (x1 - x0) / (SC.length - 1) : 0;
    var ink = tok("--ink"), faint = tok("--faint"), line = tok("--line");
    var g = '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none"/>';
    SC.forEach(function (s, j) {
      var x = x0 + j * dx;
      g += '<line x1="' + x + '" x2="' + x + '" y1="' + (y0 - 6) + '" y2="' + (H - 12) + '" stroke="' + line + '"/>';
      var label = s.name.split(" ")[0];
      g += '<text x="' + x + '" y="16" text-anchor="middle" font-size="11" fill="' + faint + '">' + esc(label) + "</text>";
    });
    function yr(r) { return y0 + (r - 1) * 34; }
    M.forEach(function (m) {
      var pts = res.map(function (r, j) { return [x0 + j * dx, yr(r.rank[m])]; });
      g += '<polyline fill="none" stroke="' + C[m] + '" stroke-width="3" points="' + pts.map(function (p) { return p.join(","); }).join(" ") + '"/>';
      pts.forEach(function (p, j) {
        g += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="9" fill="' + C[m] + '"/>';
        g += '<text x="' + p[0] + '" y="' + (p[1] + 4) + '" text-anchor="middle" font-size="10.5" font-weight="700" fill="#1E2A31">' + res[j].rank[m] + "</text>";
      });
      g += '<text x="' + (x0 - 16) + '" y="' + (yr(res[0].rank[m]) + 4) + '" text-anchor="end" font-size="12" fill="' + ink + '">' + esc(m) + "</text>";
    });
    bump.setAttribute("viewBox", "0 0 " + W + " " + H);
    bump.innerHTML = g;
  }

  // ---- weight triangle ----------------------------------------------------------------
  var cv = document.getElementById("tri-canvas");
  if (!cv || P.length < 3) return;
  var svg = document.getElementById("tri-svg");
  var VW = 460, VH = 420;
  var A = [230, 34], B = [40, 362], Cc = [420, 362];   // top: fidelity, left: utility, right: privacy
  function toXY(w) { return [w[0] * A[0] + w[1] * B[0] + w[2] * Cc[0], w[0] * A[1] + w[1] * B[1] + w[2] * Cc[1]]; }
  function toW(x, y) {
    var det = (B[1] - Cc[1]) * (A[0] - Cc[0]) + (Cc[0] - B[0]) * (A[1] - Cc[1]);
    var a = ((B[1] - Cc[1]) * (x - Cc[0]) + (Cc[0] - B[0]) * (y - Cc[1])) / det;
    var b = ((Cc[1] - A[1]) * (x - Cc[0]) + (A[0] - Cc[0]) * (y - Cc[1])) / det;
    return [a, b, 1 - a - b];
  }
  function hexRGB(hx) { var n = parseInt(hx.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  var mode = document.getElementById("tri-color");
  mode.innerHTML = '<option value="">Method ranked first</option>' + M.map(function (m) {
    return '<option value="' + esc(m) + '">Rank of ' + esc(m) + "</option>"; }).join("");

  // share of the 0.01 grid where each method ranks first
  var share = {}; M.forEach(function (m) { share[m] = 0; });
  var npts = 0;
  for (var i = 0; i <= 100; i++) for (var j = 0; j <= 100 - i; j++) {
    var o = ranked([i / 100, j / 100, (100 - i - j) / 100]).order[0].m; share[o]++; npts++;
  }
  var st = document.getElementById("tri-share");
  st.innerHTML = '<tr><th>Method</th><th class="num">Ranked first</th></tr>' + M.slice().sort(function (a, b) { return share[b] - share[a]; }).map(function (m) {
    return "<tr><td>" + chip(m) + '</td><td class="num">' + (100 * share[m] / npts).toFixed(1) + " % of the weights</td></tr>"; }).join("");

  function paint() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.round(VW * dpr), hh = Math.round(VH * dpr);
    cv.width = w; cv.height = hh;
    var ctx = cv.getContext("2d");
    var img = ctx.createImageData(w, hh), px = img.data;
    var target = mode.value, n = M.length;
    var rgb = {}; M.forEach(function (m) { rgb[m] = hexRGB(C[m]); });
    var lo = hexRGB(tok("--panel").length === 7 ? tok("--panel") : "#F5F7F9");
    var hi = hexRGB(target ? C[target] : "#000000");
    var idx = target ? M.indexOf(target) : -1, tot = new Float64Array(n);
    var pw = P.map(function (p) { return ALL.indexOf(p); });
    for (var y = 0; y < hh; y++) for (var x = 0; x < w; x++) {
      var wv = toW(x / dpr, y / dpr);
      if (wv[0] < -1e-9 || wv[1] < -1e-9 || wv[2] < -1e-9) continue;
      var best = 0, c;
      for (var q = 0; q < n; q++) {
        var t = 0, sc = S[M[q]];
        for (var z = 0; z < pw.length; z++) t += sc[z] * wv[pw[z]];
        tot[q] = t;
        if (t < tot[best] - 1e-12) best = q;
      }
      if (idx < 0) c = rgb[M[best]];
      else {
        var below = 0;
        for (var q2 = 0; q2 < n; q2++) if (tot[q2] < tot[idx] - 1e-12) below++;
        var f = n > 1 ? (n - 1 - below) / (n - 1) : 1;      // 1 for rank 1, 0 for last
        c = [lo[0] + (hi[0] - lo[0]) * f, lo[1] + (hi[1] - lo[1]) * f, lo[2] + (hi[2] - lo[2]) * f];
      }
      var k = 4 * (y * w + x); px[k] = c[0]; px[k + 1] = c[1]; px[k + 2] = c[2]; px[k + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    drawOverlay();
  }
  var cur = D.weights.slice();
  function drawOverlay() {
    var ink = tok("--ink"), faint = tok("--faint"), bg = tok("--bg");
    var g = '<polygon points="' + [A, B, Cc].map(function (p) { return p.join(","); }).join(" ") + '" fill="none" stroke="' + ink + '" stroke-width="1"/>';
    [0.25, 0.5, 0.75].forEach(function (t) {       // faint iso-weight lines
      [[0, 1, 2], [1, 2, 0], [2, 0, 1]].forEach(function (k) {
        var p = [0, 0, 0], q = [0, 0, 0];
        p[k[0]] = t; p[k[1]] = 1 - t; q[k[0]] = t; q[k[2]] = 1 - t;
        var a = toXY(p), b = toXY(q);
        g += '<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] + '" stroke="' + bg + '" stroke-opacity=".55" stroke-width="1"/>';
      });
    });
    g += '<text x="' + A[0] + '" y="' + (A[1] - 12) + '" text-anchor="middle" font-size="12" fill="' + ink + '">Statistical fidelity</text>';
    g += '<text x="' + B[0] + '" y="' + (B[1] + 22) + '" text-anchor="start" font-size="12" fill="' + ink + '">Biological utility</text>';
    g += '<text x="' + Cc[0] + '" y="' + (Cc[1] + 22) + '" text-anchor="end" font-size="12" fill="' + ink + '">Privacy</text>';
    SC.forEach(function (s) {
      var p = toXY(s.w);
      g += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="6" fill="none" stroke="' + ink + '" stroke-width="1.5"/>';
      g += '<text x="' + (p[0] + 9) + '" y="' + (p[1] + 4) + '" font-size="10.5" fill="' + ink + '" stroke="' + bg + '" stroke-width="3" paint-order="stroke">' + esc(s.name.split(" ")[0]) + "</text>";
    });
    var c = toXY(cur);
    g += '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="5" fill="' + bg + '" stroke="' + ink + '" stroke-width="2"/>';
    svg.innerHTML = g;
  }
  var oS = document.getElementById("o-stat"), oB = document.getElementById("o-bio"), oP = document.getElementById("o-priv");
  var sS = document.getElementById("w-stat"), sB = document.getElementById("w-bio"), sP = document.getElementById("w-priv");
  function show(w) {
    cur = w;
    var r = ranked(w);
    document.getElementById("tri-weights").innerHTML = ALL.map(function (p, i) {
      return '<span><span class="key ' + ["stat", "bio", "priv"][i] + '"></span>' + SHORT[p] + " <b>" + w[i].toFixed(2) + "</b></span>"; }).join("");
    document.getElementById("tri-ranks").innerHTML = r.order.map(function (o) {
      return '<li><span class="n">' + r.rank[o.m] + "</span>" + chip(o.m) + '<span class="s">' + o.t.toFixed(2) + "</span></li>"; }).join("");
    sS.value = Math.round(w[0] * 100); sB.value = Math.round(w[1] * 100); sP.value = Math.round(w[2] * 100);
    oS.textContent = w[0].toFixed(2); oB.textContent = w[1].toFixed(2); oP.textContent = w[2].toFixed(2);
    drawOverlay();
  }
  function snap(w) {
    var a = Math.round(Math.max(0, w[0]) * 100), b = Math.round(Math.max(0, w[1]) * 100);
    if (a + b > 100) b = 100 - a;
    return [a / 100, b / 100, (100 - a - b) / 100];
  }
  function pointer(ev) {
    var rc = cv.getBoundingClientRect();
    var x = (ev.clientX - rc.left) * VW / rc.width, y = (ev.clientY - rc.top) * VH / rc.height;
    var w = toW(x, y);
    if (w[0] < -0.02 || w[1] < -0.02 || w[2] < -0.02) return;
    show(snap(w));
  }
  cv.addEventListener("pointermove", pointer);
  cv.addEventListener("pointerdown", pointer);
  function fromSliders(k) {
    // k: index of the moved slider; the other two share the rest in their current proportion
    var v = [+sS.value, +sB.value, +sP.value].map(function (x) { return x / 100; });
    var o = [0, 1, 2].filter(function (i) { return i !== k; });
    var rest = 1 - v[k], prev = cur[o[0]] + cur[o[1]];
    var a = prev > 0 ? rest * cur[o[0]] / prev : rest / 2;
    var w = [0, 0, 0]; w[k] = v[k]; w[o[0]] = a; w[o[1]] = rest - a;
    show(snap(w));
  }
  sS.addEventListener("input", function () { fromSliders(0); });
  sB.addEventListener("input", function () { fromSliders(1); });
  sP.addEventListener("input", function () { fromSliders(2); });
  var legend = document.getElementById("tri-legend");
  function setLegend() {
    legend.textContent = mode.value ? "Darker: better rank of " + mode.value + " (darkest = ranked first, lightest = ranked last)."
                                    : "Each colour is the method ranked first at these weights.";
  }
  mode.addEventListener("change", function () { setLegend(); paint(); });
  setLegend();
  paint();
  show(D.weights.map(function (x) { return x / D.weights.reduce(function (a, b) { return a + b; }, 0); }));
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var re = function () { css = getComputedStyle(document.documentElement); paint(); show(cur); };
    if (mq.addEventListener) mq.addEventListener("change", re);
  }
})();
</script>
</body>
</html>
"""
