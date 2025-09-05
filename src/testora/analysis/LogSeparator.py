import ast
import json
from os.path import join, isfile, exists
from os import listdir, makedirs
import shutil


iterations = [0, 1, 2, 3, 4]
base_folder = join("data", "results")

# option 1: for all projects
target_projects = ["scipy", "marshmallow", "pandas", "keras"]

# option 2: for a single project
# with open(".target_project", "r") as f:
#     target_project = f.read().strip()
# target_projects = [target_project]

for target_project in target_projects:
    config_versions = [
        [1, 0, 1, False],
        [5, 5, 5, False],
        [5, 8, 8, False],
        [5, 8, 8, True]
    ]

    version_ids_with_iter = ['_'.join(map(str, config)) + f"_{iteration}" for config in config_versions for iteration in iterations]
    # version_ids_with_iter = ['_'.join(map(str, config)) for config in config_versions]
    

    log_results = join(base_folder, target_project)
    archive_results= join(log_results, "archive")

    result_folder = [log_results, archive_results]

    for log_folder in result_folder:
        log_files = listdir(log_folder)
        for file in log_files:
            log_file_path = join(log_folder, file)
            if isfile(log_file_path):
                with open(log_file_path, "r") as f:
                    info = json.load(f) 
                
                config_message_tmp = info[0]["message"].replace("Configuration: ", "", 1)
                config_message = ast.literal_eval(config_message_tmp)
                model_version = config_message["model_version"] # to support each version with a separate folder
                initial_prompt = config_message["initial_test_generation_prompt_version"]
                feedback_prompt = config_message["feedback_test_generation_prompt_version"]
                context = config_message["context_version"]
                try:
                    whether_feedback = config_message["use_error_feedabck"]
                    version_id = f"{initial_prompt}_{feedback_prompt}_{context}_{whether_feedback}"
                    iteration = config_message["iteration"]
                    if f"{version_id}_{iteration}" in version_ids_with_iter:
                        separated_results_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{version_id}", target_project)
                        makedirs(separated_results_folder, exist_ok=True)
                        if not exists(join(separated_results_folder, file)):
                            shutil.copy2(log_file_path, separated_results_folder)
                    # try:
                    #     iteration = config_message["iteration"]
                    # except:
                    #     if "07-28" in log_file_path:
                    #         if f"{version_id}" in version_ids_with_iter:
                    #             separated_results_folder = join(base_folder, f"iter_1", f"log_{version_id}", target_project)
                    #             makedirs(separated_results_folder, exist_ok=True)
                    #             if not exists(join(separated_results_folder, file)):
                    #                 shutil.copy2(log_file_path, separated_results_folder)
                except:
                    pass # old executions with no the newly added configs
