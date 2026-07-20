"""
Self-contained HTML report for the automatic benchmark.

Produces a single ``report.html`` (inline CSS, figures embedded as base64 PNGs —
no external/CDN dependencies) that walks the reader through a clear narrative:

    per dimension  ->  per pillar  ->  overall meta-rank

with a color-coded table at each level for transparency. The page is generic
(labels derived from the inputs), so it suits any cohort/method set — not tailored
to any particular study.

Design choices follow the dataviz guidance:
- method identity uses the established categorical palette ``DATASET_COLORS``;
- ranks use a diverging green->gray->red map (two hues + neutral gray midpoint,
  not a rainbow), rank 1 = green (best);
- legends are always shown for >=2 series; grids are recessive; exact numbers live
  in the tables, not only in the figures.
"""

from __future__ import annotations

import base64
import html
import io
import os
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from synomicsbench.metrics.fidelity.visualization import DATASET_COLORS
from .config import BenchmarkConfig, ALL_DIMS
from .metascore import COMPONENT_COLORS, plot_weighted_composite_scores


# Diverging rank colormap: rank 1 (best) = green, midpoint = neutral gray, worst = red.
RANK_CMAP = LinearSegmentedColormap.from_list(
    "rank_good_bad", ["#1a9850", "#f0f0f0", "#d73027"]
)
INK = "#1f2933"
MUTED = "#66727f"
SURFACE = "#ffffff"
PANEL = "#f7f9fb"
BORDER = "#e3e8ee"


# ---------------------------------------------------------------------------
# figure helpers
# ---------------------------------------------------------------------------

def _fig_to_base64(fig, dpi: int = 150) -> str:
    """Serialize a matplotlib figure to a base64 PNG data URI, then close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii")


def _method_order(result, config: BenchmarkConfig) -> List[str]:
    present = list(result.value_table.index) if not result.value_table.empty else []
    ordered = [m for m in config.name_map if m in present]
    return ordered + [m for m in present if m not in ordered]


def _rank_heatmap_fig(rank_table: pd.DataFrame, methods: List[str], n_candidates: int):
    dims = [d for d in ALL_DIMS if d in rank_table.columns]
    mat = rank_table.loc[methods, dims].to_numpy(dtype=float)
    n = len(methods)
    fig, ax = plt.subplots(figsize=(1.15 * len(dims) + 2.2, 0.62 * n + 1.4))
    ax.imshow((mat - 1) / max(n_candidates - 1, 1), cmap=RANK_CMAP, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels(dims, rotation=35, ha="right", fontsize=9, color=INK)
    ax.set_yticks(range(n))
    ax.set_yticklabels(methods, fontsize=9, color=INK)
    for i in range(n):
        for j in range(len(dims)):
            v = mat[i, j]
            ax.text(j, i, f"{v:.1f}" if v % 1 else f"{int(v)}", ha="center", va="center",
                    fontsize=9, color="#1a1a1a", fontweight="bold")
    ax.set_xticks(np.arange(-0.5, len(dims), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Mean rank per dimension  (1 = best, green)", fontsize=11,
                 color=INK, fontweight="bold", pad=10)
    fig.tight_layout()
    return fig


def _per_metric_bars_fig(value_table: pd.DataFrame, methods: List[str]):
    dims = [d for d in ALL_DIMS if d in value_table.columns]
    x = np.arange(len(dims))
    n = len(methods)
    width = 0.8 / max(n, 1)
    fig, ax = plt.subplots(figsize=(1.5 * len(dims) + 1, 4.6))
    for i, m in enumerate(methods):
        ax.bar(x + i * width, value_table.loc[m, dims].to_numpy(dtype=float), width,
               label=m, color=DATASET_COLORS.get(m, "#9aa5b1"), edgecolor="white", linewidth=0.8)
    ax.set_xticks(x + width * (n - 1) / 2)
    ax.set_xticklabels(dims, rotation=30, ha="right", fontsize=9, color=INK)
    ax.set_ylabel("Score (higher = better)", fontsize=10, color=INK)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8, ncol=min(n, 3), frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    return fig


def _radar_fig(value_table: pd.DataFrame, methods: List[str]):
    dims = [d for d in ALL_DIMS if d in value_table.columns]
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6.4, 6.4), subplot_kw={"polar": True})
    for m in methods:
        vals = value_table.loc[m, dims].to_numpy(dtype=float).tolist()
        vals += vals[:1]
        color = DATASET_COLORS.get(m, "#9aa5b1")
        ax.plot(angles, vals, color=color, linewidth=1.8, label=m)
        ax.fill(angles, vals, color=color, alpha=0.06)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dims, fontsize=8.5, color=INK)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.0"], fontsize=7, color=MUTED)
    ax.tick_params(pad=8)
    ax.grid(color=BORDER, linewidth=0.8)
    ax.spines["polar"].set_color(BORDER)
    ax.set_title("All-round profile  (score 0–1, larger = better)", fontsize=11,
                 color=INK, fontweight="bold", pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.12), fontsize=8, frameon=False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _chip(method: str) -> str:
    c = DATASET_COLORS.get(method, "#9aa5b1")
    return (f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
            f'background:{c};margin-right:7px;vertical-align:middle"></span>'
            f'<span style="vertical-align:middle">{html.escape(method)}</span>')


def _score_bg(v: float) -> str:
    """Subtle sequential shading for a 0..1 score (higher = deeper teal)."""
    if not np.isfinite(v):
        return ""
    t = max(0.0, min(1.0, float(v)))
    return f"background:rgba(38,132,125,{0.06 + 0.42 * t:.3f})"


def _fmt(v, nd=3) -> str:
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def _scores_table(value_table: pd.DataFrame, methods: List[str]) -> str:
    dims = [d for d in ALL_DIMS if d in value_table.columns]
    head = "".join(f"<th>{html.escape(d)}</th>" for d in dims)
    rows = []
    for m in methods:
        cells = "".join(
            f'<td style="text-align:center;{_score_bg(value_table.loc[m, d])}">{_fmt(value_table.loc[m, d])}</td>'
            for d in dims
        )
        rows.append(f"<tr><td class='rowhead'>{_chip(m)}</td>{cells}</tr>")
    return _table_html("Per-metric scores (higher = better)", f"<th>Method</th>{head}", rows)


def _pillar_table(composite: pd.DataFrame) -> str:
    cols = ["Broad Utility", "Narrow Utility", "Privacy", "Total"]
    head = "".join(
        f'<th style="color:{COMPONENT_COLORS.get(c, INK)}">{html.escape(c)}</th>' for c in cols
    )
    df = composite.sort_values("Total")
    rows = []
    for m in df.index:
        cells = "".join(f'<td style="text-align:center">{_fmt(df.loc[m, c])}</td>' for c in cols)
        rows.append(f"<tr><td class='rowhead'>{_chip(m)}</td>{cells}</tr>")
    return _table_html("Pillar sub-scores &amp; total (lower rank-derived score = better)",
                       f"<th>Method</th>{head}", rows)


def _ranking_table(composite: pd.DataFrame) -> str:
    df = composite.sort_values("Total")
    rows = []
    for pos, (m, row) in enumerate(df.iterrows(), 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, "")
        hl = ' style="background:#eaf6ee;font-weight:600"' if pos == 1 else ""
        rows.append(
            f"<tr{hl}><td style='text-align:center'>{pos} {medal}</td>"
            f"<td class='rowhead'>{_chip(m)}</td>"
            f"<td style='text-align:center'>{_fmt(row['Total'])}</td></tr>"
        )
    return _table_html("Overall ranking (lower Total = more balanced)",
                       "<th>#</th><th>Method</th><th>Total</th>", rows)


def _table_html(caption: str, header_cells: str, rows: List[str]) -> str:
    return (
        f'<table><caption>{caption}</caption>'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _img(src: str, alt: str) -> str:
    return f'<img src="{src}" alt="{html.escape(alt)}" loading="lazy"/>'


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------

def write_html_report(result, config: BenchmarkConfig, filename: str = "report.html") -> str:
    """Write a self-contained HTML report and return its path."""
    os.makedirs(config.output_dir, exist_ok=True)
    methods = _method_order(result, config)
    has_composite = result.composite is not None and not result.value_table.empty

    # Distinct (method, seed) candidates across all dimensions — the pool that gets ranked.
    pairs = {(row.Model, int(row.Seed))
             for df in result.per_dim_values.values() for row in df.itertuples()}
    seeds_per_method = {m: sorted(s for mm, s in pairs if mm == m) for m in methods}
    seed_counts = {m: len(v) for m, v in seeds_per_method.items()}
    balanced = len(set(seed_counts.values())) <= 1
    # Scale that mean ranks live on (rank 1..n_candidates); used for heatmap color + notes.
    n_candidates = len(pairs) if pairs else len(methods)

    # --- figures (embedded) ---
    figs: Dict[str, str] = {}
    if not result.rank_table.empty:
        figs["heatmap"] = _fig_to_base64(_rank_heatmap_fig(result.rank_table, methods, n_candidates))
    if not result.value_table.empty:
        figs["bars"] = _fig_to_base64(_per_metric_bars_fig(result.value_table, methods))
        figs["radar"] = _fig_to_base64(_radar_fig(result.value_table, methods))
    if has_composite:
        fig, _ = plot_weighted_composite_scores(
            result.metascore, broad_weight=config.weights[0], narrow_weight=config.weights[1],
            privacy_weight=config.weights[2], save_path=None,
        )
        figs["composite"] = _fig_to_base64(fig)

    # --- header / winner ---
    if has_composite:
        winner = result.composite["Total"].idxmin()
        wc = DATASET_COLORS.get(winner, "#26847d")
        hero = (
            f'<div class="hero" style="border-left:6px solid {wc}">'
            f'<div class="hero-label">🏆 Most balanced method</div>'
            f'<div class="hero-name" style="color:{wc}">{html.escape(str(winner))}</div>'
            f'<div class="hero-sub">Total rank-derived score '
            f'{result.composite["Total"].min():.2f} — lower is better</div></div>'
        )
    else:
        hero = ('<div class="hero"><div class="hero-sub">Composite not available — '
                'not all dimensions were evaluated.</div></div>')

    dims_run = ", ".join(result.dims_run) if result.dims_run else "none"
    n_methods = len(methods)
    seeds = sorted({int(s) for df in result.per_dim_values.values() for s in df["Seed"]}) \
        if result.per_dim_values else []
    n_seeds = len(seeds)

    # Prominent run-summary chips (so single- vs multi-seed is obvious at a glance).
    seed_label = "Seed" if n_seeds == 1 else "Seeds"
    seed_val = (", ".join(map(str, seeds)) if 0 < n_seeds <= 8 else f"{n_seeds}")
    # Only claim an "M×S" grid when seed counts are equal across methods.
    cand_detail = f"{n_methods}×{seed_counts[methods[0]]}" if (balanced and methods) else "unbalanced"
    chips = [
        ("Methods", str(n_methods)),
        (seed_label, f"{n_seeds} ({seed_val})" if seeds else "—"),
        ("Dimensions", str(len(result.dims_run))),
        ("Candidates ranked", f"{n_candidates}  ({cand_detail})"),
    ]
    chips_html = "".join(
        f'<div class="chip"><div class="chip-label">{html.escape(k)}</div>'
        f'<div class="chip-val">{html.escape(v)}</div></div>' for k, v in chips
    )
    # Aggregation note: single seed ranks per-seed; multi-seed may collapse some dims.
    if n_seeds <= 1 and balanced:
        agg_note = "Single-seed run — every dimension ranked over the {} methods.".format(n_methods)
    else:
        collapsed = [d for d in getattr(config, "collapse_dims", ()) if d in result.dims_run]
        base = ("Multi-seed run — {} candidates ranked per dimension; each method's score is the "
                "mean rank of its own seeds.").format(n_candidates)
        if collapsed:
            base += " {} collapsed to a per-method mean before ranking (manuscript-compatible).".format(
                ", ".join(collapsed))
        agg_note = base
    # Warn when seed counts differ across methods (uneven ranking pool).
    if not balanced:
        detail = "; ".join(f"{m}: {seed_counts[m]}" for m in methods)
        agg_note += (" ⚠ Unbalanced seeds per method ({}). Methods with more seeds are estimated "
                     "more stably; for a fair comparison use the same seed count per method.").format(detail)

    sections = [f'<section>{hero}<div class="chips">{chips_html}</div>'
                f'<p class="meta">Dimensions: {dims_run}.<br>{html.escape(agg_note)}</p></section>']

    # --- Level 1: per dimension ---
    lvl1 = ['<h2>1 · Per dimension</h2>',
            '<p class="lead">How each method performs on every individual metric.</p>']
    if "heatmap" in figs:
        lvl1.append(f'<div class="fig">{_img(figs["heatmap"], "rank heatmap")}</div>')
    if "bars" in figs:
        lvl1.append(f'<div class="fig">{_img(figs["bars"], "per-metric score bars")}</div>')
    # Note: the exact mean ranks are already annotated in the heatmap above, so we show
    # only the per-metric *scores* table here (ranks would duplicate the heatmap).
    if not result.value_table.empty:
        lvl1.append(_scores_table(result.value_table, methods))
    sections.append("<section>" + "".join(lvl1) + "</section>")

    # --- Level 2: per pillar ---
    if has_composite:
        lvl2 = ['<h2>2 · Per pillar</h2>',
                '<p class="lead">The eight dimensions roll up into three equally-weighted pillars: '
                f'<b style="color:{COMPONENT_COLORS["Broad Utility"]}">Broad Utility</b> '
                f'(fidelity), <b style="color:{COMPONENT_COLORS["Narrow Utility"]}">Narrow Utility</b> '
                f'(biology), and <b style="color:{COMPONENT_COLORS["Privacy"]}">Privacy</b>.</p>']
        if "radar" in figs:
            lvl2.append(f'<div class="fig">{_img(figs["radar"], "all-round radar")}</div>')
        lvl2.append(_pillar_table(result.composite))
        sections.append("<section>" + "".join(lvl2) + "</section>")

    # --- Level 3: overall ---
    if has_composite:
        lvl3 = ['<h2>3 · Overall meta-rank</h2>',
                '<p class="lead">Pillars combined into one balanced score. Lower = more balanced '
                'across utility and privacy.</p>']
        if "composite" in figs:
            lvl3.append(f'<div class="fig">{_img(figs["composite"], "composite stacked bar")}</div>')
        lvl3.append(_ranking_table(result.composite))
        sections.append("<section>" + "".join(lvl3) + "</section>")

    page = _PAGE_TEMPLATE.format(css=_CSS, body="".join(sections))
    path = os.path.join(config.output_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin:0; background:#eef1f5; color:#1f2933;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.5; }
.wrap { max-width:1040px; margin:0 auto; padding:32px 20px 64px; }
h1 { font-size:26px; margin:0 0 4px; letter-spacing:-.01em; }
.subtitle { color:#66727f; margin:0 0 24px; font-size:14px; }
h2 { font-size:19px; margin:34px 0 4px; }
.lead { color:#66727f; margin:0 0 16px; font-size:14px; }
.meta { color:#66727f; font-size:13px; margin:14px 0 0; }
section { background:#fff; border:1px solid #e3e8ee; border-radius:14px;
  padding:22px 24px; margin:0 0 20px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
.hero { background:#f7f9fb; border-radius:12px; padding:18px 22px; }
.hero-label { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:#66727f; }
.hero-name { font-size:30px; font-weight:750; margin:2px 0 2px; letter-spacing:-.02em; }
.hero-sub { color:#66727f; font-size:14px; }
.chips { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0 4px; }
.chip { flex:1 1 130px; background:#f7f9fb; border:1px solid #e3e8ee; border-radius:10px;
  padding:10px 14px; }
.chip-label { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#66727f; }
.chip-val { font-size:18px; font-weight:700; color:#1f2933; margin-top:2px; }
.fig { text-align:center; margin:12px 0 18px; }
.fig img { max-width:100%; height:auto; border-radius:8px; }
table { border-collapse:collapse; width:100%; margin:14px 0 8px; font-size:13px;
  overflow-x:auto; display:block; }
caption { caption-side:top; text-align:left; font-weight:650; font-size:13px;
  color:#1f2933; padding:6px 2px 10px; }
th,td { border-bottom:1px solid #eef1f5; padding:7px 10px; white-space:nowrap; }
thead th { color:#66727f; font-weight:600; text-align:center; border-bottom:2px solid #e3e8ee;
  position:sticky; top:0; background:#fff; }
td.rowhead { text-align:left; font-weight:500; }
footer { color:#9aa5b1; font-size:12px; text-align:center; padding:8px 0; }
@media (prefers-color-scheme: dark) {
  body { background:#0f1419; color:#e4e8ee; }
  section { background:#161b22; border-color:#242b34; box-shadow:none; }
  .hero,.chip { background:#1b2028; border-color:#242b34; }
  .chip-val { color:#e4e8ee; }
  .subtitle,.lead,.meta,.hero-sub,.hero-label,.chip-label { color:#9aa5b1; }
  h1,h2,.hero-name { color:#e4e8ee; }
  thead th { background:#161b22; border-bottom-color:#242b34; color:#9aa5b1; }
  th,td { border-bottom-color:#242b34; }
  caption { color:#e4e8ee; }
}
"""

_PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SynOmicsBench — Automatic Benchmark Report</title>
<style>{css}</style></head>
<body><div class="wrap">
<h1>SynOmicsBench — Automatic Benchmark Report</h1>
<p class="subtitle">Synthetic data generation, ranked across fidelity, biological utility and privacy.</p>
{body}
<footer>Generated by synomicsbench.autobenchmark</footer>
</div></body></html>
"""
