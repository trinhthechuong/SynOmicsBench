# Cell Type Deconvolution

This dimension evaluates whether cell type composition inferred from bulk RNA-seq data is faithfully preserved in synthetic datasets. CIBERSORTx with the LM22 reference signature estimates the proportions of 22 human immune cell types.

## Aitchison Distance

To quantify preservation of inferred immune cell compositions, we measured the similarity using the **Aitchison distance**, which is appropriate for compositional data

### Compositional Center
Let $x_{ij}$ denote the estimated fraction of cell type $j$ in sample $i$. The geometric mean of each cell type $j$ across $n$ samples:

$$g_j = \exp\!\left(\frac{1}{n}\sum_{i=1}^{n}\log x_{ij}\right)$$

### CLR Transformation

The Centered Log-Ratio transformation of the compositional center vector:

$$\text{CLR}(g_j) = \log\!\left(\frac{g_j}{\left(\prod_{l=1}^{k} g_l\right)^{1/k}}\right)$$

### Distance and Score

$$d_A = \sqrt{\sum_{j=1}^{k}\bigl(\text{CLR}(g_j^{\text{original}}) - \text{CLR}(g_j^{\text{synthetic}})\bigr)^2}$$

Converted to a score for easier comparison (higher = better):

$$\text{Score} = \exp(-d_A)$$

where the analysis is constrained to the top $k = 10$ most abundant cell types.

## Code Example

The `cell_deconvolution` module in SynOmics provides the Aitchison distance calculation:

```python
from SynOmics.metrics.narrow_utility.cell_deconvolution import (
    aitchison_distance,
    aitchison_score,
)

cell_types = ['T cells CD8', 'T cells CD4 mem. resting', 'Plasma cells']
# Compute Aitchison distance and score
d = aitchison_distance(ori_deconvolution, syn_deconvolution, cell_types)
score = aitchison_score(d)

print(f"Aitchison Distance: {d:.4f}")
print(f"Aitchison Score: {score:.4f}")
```

The `ori_deconvolution` and `syn_deconvolution` objects should be DataFrames where rows are samples and columns represent cell type fractions:

| Patient | B cells naive | B cells memory | Plasma cells | T cells CD8 | T cells CD4 naive | T cells CD4 mem. resting |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Patient1** | 0.0637 | 0.1255 | 0.0985 | 0.0500 | 0.0000 | 0.1437 |
| **Patient10** | 0.1348 | 0.0000 | 0.1443 | 0.1457 | 0.0000 | 0.4914 |
| **Patient100** | 0.0949 | 0.1930 | 0.6228 | 0.0866 | 0.0000 | 0.0000 |
| **Patient102** | 0.0502 | 0.1129 | 0.2339 | 0.1211 | 0.0000 | 0.4372 |
| **Patient105** | 0.0080 | 0.0488 | 0.0218 | 0.1817 | 0.0000 | 0.2385 |

