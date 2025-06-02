import ast
import json
from os.path import join, isfile, exists
from os import listdir, makedirs
import shutil

base_folder = join("data", "results")

target_projects = ["scipy", "marshmallow", "pandas", "keras"]
for target_project in target_projects:

    # with open(".target_project", "r") as f:
    #     target_project = f.read().strip()

    config_versions = [
        [1, 0, 1],
        [1, 1, 1],
        [2, 2, 2],
        [3, 3, 3],
        [4, 4, 4],
        [5, 5, 5],
        [6, 6, 6],
        [7, 7, 7],
        [1, 8, 8]
        ]

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        separated_results_folder = join(base_folder, f"log_{version_id}", target_project)
        makedirs(separated_results_folder, exist_ok=True)

    log_results = join(base_folder, target_project)
    archive_results= join(log_results, "archive")

    result_folder = [log_results]

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
                version_id = f"{initial_prompt}_{feedback_prompt}_{context}"
                # if version_id == "7_7_7" and not exists(join(base_folder, f"log_{version_id}", target_project, file)):
                shutil.move(log_file_path, join(base_folder, f"log_{version_id}", target_project))
