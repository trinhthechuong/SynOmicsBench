import random 
import pickle
import sys
parent_dir = "/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline"
sys.path.append(parent_dir)
from SynOmics.utils.monitoring import monitor_resources
from SinglingOut import SinglingOutEvaluator


@monitor_resources
def eval_singlingout_uni(ori, syns, n_attacks = 10_000, max_attempts = 1_000_000, seed=42):
    results_dict = {}
    for syn, syn_df in syns.items():
        print(f"----{syn}----")
        random.seed(42)
        cols = ori.columns.tolist()
        
        risks = []
        proportions = [0.25,0.50, 0.75,1]
        for p in proportions:
            n = int(len(cols) * p)
            sampled_cols = random.sample(cols, n)
            print(f"Sample {len(sampled_cols)} cols among {len(cols)}")
            sampled_ori = ori[sampled_cols]
            sampled_syn = syn_df[sampled_cols]
            print(sampled_ori.head(5), sampled_ori.shape)
            print(sampled_syn.head(5),sampled_syn.shape)

            evaluator = SinglingOutEvaluator(
        ori=sampled_ori, syn=sampled_syn, n_attacks=n_attacks, max_attempts = max_attempts, seed = seed)
            evaluator.evaluate(mode='univariate')

            print(f"Sample {len(sampled_cols)}/{p}%: risk {evaluator.risk()}")

            risks.append(evaluator)
     
        results_dict[syn] = risks
    return results_dict


@monitor_resources
def eval_singlingout_multivariate(ori, syns, test_cases, n_attacks = 10_000,max_attempts = 1_000_000, seed=42):
    results_dict = {}
    for syn, syn_df in syns.items():
        print(f"----{syn}----")
        risks = []
        # n_cols = [2,3,5,7,10,20,50,100]
        for n_col in test_cases:
            evaluator = SinglingOutEvaluator(
        ori=ori, syn=syn_df, n_cols = n_col, n_attacks=n_attacks, max_attempts = max_attempts, seed = seed)
            
            evaluator.evaluate(mode='multivariate')
            
            print(f"Attack {n_col}: risk {evaluator.risk()}")
            
            risks.append(evaluator)
            
        results_dict[syn] = risks
        
    return results_dict



        
            
            
