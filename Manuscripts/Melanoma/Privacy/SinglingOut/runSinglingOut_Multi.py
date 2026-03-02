import pandas as pd
import numpy as np
from SinglingOut import SinglingOutEvaluator
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.processing.postprocessing import post_masking
import logging
import pickle
from singlingout_experiment import eval_singlingout_multivariate

logging.basicConfig(filename=f"annonymeter_singlingout_multivariate.log", level=logging.DEBUG)

src_path = '../../Data/'
seeds = [0,1,2,3,42]

#Load original data:
original_data = pd.read_csv(src_path+'original_data.csv', index_col = 0)
masked_ori = post_masking(original_data)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]

for seed in seeds:
    synthetic_dict = {}
    syn_datasets = [f"avatarsk5_{seed}",f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
    for synthetic in syn_datasets:
        syn = pd.read_csv(src_path + synthetic + '.csv', index_col = 0)

        masked_syn_df = post_masking(syn)
        masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
        synthetic_dict[synthetic] = masked_syn_df

    #Run SinglingOut
    
    multi_so_risks = eval_singlingout_multivariate(
        ori = masked_ori,
        syns = synthetic_dict,
        test_cases = [2,3,5,7,10,20,50],
        n_attacks = 10_000,
        max_attempts = 1_000_000, 
        seed=seed
    )
    SOMulti_results = f"MultiSO/Seed_{seed}/MultiSO_Results.pkl"

    # --- Saving the dictionary (using 'wb' for 'write binary') ---
    try:
        with open(SOMulti_results, 'wb') as file:
            pickle.dump(multi_so_risks, file)
        print(f"Dictionary successfully saved to **{SOMulti_results}**.")
    except Exception as e:
        print(f"An error occurred while saving: {e}")
    
    
    
        

