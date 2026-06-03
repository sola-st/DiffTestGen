import subprocess
from os.path import join, exists
import os

max_iteration = 1
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

with open(".target_project", "r") as f:
    target_project = f.read().strip()

subset_mode = False
pr_files = None
if subset_mode == True:
    pr_file = join("data", "meta", f"subset_{target_project}.txt")
else:
    pr_split_num = 1 # could be None, 1, 2, or 3
    # marshmallow 53, keras 133, pandas 127, scipy 126 ==> 439
    # marshmallow 65, keras 160, pandas 143, scipy 157 ==> 525
    num = 53
    if target_project == "keras":
        num = 133
    elif target_project == "pandas":
        num = 127
    elif target_project == "scipy":
        num = 126

    pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
    if pr_split_num:
        pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

# By turning ON the features
# initial_prompt, feedback_prompt, context_version, changed_function_body,\
# pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback
config_versions = {
    "testora": [1, 0, 1, False, None, False, False, False], # all turned off
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True], # all turned on
    "only_coverage_feedback": [5, 8, 8, False, None, False, False, False], # testora + coverage feedback (only)
    "only_cg": [5, 0, 8, False, None, True, False, False], # testora + call graph (only)
} 

results_folder = join("data", "results")
for iteration in range(max_iteration):
    # the default cache file setting form LLMCache
    cache_dir = join("data", "llm_cache", model_version, "cache.json")

    for config_name, config in config_versions.items():
        # to resuse the cache
        marked_cache_dir = cache_dir.replace(".json", f"_{iteration}_{config_name}.json")
        if exists(marked_cache_dir):
            os.rename(marked_cache_dir, cache_dir)

        # add tasks about current target project to database
        subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks", f"--prs={pr_list}"])

        # run RegressionFinder
        config_with_iter = config + [iteration, model_version]
        subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config_with_iter}", f"--prs={pr_list}"])

        # rename the llm cache, to check the Non-determinism of models
        # Finally, we get a cache file for each iteration and for each config, and the cache file can be reuse if needed
        os.rename(cache_dir, marked_cache_dir)
