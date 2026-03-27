import copy
import subprocess
from os.path import join, exists
import os

max_iteration = 1
mode = "comparison" # could be 'comparison' and 'ablation'
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
pr_split_num = 1 # could be None, 1, 2, or 3

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
# marshmallow 53, keras 133, pandas 128, scipy 129
num = 65
if target_project == "keras":
    num = 160
elif target_project == "pandas":
    num = 143
elif target_project == "scipy":
    num = 157

pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset{num}.txt")
if pr_split_num:
    pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

config_versions = []
if mode == "comparison":
    # initial_prompt, feedback_prompt, context_version, \
    # pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback
    config_versions = {
        "testora": [1, 0, 1, None, False, False, False],
        "difftestgen": [5, 8, 8, "pr-modified", True, True, True],
        # "no_coverage_feedback": [5, 0, 8, 'pr-modified', True, True, True], 
        # "no_cg": [5, 8, 8, 'pr-modified', False, True, True],
        # "no-runtime": [5, 8, 8, 'pr-modified', True, False, True]
    } 
elif mode == "ablation":
    # base setting about ablation, to trun off feedback and call graph
    # about initial prompt
    initial_prompt = 5 # itself does not change, but inner changes, e.g., 1 and 2
    pr_modified_tests = "pr-modified" # 1
    use_call_graph = True # in initial prompt # 2

    # outer feedback loop
    feedback_prompt = 8 # coverage_feedback -> turn off, changed it to 0 # 3
    context_version = 8 # always the same, no need to turn off

    # inner loop for every round
    fix_static_error = True # could be only once and multiple attempts # 4
    runtime_error_feedback = True # inner loop for every round # 5

    our_approach = [initial_prompt, feedback_prompt, context_version, \
                    pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback]
    turn_off_indices_values = {
        "1": 0,
        "4": False,
        "5": False
    } # trun off feedback and call graph
    config_names = ["no_coverage_feedback", "no_cg", "no_runtime"]
    
    # {} to only focus on the ablation settings
    # {"difftestgen": [5, 8, 8, "pr-modified", True, True, True]} # to include our approach
    config_versions = {} 
    for (op_idx_str, turn_off_val), name_key in zip(turn_off_indices_values.items(), config_names):
        turn_off_op = copy.deepcopy(our_approach)
        turn_off_op[int(op_idx_str)] = turn_off_val 
        config_versions.update({name_key: turn_off_op})

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
