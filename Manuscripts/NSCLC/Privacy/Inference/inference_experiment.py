import os
import pandas as pd
from anonymeter.evaluators import InferenceEvaluator 
import pickle
import random
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.utils.monitoring import monitor_resources
import logging

@monitor_resources
def inferences_genes_clinical(ori, syns, num_clinical, save_path=None):
    cols = ori.columns.tolist()
    genes_cols = ori.columns.tolist()[num_clinical:]
    clinical_cols = ori.columns.tolist()[:num_clinical]
    results_as_tool = {}  
    for tool, syn_data in syns.items():
        results = []
        logging.info("Starting tool %s", tool)
        print(f"---{tool}---")
        for secret in clinical_cols:
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
