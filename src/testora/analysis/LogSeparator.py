import ast
import json
from os.path import join, isfile, exists
from os import listdir, makedirs
import shutil


# iterations = [0]
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
subset_mode = False # to grab only a specific list of PRs.
target_projects = ["scipy", "pandas", "marshmallow", "keras"]

config_versions = {
    "testora": [1, 0, 1, False, None, False, False, False],
    "difftestgen": [5, 8, 8, True, "pr-modified", True, True, True],
    "only_coverage_feedback": [5, 8, 8, False, None, False, False, False],
    "only_cg": [5, 0, 8, False, None, True, False, False],
}

base_folder = join("data", "results")
for target_project in target_projects:
    pr_list = None
    if subset_mode:
        pr_file = join("data", "meta", f"subset_{target_project}.txt")
        with open(pr_file, "r") as f:
            prs = f.readlines()
        pr_list = [int(pr) for pr in prs]

    # version_ids = ['_'.join(map(str, config)) + f"_{name}" for config in config_versions for name in config_versions_names]
    version_ids = ['_'.join(map(str, config)) for config in config_versions.values()]
    config_names = list(config_versions.keys())

    log_results = join(base_folder, target_project)
    archive_results= join(log_results, "archive")
    result_folder = [log_results, archive_results]

    for log_folder in result_folder:
        log_files = listdir(log_folder)
        for file in log_files:
            log_file_path = join(log_folder, file)
            if isfile(log_file_path):
                # to get only the specified pr logs.
                if pr_list:
                    pr_num = int(file.split("_", 1)[0])
                    if pr_num not in pr_list:
                        continue

                # # just for convenience, time-based filter
                # if "03-" in file:
                #     date = int(file.split(" ")[0].split("03-")[1])
                #     if date < 20: 
                #         continue
                # else:
                #     continue

                with open(log_file_path, "r") as f:
                    info = json.load(f) 
                
                config_message_tmp = info[0]["message"].replace("Configuration: ", "", 1)
                config_message = ast.literal_eval(config_message_tmp)
                try :   
                    option_list = [config_message[key] for key in ["initial_test_generation_prompt_version", \
                            "feedback_test_generation_prompt_version", "context_version", "changed_function_body", \
                            "use_existing_tests", "call_graph", "fix_static_error", "use_error_feedback"]]
                except:
                    pass # the old logs
                version_id = '_'.join(map(str, option_list))
                iteration = config_message["iteration"]
                if version_id in version_ids:
                    idx = version_ids.index(version_id)
                    config_name = config_names[idx]
                    separated_results_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
                    if pr_list:
                        separated_results_folder = join(base_folder, model_version, f"iter_{iteration}_subset", f"log_{config_name}", target_project)
                    makedirs(separated_results_folder, exist_ok=True)
                    if not exists(join(separated_results_folder, file)):
                        shutil.copy2(log_file_path, separated_results_folder)
