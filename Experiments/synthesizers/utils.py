from scipy.cluster.hierarchy import linkage
from collections import deque
import numpy as np
import pandas as pd
from tqdm import tqdm
import json
from numba import njit, prange

def build_cluster_tree(Z, n_samples):
    """
    Xây cây cluster từ linkage matrix.
    Trả về một dict: cluster_id -> (left_child, right_child, count)
    """
    cluster_tree = {}
    for i, (left, right, dist, count) in enumerate(Z):
        cluster_id = i + n_samples
        cluster_tree[cluster_id] = {
            'left': int(left),
            'right': int(right),
            'count': int(count)
        }
    return cluster_tree

def split_clusters_by_size(Z, threshold):
    """
    Thực hiện phân cụm top-down cho đến khi tất cả cluster đều <= threshold
    """
    n_samples = Z.shape[0] + 1
    cluster_tree = build_cluster_tree(Z, n_samples)

    final_clusters = []
    queue = deque()
    queue.append(n_samples + Z.shape[0] - 1)  # Root cluster ID

    while queue:
        cluster_id = queue.popleft()
        if cluster_id < n_samples:
            # Đây là leaf node (sample)
            final_clusters.append([cluster_id])
            continue

        node = cluster_tree[cluster_id]
        if node['count'] <= threshold:
            # Cluster đủ nhỏ → giữ lại
            leaf_members = get_leaf_members(cluster_id, cluster_tree, n_samples)
            final_clusters.append(leaf_members)
        else:
            # Chưa đủ nhỏ → tách tiếp
            queue.append(node['left'])
            queue.append(node['right'])

    return final_clusters

def get_leaf_members(cluster_id, cluster_tree, n_samples):
    """
    Trả về danh sách các sample thuộc về cluster này (leaf nodes)
    """
    result = []
    stack = [cluster_id]
    while stack:
        cid = stack.pop()
        if cid < n_samples:
            result.append(cid)
        else:
            node = cluster_tree[cid]
            stack.append(node['left'])
            stack.append(node['right'])
    return result


def check_duplicates(data: pd.DataFrame):
        try:
            print("Grouping genes with identical expression values...")
            # Transpose to check duplicates across genes
            genes_duplicated = data.T[data.T.duplicated(keep=False)].T
            if genes_duplicated.empty:
                print("No duplicate genes found")
                return {}, {}

            # Map each gene to its expression values
            gene_values = {col: vals.tolist() for col, vals in genes_duplicated.items()}
            duplicated_genes_dict = {col: [] for col in genes_duplicated.columns}
            mapped_genes_dict = duplicated_genes_dict.copy()

            # Group duplicates by expression values
            seen_values = set()
            for column in tqdm(genes_duplicated.columns, desc="Processing duplicates"):
                values = tuple(gene_values[column])  # Use tuple for hashability
                if values in seen_values:
                    continue
                seen_values.add(values)
                duplicates = [col for col, vals in gene_values.items() if vals == gene_values[column]]
                for dup in duplicates:
                    duplicated_genes_dict[dup] = duplicates

            # Save results
            with open("duplicated_genes_dict.json", "w") as f:
                json.dump(duplicated_genes_dict, f) 
            return duplicated_genes_dict
        except Exception as e:
            raise ValueError(f"Duplicate check failed: {e}")