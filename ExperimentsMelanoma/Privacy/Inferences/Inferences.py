import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from anonymeter.evaluators import InferenceEvaluator 
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.processing.postprocessing import post_masking
from tqdm import tqdm
from SynOmics.utils.monitoring import monitor_resources
import pickle
import logging
logging.basicConfig(filename="anonymeter_inferences.log", level=logging.DEBUG)

ori = pd.read_csv("OriginalData/integrated_data_final.csv", index_col = 0)
masked_ori = post_masking(ori)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]

syn_datas = ["synthetic_data_avatars_k5","synthetic_data_avatars_k10","synthetic_data_ctgan","synthetic_data_gauss_copula","synthetic_data_tvae",
             "synthetic_data_synthpop"]
tools = ["AvatarsK5", "AvatarsK10", "CTGAN","GaussianCopula", "TVAE","Synthpop"]
synthetic_dict = {}
for i, tool in enumerate(tools):
    syn_df = pd.read_csv(f"SyntheticData/{syn_datas[i]}.csv", index_col = 0)
    masked_syn_df = post_masking(syn_df)
    masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
    synthetic_dict[tool] = masked_syn_df


@monitor_resources
def inferences_genes_clinical(ori, syns, save_path=None):
    cols = ori.columns.tolist()

    genes_cols = []
    clinical_cols = []
    for col in cols:
        if col.startswith("ENSG"):
            genes_cols.append(col)
        else:
            clinical_cols.append(col)

    results_as_tool = {}  # <--- moved outside the loop to accumulate results

    for tool, syn_data in syns.items():
        results = []
        logging.info("Starting tool %s", tool)
        print(f"---{tool}---")
        for secret in tqdm(clinical_cols, desc=f"{tool} secrets"):
            try:
                evaluator = InferenceEvaluator(
                    ori=ori,
                    syn=syn_data,
                    aux_cols=genes_cols,
                    secret=secret,
                    n_attacks=ori.shape[0],
                )
                evaluator.evaluate(n_jobs=-2)
                results.append((secret, evaluator.results()))
                logging.info("Tool %s: secret %s risk=%s", tool, secret, evaluator.results().risk().value)
                print(f"Secret {secret}: Privacy Risk {evaluator.results().risk().value}")
            except Exception as ex:
                # log and store the exception so you know which secret failed
                logging.exception("Error evaluating tool=%s secret=%s: %s", tool, secret, ex)
                results.append((secret, {"error": str(ex)}))

            # optional: incremental save after each secret
            if save_path:
                results_as_tool[tool] = results
                with open(save_path, "wb") as f:
                    pickle.dump(results_as_tool, f)

        results_as_tool[tool] = results

    return results_as_tool

results_inferences = inferences_genes_clinical(masked_ori, synthetic_dict)

# Save to pickle
with open("results_inferences.pkl", "wb") as f:
    pickle.dump(results_inferences, f)
