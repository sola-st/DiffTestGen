import ast
import json
from os.path import join, isfile, exists
from os import listdir, makedirs
import shutil

base_folder = join("data", "results")
iteration = 0

# option 1: for all projects
# target_projects = ["scipy", "marshmallow", "pandas", "keras"]

# option 2: for a single project
with open(".target_project", "r") as f:
    target_project = f.read().strip()
target_projects = [target_project]

for target_project in target_projects:
    config_versions = [
        # [1, 0, 1],
        # [5, 5, 5],
        [5, 8, 8, True]
        ]

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        separated_results_folder = join(base_folder, f"iter_{iteration}", f"log_{version_id}", target_project)
        makedirs(separated_results_folder, exist_ok=True)

    log_results = join(base_folder, target_project)
    # archive_results= join(log_results, "archive")

    result_folder = [log_results] #, archive_results]

    for log_folder in result_folder:
        log_files = listdir(log_folder)
        for file in log_files:
            log_file_path = join(log_folder, file)
            if isfile(log_file_path):
                with open(log_file_path, "r") as f:
                    info = json.load(f) 
                
                config_message_tmp = info[0]["message"].replace("Configuration: ", "", 1)
                config_message = ast.literal_eval(config_message_tmp)
                initial_prompt = config_message["initial_test_generation_prompt_version"]
                feedback_prompt = config_message["feedback_test_generation_prompt_version"]
                context = config_message["context_version"]
                whether_feedback = config_message["use_error_feedabck"]
                version_id = f"{initial_prompt}_{feedback_prompt}_{context}_{whether_feedback}"
                # if not exists(join(base_folder, f"log_{version_id}", target_project, file)):
                shutil.move(log_file_path, join(base_folder, f"iter_{iteration}", f"log_{version_id}", target_project))
