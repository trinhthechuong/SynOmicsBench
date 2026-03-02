# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple, Any, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATASET_COLORS: Dict[str, str] = {
    "Origin": "#4d4d4d",
    "Avatars K5":  "#66c2a5",
    "Avatars K10": "#fc8d62",
    "CTGAN":  "#8da0cb",
    "Gaussian Copula":   "#e78ac3",
    "Synthpop":  "#a6d854",
    "TVAE":  "#ffd92f",
}


def _apply_plot_style():
    """Apply matplotlib styles."""
    try:
        plt.style.use(["science", "nature", "notebook"])
    except Exception:
        pass

    plt.rcParams.update({
        'text.usetex': False,
        'axes.edgecolor': '#333333',
        'xtick.minor.visible': False,
        'ytick.minor.visible': False,
        'xtick.top': False,
        'ytick.right': False,
    })


def plot_logistic_regression_replicates(
    Result_As_Seed: Dict[int, Dict[str, Dict[str, Dict[str, Any]]]],
    synthesizer_names: Sequence[str],
    metric_name: str = "ROC-AUC",
    classifier_name: str = "Logistic_Regression",
    p_value_key: str = "p_value",  # Use unadjusted p-value
    significance_threshold: float = 0.05,
    save_path: Optional[str] = None,
    figsize: Tuple[float, float] = (20, 8),
    all_seeds: Optional[List[int]] = None,  # Expected seeds list
) -> None:
    """
    Plot boxplots for Logistic Regression across all 5 replicates (seeds).
    Each synthesizer will have 5 boxplots (one per seed).
    Mark replicates with asterisk (*) if p-value > significance_threshold (comparable performance).
    Show placeholder boxes for missing seeds (e.g., TVAE seeds 1, 3).

    Args:
        Result_As_Seed: nested dict: Result_As_Seed[seed][synth_name][classifier_name]
        synthesizer_names: list of synthesizer names to plot
        metric_name: y-axis label
        classifier_name: which classifier to extract (default: "Logistic_Regression")
        p_value_key: which p-value to use ("p_value" for unadjusted)
        significance_threshold: p-value threshold (default 0.05)
        save_path: optional path to save figure
        figsize: figure size
        all_seeds: list of all expected seeds (e.g., [0, 1, 2, 3, 42])

    Returns:
        None
    """
    _apply_plot_style()

    if all_seeds is None:
        all_seeds = sorted(Result_As_Seed.keys())
    else:
        all_seeds = sorted(all_seeds)
    
    origin_color = DATASET_COLORS.get("Origin", "#4d4d4d")
    
    # Collect data
    positions: List[float] = []
    data_list: List[List[float]] = []
    colors_list: List[str] = []
    labels_list: List[str] = []
    
    # For annotations
    p_values_list: List[Optional[float]] = []
    is_comparable_list: List[bool] = []
    is_missing_list: List[bool] = []  # Track missing data
    
    start_x = 0.0
    group_centers: List[float] = []
    group_labels: List[str] = []
    group_bounds: List[Tuple[float, float]] = []
    
    # First, add Origin (aggregate all seeds)
    origin_data_all = []
    for seed in all_seeds:
        if seed not in Result_As_Seed:
            continue
        for synth_name in synthesizer_names:
            if synth_name in Result_As_Seed[seed] and classifier_name in Result_As_Seed[seed][synth_name]:
                real_scores = Result_As_Seed[seed][synth_name][classifier_name].get("real_scores", [])
                if real_scores:
                    origin_data_all.extend([float(v) for v in real_scores])
                    break  # Only need to add once per seed
        
    if origin_data_all:
        positions.append(start_x)
        data_list.append(origin_data_all)
        colors_list.append(origin_color)
        labels_list.append("Origin\n(all seeds)")
        p_values_list.append(None)
        is_comparable_list.append(False)
        is_missing_list.append(False)
        start_x += 1.5  # Extra gap after Origin
    
    # Now add each synthesizer with ALL expected seeds (including missing ones)
    for synth_name in synthesizer_names:
        group_positions = []
        synth_color = DATASET_COLORS.get(synth_name, "#888888")
        
        for seed in all_seeds:
            # Check if data exists for this seed
            has_data = (
                seed in Result_As_Seed and
                synth_name in Result_As_Seed[seed] and
                classifier_name in Result_As_Seed[seed][synth_name]
            )
            
            if has_data:
                result = Result_As_Seed[seed][synth_name][classifier_name]
                synth_scores = result.get("synthetic_scores", [])
                
                if synth_scores:
                    # Normal case: data exists
                    p_val = result.get(p_value_key, None)
                    if p_val is not None:
                        p_val = float(p_val)
                    
                    is_comparable = (p_val is not None) and (p_val > significance_threshold)
                    
                    positions.append(start_x)
                    data_list.append([float(v) for v in synth_scores])
                    colors_list.append(synth_color)
                    labels_list.append(f"{synth_name}\nSeed {seed}")
                    p_values_list.append(p_val)
                    is_comparable_list.append(is_comparable)
                    is_missing_list.append(False)
                    group_positions.append(start_x)
                    
                    start_x += 1.0
                    continue
            
            # Missing data: create placeholder
            positions.append(start_x)
            data_list.append([0.0])  # Placeholder value
            colors_list.append("#e0e0e0")  # Gray color for missing
            labels_list.append(f"{synth_name}\nSeed {seed}")
            p_values_list.append(None)
            is_comparable_list.append(False)
            is_missing_list.append(True)
            group_positions.append(start_x)
            
            start_x += 1.0
        
        if group_positions:
            center = float(np.mean(group_positions))
            group_centers.append(center)
            group_labels.append(synth_name)
            group_bounds.append((min(group_positions), max(group_positions)))
            start_x += 0.8  # Gap between synthesizers
    
    if not data_list:
        raise ValueError("No data found for plotting.")
    
    # Create plot
    fig, ax = plt.subplots(figsize=figsize)
    
    flierprops = dict(marker="o", markersize=3, markeredgecolor="#666666", alpha=0.6)
    medianprops = dict(linewidth=1.5, color="black")
    whiskerprops = dict(linewidth=0.9, color="#333333")
    capprops = dict(linewidth=0.9, color="#333333")
    boxprops = dict(linewidth=1.0)
    
    bp = ax.boxplot(
        data_list,
        positions=positions,
        widths=0.7,
        patch_artist=True,
        showfliers=True,
        flierprops=flierprops,
        medianprops=medianprops,
        whiskerprops=whiskerprops,
        capprops=capprops,
        boxprops=boxprops,
    )
    
    # Color boxes
    for i, (box, color, is_missing) in enumerate(zip(bp["boxes"], colors_list, is_missing_list)):
        box.set_facecolor(color)
        if is_missing:
            box.set_edgecolor("#999999")
            box.set_linewidth(1.0)
            box.set_linestyle("--")  # Dashed line for missing
            box.set_alpha(0.5)
        else:
            box.set_edgecolor("#222222")
            box.set_linewidth(1.0)
            box.set_alpha(0.85)
    
    # Style whiskers, caps, medians
    for i, (whisk, is_missing) in enumerate(zip(bp.get("whiskers", []), is_missing_list * 2)):  # *2 because 2 whiskers per box
        if i // 2 < len(is_missing_list) and is_missing_list[i // 2]:
            whisk.set_alpha(0.3)
        else:
            whisk.set_color("#222222")
    
    for i, (cap, is_missing) in enumerate(zip(bp.get("caps", []), is_missing_list * 2)):
        if i // 2 < len(is_missing_list) and is_missing_list[i // 2]:
            cap.set_alpha(0.3)
        else:
            cap.set_color("#222222")
    
    for i, (med, is_missing) in enumerate(zip(bp.get("medians", []), is_missing_list)):
        if is_missing:
            med.set_alpha(0.3)
        else:
            med.set_color("black")
            med.set_linewidth(1.6)
    
    # Calculate y-range for positioning (exclude missing data)
    valid_data = [d for d, is_miss in zip(data_list, is_missing_list) if not is_miss]
    if valid_data:
        y_min = min([min(d) for d in valid_data])
        y_max = max([max(d) for d in valid_data])
    else:
        y_min, y_max = 0.0, 1.0
    
    y_range = y_max - y_min if y_max > y_min else 1.0
    y_off_mean = y_range * 0.02
    y_off_star = y_range * 0.06
    
    # Add mean markers and asterisk annotations
    for pos, values, is_comparable, is_missing in zip(positions, data_list, is_comparable_list, is_missing_list):
        if is_missing:
            # Add "N/A" text for missing data
            ax.text(pos, y_min + y_range * 0.5, "N/A", ha="center", va="center",
                    fontsize=10, color="#999999", fontweight="bold", style="italic")
            continue
        
        m = float(np.mean(values))
        
        # Mean marker (simple diamond)
        ax.scatter(
            pos, m,
            facecolor="white",
            edgecolors="#d32f2f",
            marker="D",
            s=60,
            zorder=11,
            linewidths=1.5,
        )
        
        # Mean text
        ax.text(pos, m + y_off_mean, f"{m:.3f}", ha="center", va="bottom", 
                fontsize=8, color="#111111", fontweight="normal")
        
        # Asterisk for comparable replicates
        if is_comparable:
            ax.text(pos, y_max + y_off_star, "*", ha="center", va="bottom",
                    fontsize=20, color="#2e7d32", fontweight="bold")
    
    # Set x-ticks at group centers
    ax.set_xticks([positions[0]] + group_centers)
    ax.set_xticklabels(["Origin"] + [f"$\\mathbf{{{label}}}$" for label in group_labels], 
                       rotation=0, ha="center", fontsize=11)
    
    # Vertical separators
    for lb, ub in group_bounds:
        sep_x = ub + 0.4
        ax.axvline(x=sep_x, color="#bdbdbd", linestyle="--", linewidth=1.0, alpha=0.5)
    
    ax.set_xlabel("Synthesizer (5 replicates each)", fontsize=12, fontweight="bold")
    ax.set_ylabel(metric_name, fontsize=12, fontweight="bold")
    title = f"{metric_name} Distribution: {classifier_name.replace('_', ' ')} Across 5 Seeds"
    ax.set_title(title, fontsize=14, fontweight="bold")
    
    # Legend
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    
    origin_patch = mpatches.Patch(color=origin_color, label="Origin (Real)", alpha=0.85)
    
    star_proxy = Line2D([0], [0], marker='*', color='w', 
                        markerfacecolor='#2e7d32', markersize=15,
                        label=f'* Comparable (p > {significance_threshold})', linestyle='None')
    
    missing_patch = mpatches.Patch(facecolor='#e0e0e0', edgecolor='#999999', 
                                   linestyle='--', linewidth=1.0,
                                   label='N/A (Missing data)', alpha=0.5)
    
    ax.legend(handles=[origin_patch, star_proxy, missing_patch], 
             loc="upper right", frameon=True, fontsize=10, fancybox=True, shadow=True)
    
    # Adjust y-axis to make room for asterisks
    ax.set_ylim(y_min - y_range * 0.05, y_max + y_range * 0.15)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
    
    plt.show()
    plt.close()