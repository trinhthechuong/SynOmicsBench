#!/bin/bash
#OAR -n CTGAN_job
#OAR -l /nodes=1/gpu=1,walltime=48:00:00
#OAR -p gpumodel='V100' 
#OAR --project pr-ai4drug
#OAR --stdout ctgan_2307.out
#OAR --stderr ctgan_2307.err

echo toto

source source /applis/environments/cuda_env.sh 12.6

cd /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace/containers

singularity exec \
  --bind /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace:/mnt/ \
  --no-home \
  --nv my_singularity \
  bash -c "
    source /binary/miniforge3/etc/profile.d/conda.sh && \	
    conda activate synthetic_data && \
    cd /mnt/digphat/syntheticDataBenchmark/Chuong_pipeline && \
    python CTGAN_2307.py
"