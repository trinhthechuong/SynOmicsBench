#!/bin/bash
#OAR -n BivariateAll_Across_Replicates
#OAR -l /nodes=1/core=32,walltime=48:00:00
#OAR --project pr-ai4drug
#OAR --stdout figure3b_bivariate/BivariateAll_Across_Replicates.out
#OAR --stderr figure3b_bivariate/BivariateAll_Across_Replicates.err

echo toto


cd /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace/containers

singularity exec \
  --bind /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace:/mnt/ \
  --no-home \
  my_sandbox \
  bash -c "
    source /binary/miniforge3/etc/profile.d/conda.sh && \	
    conda activate synthetic_data && \ 
    cd /mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/Manuscript/FigureBroadUtility && \
    python Figure3b_bivariate_all.py
"