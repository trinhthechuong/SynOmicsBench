import pandas as pd
import numpy as np
from avatars.manager import Manager
from avatars.models import JobKind
import os
import time
import json
import uuid

url = os.environ.get("AVATAR_BASE_API_URL", "https://www.octopize.app/api")
username = os.environ.get("the-chuong.trinh@cea.fr")
password = os.environ.get("ttcAVATARS#123")

manager = Manager(base_url=url)
manager.authenticate("the-chuong.trinh@cea.fr", "ttcAVATARS#123", should_verify_compatibility=False)


with open("avatars/cluster_final.json", "r") as f:
    cluster_features = json.load(f)

cluster_flat = []
for cluster in cluster_features:
    cluster_flat += cluster
print("Number of features:", len(cluster_flat))
seed = 0
k = 10
errors = []
for i in range(0, len(cluster_features)):
    try:
        data = pd.read_csv(f"avatars/original_blocks/original_block_{i}.csv", index_col =False)
        data_clean = data.drop(columns=["Patient"])
        # Create runner and add table
        job_name = f"Block_{i}_k{k}_{seed}" + str(uuid.uuid4())
        runner = manager.create_runner(job_name, seed = seed)
        table_name = f"block_{i}_k{k}_{seed}" + str(uuid.uuid4())
        
        runner.add_table(table_name, data_clean)
        runner.set_parameters(table_name, k=k)
        
        # # Only run the synthesis job
        avatarization_job = runner.run(jobs_to_run=[JobKind.standard])
        
        # # Now retrieve the unshuffled synthetic data
        synthetic_df = runner.sensitive_unshuffled(table_name)
        synthetic_df.to_csv(f"avatars/synthetic_blocks_k{k}_{seed}/synthetic_block_{i}.csv", index=False)
        if data_clean.shape[1] >= 3000:
            time.sleep(6000)
        else:
            time.sleep(30)
    except Exception as e:
        print(f"Error processing cluster {i}: {e}")
        errors.append((i, str(e)))
        continue
