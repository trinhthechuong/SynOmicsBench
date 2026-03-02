import pandas as pd
import numpy as np
import sys
from typing import Dict, Optional, Tuple, Any, List
import math
import json
import matplotlib.pyplot as plt
import warnings
import seaborn as sns
from DGE import dge_analysis
import os

from DGE import extract_significant_genes
from DGE import compute_jaccard_indices
from DGE import compare_spearman_degs

sys.path.append("/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/")
from SynOmics.processing.metadata import MetaData

# Load original data once
original_data = pd.read_csv("../../Data/original_data.csv", index_col=0)
# original_data = original_data[original_data['Arm']=='NIVOLUMAB']
# original_data = original_data[original_data['Benefit']!='ICB']

# # responders = original_data[original_data['Benefit'] != "NCB"].index.tolist()
# # non_responders = original_data[original_data['Benefit'] == "NCB"].index.tolist()

# # original_data['Responds'] = 'NCB'
# # original_data.loc[responders, 'Responds'] = 'CB/ICB'
# # original_data.loc[non_responders, 'Responds'] = 'NCB'

# # If you have a precomputed Origin DGE results file, it will be read per-seed below.
# # NOTE: dataset_dict and degs_results must be initialized per-seed (fixed).
# # dge_or = pd.read_csv('DGE_results/DGE_Origin.csv')  # may raise if missing; keep as-is
seeds = [0,1,2,3]

for seed in seeds:
    # Initialize dataset dict per-seed to avoid accumulation across seeds
    dataset_dict: Dict[str, pd.DataFrame] = {}
    dataset_dict["Origin"] = original_data.copy()

    syn_datas = [f"avatarsk5_{seed}", f"avatarsk10_{seed}", f"ctgan_{seed}", f"gaussiancopula_{seed}", f"synthpop_{seed}", f"tvae_{seed}"]
    print(seed, syn_datas)
    for i, tool in enumerate(syn_datas):
        syn_df = pd.read_csv(f"../../Data/{syn_datas[i]}.csv", index_col=0)
        dataset_dict[tool] = syn_df

    mapped_dataset = {}
    with open("../../Data/mapping_genes.json", "r") as f:
        genes_mapping = json.load(f)

    abnormal_counts = []
    nan_counts = []
    for k, v in genes_mapping.items():
        if isinstance(v[0], float) and math.isnan(v[0]):
            nan_counts.append([k, v])
            abnormal_counts.append([k, v])
        elif len(v) > 1 and isinstance(v[0], str):
            abnormal_counts.append([k, v])
            genes_mapping[k] = [v[0]]

    def ensembl_to_hugo(col, mapping):
        ensembl_id = col.split('.')[0]  # Remove version
        hugo = mapping.get(ensembl_id, [col])  # fallback: leave as is if not found
        return str(hugo[0])

    for k in nan_counts:
        genes_mapping.pop(k[0], None)

    genes_cols = []
    for col in original_data.columns:
        if col.startswith("ENSG"):
            genes_cols.append(col)

    symbols_dataset_dict = {}
    for tool, data in dataset_dict.items():
        # If some ENSG columns are missing in a dataset, selecting will raise KeyError.
        # Use intersection to be robust.
        present_genes_cols = [c for c in genes_cols if c in data.columns]
        genes_exp_df = data[present_genes_cols]
        # Rename column
        genes_exp_df_mapped = genes_exp_df.copy()
        genes_exp_df_mapped.columns = [ensembl_to_hugo(col, genes_mapping) for col in genes_exp_df_mapped.columns]

        drop_cols = [col for col in genes_exp_df_mapped.columns if col.startswith("ENSG")]
        genes_exp_df_mapped = genes_exp_df_mapped.drop(columns=drop_cols)

        genes_exp_df_mapped_t = genes_exp_df_mapped.T.reset_index()
        genes_exp_df_mapped_t.columns.values[0] = 'Gene'

        # Averaging duplicated genes
        genes_exp_df_mapped_t_grouped = genes_exp_df_mapped_t.groupby("Gene", as_index=False).mean()
        symbols_dataset_dict[tool] = genes_exp_df_mapped_t_grouped

    # Create per-seed output directory
    os.makedirs(f'DGE_Del9p21/Seed_{seed}', exist_ok=True)

    # Initialize degs_results per-seed
    degs_results: Dict[str, pd.DataFrame] = {}
    # If there's a precomputed global Origin DGE file, load it into degs_results for this seed
    try:
        degs_results['Origin'] = dge_or
    except Exception:
        # keep degs_results empty if DGE_Origin.csv was not read
        pass

    for name, data in dataset_dict.items():
        # if name != 'Origin':
        print(f"-----{name}------")
        metadata = pd.DataFrame(
            {"Patient": data.index,
             "Deletion_9p21.3": data['Deletion_9p21.3'].values.tolist()}
        )
        # gene_expressions = data[genelist]
        gene_expressions = symbols_dataset_dict.get(name)
        if gene_expressions is None:
            print(f"Skipping {name}: no expression table prepared.")
            continue
        id_col = "Patient"
        phenotypes = {"Deletion_9p21.3": ["MUT", "WT"]}
        
        try:
            degs_df = dge_analysis(gene_expressions, metadata, phenotypes, id_col, n_jobs=-1)
            degs_df.to_csv(f"DGE_Del9p21/Seed_{seed}/DGE_{name}.csv", index=True)
            degs_results[name] = degs_df
        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}")

    # Ensure Origin DGE is present before downstream comparisons
    if "Origin" not in degs_results:
        print("Warning: Origin DGE not found in degs_results for this seed. Skipping Jaccard/Spearman.")
        continue

    orig_genes = extract_significant_genes(degs_results["Origin"], term_col="Gene", adj_p_col="Q_value", threshold=0.05)
    synth_genes_dict = {k: extract_significant_genes(v, term_col="Gene", adj_p_col="Q_value", threshold=0.05)
                        for k, v in degs_results.items() if k != "Origin"}
    jaccard_df = compute_jaccard_indices(orig_genes, synth_genes_dict)
    jaccard_df.to_csv(f"DGE_Del9p21/Seed_{seed}/JaccardIndex_{seed}.csv", index=False)

    spearmanDF, RankScoreDF = compare_spearman_degs(
        degs_results,
        origin='Origin',
        term_col="Gene",
        lfc_col="Log2FC",
        q_col="Q_value")
    spearmanDF.to_csv(f"DGE_Nivo/Seed_{seed}/Spearman_{seed}.csv", index=False)
    RankScoreDF.to_csv(f"DGE_Nivo/Seed_{seed}/GeneRankScore_{seed}.csv", index=False)