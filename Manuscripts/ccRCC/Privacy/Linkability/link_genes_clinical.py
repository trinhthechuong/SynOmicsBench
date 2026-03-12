import random
import pickle
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.utils.monitoring import monitor_resources
from linkability_evaluator import LinkabilityEvaluator #this one the code base from Anonymeter

@monitor_resources
def eval_genes_clinical(ori, syns, num_clinical, n_neighbors):
    results_dict = {}
    for syn, syn_df in syns.items():
        print(f"----{syn}----")
        random.seed(42)
        cols = ori.columns.tolist()
        genes_cols = ori.columns.tolist()[num_clinical:]
        clinical_cols = ori.columns.tolist()[:num_clinical]  
        risks = []
        proportions = [0.25,0.50, 0.75,1]
        for p in proportions:
            n = int(len(genes_cols) * p)
            
            sampled_genes_cols = random.sample(genes_cols, n)
            print(f"Sample {len(sampled_genes_cols)} cols among {len(genes_cols)}")
            aux_cols = [clinical_cols, sampled_genes_cols]
            evaluator = LinkabilityEvaluator(ori=ori, 
                                             syn=syn_df, 
                                             n_attacks=ori.shape[0],
                                             aux_cols=aux_cols,
                                             n_neighbors=n_neighbors)
            evaluator.evaluate(n_jobs=-2)  # n_jobs follow joblib convention. -1 = all cores, -2 = all execept one
            evaluator.risk()
            print(f"{p}", evaluator.risk(n_neighbors=n_neighbors))
            risks.append(evaluator)
        results_dict[syn] = risks
    return results_dict