import pandas as pd
import numpy as np
import sys
parent_path = '/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline'
sys.path.append(parent_path)
from SynOmics.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
from SynOmics.processing.metadata import MetaData
from SynOmics.processing.postprocessing import post_masking
from typing import Dict, Optional, Tuple
import seaborn as sns
import matplotlib.pyplot as plt
import itertools
from scipy import stats
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import matplotlib as mpl
from numpy.random import default_rng
from BroadUtility import plot_violin

###### Data. ######
or_data = pd.read_csv("../Data/original_data.csv", index_col = 0)
transcriptomics_or_data = or_data.iloc[:,54:]
metadata = MetaData.get_metadata(data = transcriptomics_or_data, 
                                 threshold_unique_values = 10, 
                                    ordinal_features = None,
                                    transcriptomic_cols =transcriptomics_or_data.columns.tolist())
seeds = [42,0,1,2,3]

def save_results(path, result):
    result_arr = np.asarray(result)
    np.save(path, result_arr)

    
results_all = {}
n = int(1e6)
rng = default_rng(42) 
for seed in seeds:
    print(f"---Seed {seed}---")
    syn_datas = [f"avatarsk5_{seed}",f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
    results_seed = {}
    visulize_results_dict = {}
    visulize_results_dict_filtered = {}
    visulize_results_dict_filtered_low = {}
    for syn_data in syn_datas:
        print(f"---Method {syn_data}---")
        syn_df = pd.read_csv(f"../Data/{syn_data}.csv", index_col = 0)
        transcriptomics_syn_df = syn_df.iloc[:,54:]
        # masked_syn_clinical_df = post_masking(clinical_syn_df)
        pw_computer = PairwiseSimilarity(
        original_data = transcriptomics_or_data,
        synthetic_data = transcriptomics_syn_df,
        metadata = metadata,
        output_dir = f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}",
        verbose = True,
        save = True,
        name = syn_data
    )
        result = pw_computer.get_pairwise_scores(method = "spearman")
        results_seed[syn_data] =result
        correlations_scores = result["PairwiseScore"]
        or_correlations = result["OriginalCorrelation"]
        indices = rng.choice(correlations_scores.shape[0], size=n, replace=False)
        sampling_scores = correlations_scores[indices]
        # sampling_or_correlations = or_correlations[indices]

        high_score_indices = np.where(np.absolute(or_correlations) >= 0.5)[0] 
        high_scores = correlations_scores[high_score_indices]
        
        if high_scores.shape[0] <= n: # Use shape[0] for array length check
            chosing_scores = high_scores
        else:
            # Sample only if the number of high scores is greater than n
            sampled_high_indices = rng.choice(high_scores.shape[0], size=n, replace=False)
            chosing_scores = high_scores[sampled_high_indices]

        # Filter for low original correlation scores (|r| < 0.5)
        # NOTE: Using [0] to extract the array of indices from the np.where tuple
        low_score_indices = np.where(np.absolute(or_correlations) < 0.5)[0]
        low_scores = correlations_scores[low_score_indices]
        
        if low_scores.shape[0] <= n: # Use shape[0] for array length check
            chosing_low_scores = low_scores
        else:
            # Sample only if the number of low scores is greater than n
            sampled_low_indices = rng.choice(low_scores.shape[0], size=n, replace=False)
            chosing_low_scores = low_scores[sampled_low_indices]
            
        visulize_results_dict[syn_data] = sampling_scores
        visulize_results_dict_filtered[syn_data] = chosing_scores
        visulize_results_dict_filtered_low[syn_data] = chosing_low_scores # <-- FIX B: This line now works

        path_score = f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}/{syn_data}_all.npy"
        save_results(path_score, correlations_scores)

        path_score_filtered = f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}/{syn_data}_filtered.npy"
        save_results(path_score_filtered, high_scores)
        
    title_sampling = f'Distribution of pairwise similarity scores (Transcriptomics Features)'
    fig_sampling, ax = plot_violin(
        visulize_results_dict,
        title=title_sampling,
        annotate=True,
        figsize=(10, 5),
    )
                                    
    fig_sampling.savefig(f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}/Benchmark_PaiwiseTranscriptomics_{seed}.png", dpi=300, bbox_inches='tight')
    
    title_filtered = f'Distribution of pairwise similarity scores (Transcriptomics Features)'
    fig_filtered, ax = plot_violin(
        visulize_results_dict_filtered,
        title=title_filtered,
        annotate=True,
        figsize=(10, 5),
    )
    fig_filtered.savefig(f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}/Benchmark_PaiwiseTranscriptomics_Filter_{seed}.png", dpi=300, bbox_inches='tight')


    title_filtered = f'Distribution of pairwise similarity scores (Transcriptomics Features)'
    fig_filtered_low, ax = plot_violin(
        visulize_results_dict_filtered_low,
        title=title_filtered,
        annotate=True,
        figsize=(10, 5),
    )
    fig_filtered_low.savefig(f"PairwiseTranscriptomicsSimi/PairwiseTranscriptomicsSimi_{seed}/Benchmark_PaiwiseTranscriptomics_FilterLow_{seed}.png", dpi=300, bbox_inches='tight')


    
