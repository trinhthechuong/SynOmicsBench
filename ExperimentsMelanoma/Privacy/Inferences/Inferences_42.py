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

seed = 42
logging.basicConfig(filename=f"anonymeter_inferences_{seed}.log", level=logging.DEBUG)

ori = pd.read_csv("../Data/original_data.csv", index_col = 0)
masked_ori = post_masking(ori)
masked_ori.columns = [col.replace('.', '_') for col in masked_ori.columns]

syn_datas = [f"avatarsk10_{seed}",f"ctgan_{seed}",f"gaussiancopula_{seed}",f"synthpop_{seed}",f"tvae_{seed}"]
synthetic_dict = {}
for syn_data in syn_datas:
    syn_df = pd.read_csv(f"../Data/{syn_data}.csv", index_col = 0)
    masked_syn_df = post_masking(syn_df)
    masked_syn_df.columns = [col.replace('.', '_') for col in masked_syn_df.columns]
    synthetic_dict[syn_data] = masked_syn_df


@monitor_resources
def inferences_genes_clinical(ori, syns, save_path=None):
    cols = ori.columns.tolist()

    genes_cols = ori.columns.tolist()[47:]
    clinical_cols = ori.columns.tolist()[:47]

    results_as_tool = {}  

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
with open(f"results_inferences_{seed}.pkl", "wb") as f:
    pickle.dump(results_inferences, f)
