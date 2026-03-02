#!/bin/bash
#OAR -n CTGAN_job
#OAR -l /nodes=1/core=20,walltime=48:00:00
#OAR --project pr-ai4drug
#OAR --stdout ctgan_2307.out
#OAR --stderr ctgan_2307.err

echo toto


cd /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace/containers

singularity exec \
  --bind /bettik/PROJECTS/pr-ai4drug/trinhtc/workspace:/mnt/ \
  --no-home \
  my_singularity \
  bash -c "
    source /binary/miniforge3/etc/profile.d/conda.sh && \	
    conda activate synthetic_data && \ # modify the conda environment
    cd /mnt/digphat/syntheticDataBenchmark/Chuong_pipeline && \#modify the path to python file
    python CTGAN_2307.py #modify the file name
"