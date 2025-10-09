# Only needed if running different versions of prompts non-stop.
# import ast
import copy
import shutil
import subprocess
from os.path import join, isfile, exists
from os import makedirs, rename
import os

max_iteration = 5
mode = "ablation" # could be 'comparison' and 'ablation'
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
pr_split_num = 1 # could be None, 1, 2, or 3

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
# marshmallow 53, keras 133, pandas 128, scipy 129
num = 53
if target_project == "keras":
    num = 133
elif target_project == "pandas":
    num = 128
elif target_project == "scipy":
    num = 129

pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset{num}.txt")
if pr_split_num:
    pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

config_versions = []
if mode == "comparison":
    '''For a single config: 
    [initial_prompt_version, feedback_prompt_version, context_version, runtime_error_feedback, fix_static_error, use_existing_tests]
    * existing developer-written tests
        "none": do not make any extra effort about developer-written tests,
        "pr-modified": use the PR-modified tests, 
        "all": use PR-modified tests + local tests
    '''

    config_versions = [
        [1, 0, 1, False, False, None],
        [5, 8, 8, True, True, "pr-modified"]
    ]
elif mode == "ablation":
    # base setting about ablation
    # about initial prompt
    initial_prompt = 5 # itself does not change, but inner changes, e.g., 1 and 2
    pr_modified_tests = "pr-modified" # 1
    use_call_graph = True # in initial prompt # 2

    # outer feedback loop
    feedback_prompt = 8 # coverage_feedback -> turn off, changed it to 0 # 3
    # prior_generated_test = True # this is an entire set of coverage feedback, consider as a subsetting of feedback_prompt

    context_version = 8 # always the same, no need to turn off

    # inner loop for every round
    fix_static_error = True # could be only once and multiple attempts # 4
    runtime_error_feedback = True # inner loop for every round # 5

    # TODO later
    # updated_crash_detection = True # difference check
    # use_pr_title_desc = True

    our_approach = [initial_prompt, feedback_prompt, context_version, \
                    pr_modified_tests, use_call_graph, fix_static_error, runtime_error_feedback]
    turn_off_values = [initial_prompt, 0, context_version, None, False, False, False]
    
    # [] to only focus on the ablation settings
    # [our_approach] # to include our approach
    config_versions = [our_approach] 
    for op_idx, turn_off_val in enumerate(turn_off_values):
        # from setting 'initial_prompt' and 'context_version' we, 
        if op_idx in [0, 2]:
            continue
        turn_off_op = copy.deepcopy(our_approach)
        turn_off_op[op_idx] = turn_off_val 
        config_versions.append(turn_off_op)

results_folder = join("data", "results")
# if exists(results_folder):
#     rename(results_folder, f"{results_folder}_backup")

for iteration in range(max_iteration):
    breakpoints_data_folder = join(results_folder, "breakpoint", model_version, f"iter_{iteration}")

    # the default cache file setting form LLMCache
    # gpt-5-mini-2025-08-07, gpt-4o-mini-2024-07-18
    cache_dir = join("data", "llm_cache", model_version, "cache.json")
    # to resuse the cache
    iter_marked_cache_dir = cache_dir.replace(".json", f"_{iteration}.json")
    if exists(iter_marked_cache_dir):
        os.rename(iter_marked_cache_dir, cache_dir)

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        # add tasks about current target project to database
        subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks", f"--prs={pr_list}"])

        # run RegressionFinder
        config_with_iter = config + [iteration, model_version]
        subprocess.run(["python", "-m", "testora.RegressionFinder", "--db", f"--paras={config_with_iter}", f"--prs={pr_list}"])
        
        # store the breakpoint data seperately
        bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
        makedirs(bp_data_cur_version, exist_ok=True)
        for f in os.listdir('.'):
            if isfile(f) and f.endswith("_breakpoint_data.json"):
                shutil.move(f, bp_data_cur_version)

        # rename the llm cache, to check the Non-determinism of models
        # Finally, we get a cache file for each iteration, and the cache file can be reuse if needed
        os.rename(cache_dir, iter_marked_cache_dir.replace(".json", f"_{version_id}.json"))
    # os.rename(cache_dir, iter_marked_cache_dir)