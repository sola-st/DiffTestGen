import json
from os.path import exists, join, isfile
import os

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
projects = ["marshmallow", "pandas", "scipy", "keras"]
    
# marshmallow 53, keras 133, pandas 128, scipy 129
config_versions = {
    "testora": [1, 0, 1, None, False, False, False],
    "difftestgen": [5, 8, 8, "pr-modified", True, True, True],
    "no_coverage_feedback": [5, 0, 8, 'pr-modified', True, True, True], 
    "no_cg": [5, 8, 8, 'pr-modified', False, True, True],
    "no_changed_tests" : [5, 8, 8, None, True, True, True],
    "no_static" : [5, 8, 8, 'pr-modified', True, False, True],
    "no_runtime" : [5, 8, 8, 'pr-modified', True, True, False],
}
        
results_folder = join("data", "results")
log_folder = join(results_folder, model_version, f"iter_{iteration}")

meta = {}
for project in projects:
    meta.update({project: {}})
    for config_name, config in config_versions.items():
        full_config = "_".join(map(str, config + [config_name]))
    
        log_folder_cur_version = join(log_folder, f"log_{full_config}", project) 
        if exists(log_folder_cur_version):
            print(f"{project}   {full_config}")
            num = 0
            for f in os.listdir(log_folder_cur_version):
                log_file_path = join(log_folder_cur_version, f)
                if isfile(log_file_path):
                    with open(log_file_path, "r") as f:
                        info = f.read()
                    if "Different outputs" in info:
                        num += 1
            meta[project].update({config_name: num})


result_file = join(results_folder, f"different_outputs_overall_{model_version}.json")
with open(result_file, "w") as f:
    json.dump(meta, f, indent=4)