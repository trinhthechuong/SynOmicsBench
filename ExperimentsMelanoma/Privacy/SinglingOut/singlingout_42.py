import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from SinglingOut import SinglingOutEvaluator
# from anonymeter.evaluators import LinkabilityEvaluator
# from anonymeter.evaluators import InferenceEvaluator 
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.processing.postprocessing import post_masking
from SynOmics.utils.monitoring import monitor_resources
import pickle


import logging

# i = "avatarsk5_0"




ori = pd.read_csv("../Data/original_data.csv", index_col = 0)
masked_ori = post_masking(ori)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]


seed = 42
seed_value = 42
rng = np.random.default_rng(seed_value)
max_attempts = 1_000_000
n_cols_to_try = [1000, 5000, 10000, 40992] 

@monitor_resources
def singling_out(ori, syn, n_cols_to_try, max_attempts, seed):
    # print(f"---{i}---")
    risk_tool = []
    evaluator_tool = []
    for n_col in n_cols_to_try:
        print(f"----{n_col}---")
        ori_test = ori.iloc[:, 0: n_col]
        syn_test = syn.iloc[:,0:n_col]
        evaluator = SinglingOutEvaluator(ori=ori_test, 
                                     syn=syn_test, 
                                     n_attacks=10_000,
                                    max_attempts = 1_000_000, seed = seed
                                        )
        evaluator.evaluate(mode="univariate")
        risk = evaluator.risk()
        print(f"{n_col} columns Risk{risk}")
        risk_tool.append(risk)
        evaluator_tool.append(evaluator)
    return evaluator_tool, risk_tool

syn_datas = [f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
for syn_data in syn_datas:
    print(f"---Tool: {syn_data}---")
    logging.basicConfig(filename=f"anonymeter_singlingout_{syn_data}.log", level=logging.DEBUG)
    syn_df = pd.read_csv(f"../Data/{syn_data}.csv", index_col = 0)
    masked_syn_df = post_masking(syn_df)
    masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
    evaluator_singling, singlingout_risk = singling_out(masked_ori, masked_syn_df, n_cols_to_try, max_attempts, seed)
    # Save to pickle
    with open(f"evaluator_singling_{syn_data}_{seed}.pkl", "wb") as f:
        pickle.dump(evaluator_singling, f)
    
    with open(f"singlingout_risk_{syn_data}_{seed}.pkl", "wb") as f:
        pickle.dump(singlingout_risk, f)
