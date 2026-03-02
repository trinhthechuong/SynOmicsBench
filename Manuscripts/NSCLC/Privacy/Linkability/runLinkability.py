from linkability_evaluator import LinkabilityEvaluator
from link_genes_clinical import eval_genes_clinical
import pandas as pd
import numpy as np
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.processing.postprocessing import post_masking
import logging
import pickle
seed = 42

logging.basicConfig(filename=f"anonymeter_linkability_{seed}.log", level=logging.DEBUG)

src_path = '../../Data/'

seeds = [0,1,2,3,42]

#Load original data
original_data = pd.read_csv(src_path+'original_data.csv', index_col = 0)
masked_ori = post_masking(original_data)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]

for seed in seeds:
    synthetic_dict = {}
    syn_datas = [f"avatarsk5_{seed}",f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
    for synthetic in syn_datas:
        syn = pd.read_csv(src_path + synthetic + ".csv", index_col = 0)
        masked_syn_df = post_masking(syn)
        masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
        synthetic_dict[synthetic] = masked_syn_df

    #Run link
    linkability_res_genes_to_clinical = eval_genes_clinical(masked_ori, synthetic_dict, num_clinical= 14, n_neighbors = 1)
    linkability_results = f"Seed_{seed}/LinkabilityResults.pkl"
    # --- Saving the dictionary (using 'wb' for 'write binary') ---
    try:
        with open(linkability_results, 'wb') as file:
            pickle.dump(linkability_res_genes_to_clinical, file)
        print(f"Dictionary successfully saved to **{linkability_results}**.")
    except Exception as e:
        print(f"An error occurred while saving: {e}")
 
        

    
        



