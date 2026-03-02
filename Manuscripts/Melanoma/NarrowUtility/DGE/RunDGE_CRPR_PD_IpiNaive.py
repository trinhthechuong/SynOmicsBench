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
responderCrit = original_data['BR'].isin(['CR','PR'])
progressorCrit = original_data['BR'].isin(['PD'])

responders = original_data[responderCrit].index
progressors = original_data[progressorCrit].index

original_data.loc[responders,"Labels"] = 'Responder'
original_data.loc[progressors,"Labels"] = 'Progressor'
original_data = original_data[original_data['daysBiopsyAfterIpiStart']=='noIpi']
seeds = [42, 0, 1, 2, 3]

for seed in seeds:
    # Initialize dataset dict per-seed to avoid accumulation across seeds
    dataset_dict: Dict[str, pd.DataFrame] = {}
    dataset_dict["Origin"] = original_data.copy()

    syn_datas = [f"avatarsk5_{seed}", f"avatarsk10_{seed}", f"ctgan_{seed}", f"gaussiancopula_{seed}", f"synthpop_{seed}", f"tvae_{seed}"]
    print(seed, syn_datas)
    for i, tool in enumerate(syn_datas):
        syn_df = pd.read_csv(f"../../Data/{syn_datas[i]}.csv", index_col=0)
        responderCrit = syn_df['BR'].isin(['CR','PR'])
        progressorCrit = syn_df['BR'].isin(['PD'])
        
        responders = syn_df[responderCrit].index
        progressors = syn_df[progressorCrit].index
        
        syn_df.loc[responders,"Labels"] = 'Responder'
        syn_df.loc[progressors,"Labels"] = 'Progressor'
        syn_df = syn_df[syn_df['daysBiopsyAfterIpiStart']=='noIpi']
        dataset_dict[tool] = syn_df


    genes_cols = original_data.iloc[:,54:-1].columns.tolist()
    symbols_dataset_dict = {}
    for tool, data in dataset_dict.items():
        # If some ENSG columns are missing in a dataset, selecting will raise KeyError.
        # Use intersection to be robust.
        present_genes_cols = [c for c in genes_cols if c in data.columns]
        genes_exp_df = data[present_genes_cols]
        # Rename column
        genes_exp_df_mapped = genes_exp_df.copy()
        # genes_exp_df_mapped.columns = [ensembl_to_hugo(col, genes_mapping) for col in genes_exp_df_mapped.columns]

        # drop_cols = [col for col in genes_exp_df_mapped.columns if col.startswith("ENSG")]
        # genes_exp_df_mapped = genes_exp_df_mapped.drop(columns=drop_cols)

        genes_exp_df_mapped_t = genes_exp_df_mapped.T.reset_index()
        genes_exp_df_mapped_t.columns.values[0] = 'Gene'

        # Averaging duplicated genes
        # genes_exp_df_mapped_t_grouped = genes_exp_df_mapped_t.groupby("Gene", as_index=False).mean()
        symbols_dataset_dict[tool] = genes_exp_df_mapped_t

    # Create per-seed output directory
    os.makedirs(f'Ipinaive/Seed_{seed}', exist_ok=True)

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
             "Labels": data['Labels'].values.tolist()}
        )
        # gene_expressions = data[genelist]
        gene_expressions = symbols_dataset_dict.get(name)
        if gene_expressions is None:
            print(f"Skipping {name}: no expression table prepared.")
            continue
        id_col = "Patient"
        phenotypes = {"Labels": ["Responder", "Progressor"]}
        
        try:
            degs_df = dge_analysis(gene_expressions, metadata, phenotypes, id_col, n_jobs=-1)
            degs_df.to_csv(f"Ipinaive/Seed_{seed}/DGE_{name}.csv", index=False)
            degs_results[name] = degs_df
        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}")

    # Ensure Origin DGE is present before downstream comparisons
    if "Origin" not in degs_results:
        print("Warning: Origin DGE not found in degs_results for this seed. Skipping Jaccard/Spearman.")
        continue

    # orig_genes = extract_significant_genes(degs_results["Origin"], term_col="Gene", adj_p_col="Q_value", threshold=0.05)
    # if len(orig_genes) = 0
    # synth_genes_dict = {k: extract_significant_genes(v, term_col="Gene", adj_p_col="P_value", threshold=0.05)
    #                     for k, v in degs_results.items() if k != "Origin"}
    # jaccard_df = compute_jaccard_indices(orig_genes, synth_genes_dict)
    # jaccard_df.to_csv(f"CRPR_PD/Seed_{seed}/JaccardIndex_{seed}_NivoBenefit.csv", index=False)

    # spearmanDF, RankScoreDF = compare_spearman_degs(
    #     degs_results,
    #     origin='Origin',
    #     term_col="Gene",
    #     lfc_col="Log2FC",
    #     q_col="Q_value")
    # spearmanDF.to_csv(f"CRPR_PD/Seed_{seed}/Spearman_{seed}_NivoBenefit.csv", index=False)
    # RankScoreDF.to_csv(f"CRPR_PD/Seed_{seed}/GeneRankScore_{seed}_NivoBenefit.csv", index=False)