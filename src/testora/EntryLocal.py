# Only needed if running different versions of prompts non-stop.
import copy
# import shutil
import subprocess
# from os.path import join, isfile, exists
# from os import makedirs, rename
# import os

iteration = 0
mode = "comparison" # could be 'comparison' and 'ablation'
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = []
if mode == "comparison":
    config_versions = [
        # [1, 0, 1, False, False, None],
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
    # all possible abalation settings
    # [5, 0, 8, 'pr-modified', True, True, True]
    # [5, 8, 8, None, True, True, True]
    # [5, 8, 8, 'pr-modified', False, True, True]
    # [5, 8, 8, 'pr-modified', True, False, True]
    # [5, 8, 8, 'pr-modified', True, True, False]
    for op_idx, turn_off_val in enumerate(turn_off_values):
        # from setting 'initial_prompt' and 'context_version' we, 
        if op_idx in [0, 2]:
            continue
        turn_off_op = copy.deepcopy(our_approach)
        turn_off_op[op_idx] = turn_off_val 
        config_versions.append(turn_off_op)
        
# results_folder = join("data", "results")
# if exists(results_folder):
#     rename(results_folder, f"{results_folder}_backup")

# breakpoints_data_folder = join(results_folder, "breakpoint", model_version)

with open(".target_project", "r") as f:
    target_project = f.read().strip()

# with open(f"data/meta/pr_nums/{target_project}_nodiff_21.txt", "r") as f:
#     prs = f.readlines()
#     pr_list = [int(pr) for pr in prs]
pr_list = [2758, 2709, 2752] # [2730] #[2277] # 2755, 2793
for config in config_versions:
    version_id = '_'.join(map(str, config))
    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.RegressionFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])
    
    # # store the breakpoint data seperately
    # bp_data_cur_version = join(breakpoints_data_folder, f"bp_{version_id}")
    # makedirs(bp_data_cur_version, exist_ok=True)
    # # store the log results
    # # no iter info, to separate local and db, but also good to have, becasuse the log file prefix are different.
    # log_folder = join(results_folder, model_version, f"log_{version_id}", target_project) 
    # makedirs(log_folder, exist_ok=True)

    # for f in os.listdir('.'):
    #     if isfile(f):
    #         if f.endswith("_breakpoint_data.json"):
    #             shutil.move(f, bp_data_cur_version)
    #         elif f.startswith("logs_"):
    #             shutil.move(f, log_folder)