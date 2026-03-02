import numpy as np
import pandas as pd
from typing import Dict, List, Union, Literal
import warnings
warnings.filterwarnings('ignore')

class ImmuneSignatureCalculator:
    """
    Tính toán điểm immune cell signature theo ĐÚNG phương pháp trong code R gốc
    Reference: livnatje/ImmuneResistance - ImmRes_OE. R
    """
    
    def __init__(self, 
                 expression_matrix: pd.DataFrame,
                 signatures: Dict[str, List[str]],
                 num_rounds: int = 1000,
                 n_bins: int = 50,
                 random_seed: int = 1234,
                 is_logged: bool = False):
        """
        Parameters
        ----------
        expression_matrix : pd.DataFrame
            Ma trận expression với TPM values
            Index: gene names (phải match với signatures)
            Columns: patient/sample IDs
        signatures : Dict[str, List[str]]
            Dictionary với key là tên signature, value là list gene names
        num_rounds : int
            Số lần random sampling (default: 1000)
        n_bins : int
            Số bins để phân nhóm genes (default: 50)
        random_seed : int
            Random seed (default: 1234)
        is_logged : bool
            TPM đã log-transform chưa?  False = chưa (raw TPM)
        """
        # Convert to log2(TPM+1) if needed
        if not is_logged:
            print("Converting raw TPM to log2(TPM+1)...")
            self.tpm = np.log2(expression_matrix + 1)
        else:
            self.tpm = expression_matrix. copy()
            
        self.signatures = signatures
        self.num_rounds = num_rounds
        self.n_bins = n_bins
        self.random_seed = random_seed
        
        self.genes = self.tpm.index. tolist()
        self.samples = self.tpm.columns. tolist()
        
        print(f"Initialized with {len(self.genes)} genes, {len(self.samples)} samples")
        
    def _discretize(self, values: np. ndarray, n_cat: int) -> np.ndarray:
        """
        Discretize values into bins
        Matching R code:  discretize(r$genes. dist, n. cat = 50)
        """
        # Create quantile-based bins
        quantiles = np.linspace(0, 1, n_cat + 1)
        bins = np.percentile(values, quantiles * 100)
        
        # Remove duplicates and sort
        bins = np.unique(bins)
        
        # Assign to bins (bins start from 1, not 0)
        bin_assignments = np.digitize(values, bins[:-1], right=False)
        
        return bin_assignments
    
    def _get_semi_random_OE(self, genes_dist_q, b_sign):
        """
        Get semi-random scores
        
        Matching R code: 
        get. semi.random.OE <- function(r, genes.dist. q, b.sign, num.rounds = 1000)
        
        Parameters
        ----------
        genes_dist_q : np.ndarray
            Bin assignments for all genes
        b_sign : np.ndarray
            Boolean array indicating signature genes
            
        Returns
        -------
        np.ndarray
            Random control scores for each sample
        """
        np.random.seed(self.random_seed)
        
        # Count genes in each bin for the signature
        # R code: sign.q <- as.matrix(table(genes.dist.q[b.sign]))
        signature_bins = genes_dist_q[b_sign]
        unique_bins, counts = np.unique(signature_bins, return_counts=True)
        sign_q = dict(zip(unique_bins, counts))
        
        n_genes = len(genes_dist_q)
        n_samples = len(self.samples)
        
        # Initialize matrices
        # R code: B <- matrix(data = F, nrow = length(genes.dist.q), ncol = num.rounds)
        B = np.zeros((n_genes, self.num_rounds), dtype=bool)
        
        # For each bin with signature genes
        for bin_val, num_genes_needed in sign_q.items():
            if num_genes_needed > 0:
                # Find all genes in this bin
                # R code: idx <- which(is.element(genes.dist.q, q[i]))
                idx = np.where(genes_dist_q == bin_val)[0]
                
                # Sample genes for each round
                for j in range(self.num_rounds):
                    # Exclude already selected genes in this round
                    available = idx[~B[idx, j]]
                    
                    if len(available) >= num_genes_needed: 
                        # R code: idxj <- sample(idx, num.genes)
                        sampled = np.random.choice(available, size=num_genes_needed, replace=False)
                        B[sampled, j] = True
        
        # Calculate random scores for each round
        # R code: rand.scores <- apply(B, 2, function(x) colMeans(r$zscores[x,]))
        rand_scores = np.zeros((n_samples, self.num_rounds))
        
        zscores_array = self.zscores.values
        for j in range(self.num_rounds):
            selected_genes = B[: , j]
            if selected_genes.sum() > 0:
                rand_scores[:, j] = zscores_array[selected_genes, : ].mean(axis=0)
        
        # Return mean across rounds
        # R code: rand.scores <- rowMeans(rand.scores)
        return rand_scores. mean(axis=1)
    
    def calculate_signatures(self, return_details: bool = False):
        """
        Calculate signature scores
        
        Matching R code:  get.OE.bulk()
        
        Returns
        -------
        pd. DataFrame
            Normalized signature scores (samples x signatures)
        """
        print("\n" + "="*60)
        print("CALCULATING SIGNATURE SCORES")
        print("="*60)
        
        # Step 1: Calculate mean expression and z-scores
        print("\nStep 1: Calculating z-scores...")
        # R code: r$genes.mean <- rowMeans(r$tpm)
        self.genes_mean = self.tpm. mean(axis=1)
        
        # R code: r$zscores <- sweep(r$tpm, 1, r$genes.mean, FUN = '-')
        self.zscores = self.tpm.subtract(self.genes_mean, axis=0)
        
        print(f"  Mean expression range: [{self.genes_mean.min():.3f}, {self.genes_mean.max():.3f}]")
        
        # Step 2: Calculate gene distribution and bin
        print("\nStep 2: Binning genes by expression...")
        # R code (for bulk): r$genes.dist <- r$genes.mean
        genes_dist = self.genes_mean. values
        
        # R code:  r$genes.dist.q <- discretize(r$genes.dist, n.cat = 50)
        genes_dist_q = self._discretize(genes_dist, self.n_bins)
        
        print(f"  Created {len(np.unique(genes_dist_q))} bins")
        
        # Step 3: Calculate scores for each signature
        print("\nStep 3: Calculating signature scores...")
        
        sig_scores = pd.DataFrame(
            np.zeros((len(self.samples), len(self.signatures))),
            index=self.samples,
            columns=list(self.signatures.keys())
        )
        
        sig_scores_raw = sig_scores.copy()
        rand_scores_df = sig_scores.copy()
        
        for i, (sig_name, sig_genes) in enumerate(self.signatures.items()):
            print(f"\n  [{i+1}/{len(self. signatures)}] Processing:  {sig_name}")
            
            # Find genes in data
            # R code: b. sign <- is.element(r$genes, gene.sign[[i]])
            genes_found = [g for g in sig_genes if g in self.genes]
            b_sign = np.array([g in genes_found for g in self.genes])
            
            n_found = b_sign.sum()
            print(f"    Found {n_found}/{len(sig_genes)} genes")
            
            if n_found < 2:
                warnings.warn(f"    Skipping {sig_name}:  < 2 genes found")
                continue
            
            # Calculate raw scores
            # R code: raw.scores <- colMeans(r$zscores[b.sign,])
            raw_scores = self.zscores. values[b_sign, : ].mean(axis=0)
            
            # Calculate random control scores
            # R code: rand.scores <- get.semi.random.OE(r, r$genes.dist.q, b.sign, num.rounds)
            rand_scores = self._get_semi_random_OE(genes_dist_q, b_sign)
            
            # Calculate final normalized scores
            # R code: final.scores <- raw.scores - rand.scores
            final_scores = raw_scores - rand_scores
            
            sig_scores.loc[: , sig_name] = final_scores
            sig_scores_raw.loc[:, sig_name] = raw_scores
            rand_scores_df.loc[:, sig_name] = rand_scores
            
            print(f"    Score range: [{final_scores.min():.3f}, {final_scores.max():.3f}]")
        
        print("\n" + "="*60)
        print("DONE!")
        print("="*60)
        
        if return_details:
            return {
                'normalized':  sig_scores,
                'raw': sig_scores_raw,
                'random': rand_scores_df,
                'genes_mean': self.genes_mean,
                'zscores': self. zscores
            }
        else:
            return sig_scores


def load_signatures_from_csv(filepath: str, 
                             header:  int = 0,
                             clean_names: bool = True) -> Dict[str, List[str]]:
    """
    Load signatures from CSV file
    
    Parameters
    ----------
    filepath :  str
        Path to CSV file (each column is a signature)
    header : int
        Header row (default: 0)
    clean_names : bool
        Clean column names (strip whitespace, etc.)
    
    Returns
    -------
    Dict[str, List[str]]
        Dictionary of signatures
    """
    sig_df = pd.read_csv(filepath, header=header)
    
    signatures = {}
    for col in sig_df.columns:
        # Clean column name
        col_name = col.strip() if clean_names else col
        
        # Get genes (remove NaN and empty)
        genes = sig_df[col]. dropna().astype(str).tolist()
        genes = [g. strip() for g in genes if g and g.upper() != 'NAN' and g.strip()]
        
        if genes: 
            signatures[col_name] = genes
    
    return signatures


def compare_with_paper(your_scores: pd.DataFrame, 
                       paper_scores: pd.DataFrame,
                       patients: List[str] = None,
                       signatures: List[str] = None):
    """
    Compare your results with paper results
    
    Parameters
    ----------
    your_scores : pd.DataFrame
        Your calculated scores
    paper_scores : pd. DataFrame
        Paper's scores
    patients : List[str], optional
        Specific patients to compare (default: all common)
    signatures : List[str], optional
        Specific signatures to compare (default: all common)
    """
    print("\n" + "="*60)
    print("COMPARISON WITH PAPER RESULTS")
    print("="*60)
    
    # Find common patients and signatures
    common_patients = set(your_scores.index) & set(paper_scores.index)
    common_sigs = set(your_scores. columns) & set(paper_scores.columns)
    
    if patients:
        common_patients = [p for p in patients if p in common_patients]
    if signatures:
        common_sigs = [s for s in signatures if s in common_sigs]
    
    print(f"\nCommon patients: {len(common_patients)}")
    print(f"Common signatures: {len(common_sigs)}")
    
    if not common_patients or not common_sigs:
        print("ERROR: No common patients or signatures!")
        return
    
    # Calculate correlation for each patient
    print("\n" + "-"*60)
    print("Per-patient correlation:")
    print("-"*60)
    
    for patient in sorted(list(common_patients))[:5]:  # Show first 5
        your_vals = your_scores. loc[patient, list(common_sigs)]
        paper_vals = paper_scores. loc[patient, list(common_sigs)]
        
        corr = your_vals.corr(paper_vals)
        mae = (your_vals - paper_vals).abs().mean()
        
        print(f"{patient: 15s}:  Correlation = {corr:.4f}, MAE = {mae:. 4f}")
    
    # Show detailed comparison for specific cases
    print("\n" + "-"*60)
    print("Detailed comparison (first 3 patients, first 5 signatures):")
    print("-"*60)
    
    for patient in sorted(list(common_patients))[:3]:
        print(f"\n{patient}:")
        print(f"{'Signature':<20s} {'Paper': >12s} {'Yours':>12s} {'Diff':>12s} {'Ratio':>12s}")
        print("-" * 70)
        
        for sig in sorted(list(common_sigs))[:5]:
            paper_val = paper_scores.loc[patient, sig]
            your_val = your_scores.loc[patient, sig]
            diff = your_val - paper_val
            ratio = your_val / paper_val if abs(paper_val) > 1e-6 else np.inf
            
            print(f"{sig:<20s} {paper_val:12.6f} {your_val:12.6f} {diff:12.6f} {ratio:12.2f}")