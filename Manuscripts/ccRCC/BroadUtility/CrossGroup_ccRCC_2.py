import pandas as pd
import numpy as np
import sys
import os
parent_path = '/mnt/digphat/syntheticDataBenchmark/Chuong_pipeline'
sys.path.append(parent_path)
from SynOmics.metrics.fidelity.PairwiseSimilarity import PairwiseSimilarity
from SynOmics.processing.metadata import MetaData
from SynOmics.processing.postprocessing import post_masking

###### Data Loading ######
or_data = pd.read_csv("../Data/original_data.csv", index_col=0)
or_data = post_masking(or_data)

# Define feature groups
clinical_features = or_data.columns.tolist()[0:52]
transcriptomic_features = or_data.columns.tolist()[52:]

print(f"Clinical features: {len(clinical_features)}")
print(f"Transcriptomic features: {len(transcriptomic_features)}")
print(f"Total cross-group pairs: {len(clinical_features) * len(transcriptomic_features)}")

# Get metadata for the full dataset
metadata = MetaData.get_metadata(
    data=or_data, 
    threshold_unique_values=10, 
    ordinal_features=None,
    transcriptomic_cols=transcriptomic_features
)

seeds = [3,2]

def save_results_csv(path, df):
    """Save DataFrame to CSV."""
    df.to_csv(path, index=False)
    print(f"Saved: {path}")

###### Main Loop ######
for seed in seeds:
    print(f"\n{'='*60}")
    print(f"Processing Seed: {seed}")
    print(f"{'='*60}")
    
    syn_methods = [
        f"avatarsk5_{seed}", 
        f"avatarsk10_{seed}", 
        f"ctgan_{seed}", 
        f"gaussiancopula_{seed}", 
        f"synthpop_{seed}", 
        f"tvae_{seed}"
    ]
    
    # Create output directory
    output_dir = f"PairwiseCrossGroup/CrossGroup_{seed}"
    os.makedirs(output_dir, exist_ok=True)
    
    for syn_method in syn_methods:
        print(f"\n--- Processing Method: {syn_method} ---")
        
        # Load synthetic data
        syn_df = pd.read_csv(f"../Data/{syn_method}.csv", index_col=0)
        syn_df = post_masking(syn_df)
        
        # Initialize PairwiseSimilarity with FULL dataset
        pw_computer = PairwiseSimilarity(
            original_data=or_data,
            synthetic_data=syn_df,
            metadata=metadata,
            output_dir=output_dir,
            verbose=True,
            save=False,
            name=syn_method
        )
        
        # Step 1: Compute full correlation matrices
        print("Computing correlation matrices...")
        dict_results = pw_computer.get_pairwise_scores(method="spearman", n_bins=10)
        
        # Step 2: Compute cross-group associations
        print("Computing cross-group associations...")
        cross_group_df = pw_computer.get_multiple_associations(
            feature_pairs=[
                (clin_feat, trans_feat) 
                for clin_feat in clinical_features 
                for trans_feat in transcriptomic_features
            ],
            score_matrix=dict_results['PairwiseScore'],
            original_matrix=dict_results['OriginalCorrelation'],
            synthetic_matrix=dict_results['SyntheticCorrelation'],
            condensed=True
        )
        
        print(f"Cross-group associations computed: {len(cross_group_df)} pairs")
        print(f"Mean score: {cross_group_df['Score'].mean():.4f}")
        print(f"Median score: {cross_group_df['Score'].median():.4f}")
        
        # Step 3: Save full cross-group results to CSV
        csv_path_full = os.path.join(output_dir, f"{syn_method}_cross_group_full.csv")
        save_results_csv(csv_path_full, cross_group_df)
        
        # Step 4: Filter and save high correlation pairs (|r| >= 0.5)
        high_mask = np.abs(cross_group_df['Original_Correlation']) >= 0.5
        high_df = cross_group_df[high_mask].copy()
        
        if len(high_df) > 0:
            csv_path_high = os.path.join(output_dir, f"{syn_method}_cross_group_high.csv")
            save_results_csv(csv_path_high, high_df)
            print(f"High correlation pairs (|r| >= 0.5): {len(high_df)}")
            print(f"  Mean score: {high_df['Score'].mean():.4f}")
        else:
            print("No high correlation pairs found (|r| >= 0.5)")
        
        # Step 5: Filter and save low correlation pairs (|r| < 0.5)
        low_mask = np.abs(cross_group_df['Original_Correlation']) < 0.5
        low_df = cross_group_df[low_mask].copy()
        
        if len(low_df) > 0:
            csv_path_low = os.path.join(output_dir, f"{syn_method}_cross_group_low.csv")
            save_results_csv(csv_path_low, low_df)
            print(f"Low correlation pairs (|r| < 0.5): {len(low_df)}")
            print(f"  Mean score: {low_df['Score'].mean():.4f}")
        else:
            print("No low correlation pairs found (|r| < 0.5)")
        
        # Step 6: Summary statistics
        summary_stats = {
            'Method': syn_method,
            'Seed': seed,
            'Total_Pairs': len(cross_group_df),
            'High_Corr_Pairs': len(high_df),
            'Low_Corr_Pairs': len(low_df),
            'Mean_Score_All': cross_group_df['Score'].mean(),
            'Median_Score_All': cross_group_df['Score'].median(),
            'Std_Score_All': cross_group_df['Score'].std(),
            'Mean_Score_High': high_df['Score'].mean() if len(high_df) > 0 else np.nan,
            'Mean_Score_Low': low_df['Score'].mean() if len(low_df) > 0 else np.nan,
        }
        
        # Save summary
        summary_df = pd.DataFrame([summary_stats])
        summary_path = os.path.join(output_dir, f"{syn_method}_summary.csv")
        save_results_csv(summary_path, summary_df)

print("\n" + "="*60)
print("Cross-group analysis completed!")
print("="*60)
