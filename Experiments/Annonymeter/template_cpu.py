#!/bin/bash
#OAR -n Inferences
#OAR -l /nodes=1/core=32,walltime=48:00:00
#OAR --project pr-ai4drug
#OAR --stdout Inferences.out
#OAR --stderr Inferences.err

echo toto


cd /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace/containers

singularity exec \
  --bind /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace:/mnt/ \
  --no-home \
  my_singularity \
  bash -c "
    source /binary/miniforge3/etc/profile.d/conda.sh && \	
    conda activate synthetic_data && \
    cd /mnt/digphat/syntheticDataBenchmark/Chuong_pipeline/Experiments/Annonymeter && \
    python Inferences.py 
"