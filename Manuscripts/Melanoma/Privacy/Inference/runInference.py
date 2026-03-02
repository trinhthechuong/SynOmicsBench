import os
import pandas as pd
from anonymeter.evaluators import InferenceEvaluator 
from inference_experiment import inferences_genes_clinical
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.processing.postprocessing import post_masking
from tqdm import tqdm
from SynOmics.utils.monitoring import monitor_resources
import pickle
import logging

seeds = [0,1,2,3,42]

logging.basicConfig(filename=f"anonymeter_inferences.log", level=logging.DEBUG)

ori = pd.read_csv("../../Data/original_data.csv", index_col = 0)
masked_ori = post_masking(ori)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]

for seed in seeds:
    syn_datas = [f"avatarsk5_{seed}", f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
    synthetic_dict = {}
    for syn_data in syn_datas:
        syn_df = pd.read_csv(f"../../Data/{syn_data}.csv", index_col = 0)
        masked_syn_df = post_masking(syn_df)
        masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
        synthetic_dict[syn_data] = masked_syn_df
    
    results_inferences = inferences_genes_clinical(masked_ori, synthetic_dict, num_clinical=47)
    
    # Save to pickle
    with open(f"Seed_{seed}/results_inferences.pkl", "wb") as f:
        pickle.dump(results_inferences, f)
