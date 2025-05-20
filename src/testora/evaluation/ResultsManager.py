import os
from datetime import datetime
from os.path import join, exists
from os import makedirs, listdir

results_base_dir = "data/results/"
classification_results_base_dir = "data/classification_results/"


def result_files():
    for project_dir in listdir(results_base_dir):
        for pr_result_file in listdir(join(results_base_dir, project_dir)):
            if pr_result_file.endswith(".json"):
                yield join(results_base_dir, project_dir, pr_result_file)


def result_files_for_project(project_name, minimum_timestamp=None, is_classification=False, file_name=None, base_dir_arg=None):
    if base_dir_arg:
        base_dir = base_dir_arg
    else:
        base_dir = classification_results_base_dir if is_classification else results_base_dir
    
    for pr_result_file in listdir(join(base_dir, project_name)):
        if pr_result_file.endswith(".json"):
            if minimum_timestamp:
                pr_timestamp = pr_result_file.replace(".json", "").split("_")[1]
                if datetime.strptime(pr_timestamp, "%Y-%m-%d %H:%M:%S") < datetime.strptime(minimum_timestamp, "%Y-%m-%d %H:%M:%S"):
                    continue

            if file_name and pr_result_file != file_name:
                continue

            yield join(base_dir, project_name, pr_result_file)


def current_results(include_archive=True, is_classification=False, projects=None):
    base_dir = classification_results_base_dir if is_classification else results_base_dir

    project_to_prs_and_timestamps = {}
    for project in projects:
        result_dirs = [] # expected to have 2 elements: normal project result folder and a inner 'archive' folder
        
        result_dir = join(base_dir, project)
        makedirs(result_dir, exist_ok=True)
        result_dirs.append(result_dir)
    
        project_to_prs_and_timestamps[project] = []
        if include_archive:
            archive_dir = join(result_dir, "archive")
            if not exists(archive_dir):
                makedirs(archive_dir)
                print(f"Created directory {archive_dir}")
            result_dirs.append(archive_dir)

        for result_dir in result_dirs:
            for pr_result_file in listdir(result_dir):
                if pr_result_file.endswith(".json"):
                    pr_nb, timestamp = pr_result_file.replace(".json", "").split("_")
                    project_to_prs_and_timestamps[project].append([pr_nb, timestamp])
    return project_to_prs_and_timestamps


def add_result(project_name, pr_nb, timestamp, result, is_classification, projects=None):
    base_dir = classification_results_base_dir if is_classification else results_base_dir

    if not exists(base_dir):
        makedirs(base_dir)
        print(f"Created directory {base_dir}")

    all_old_results = current_results(is_classification=is_classification, projects=projects)
    non_archive_old_results = current_results(
        False, is_classification=is_classification, projects=projects)

    # check if result already exists
    for old_pr_nb, old_timestamp in all_old_results[project_name]:
        if old_pr_nb == pr_nb and old_timestamp == timestamp:
            return

    # Write new result to file
    if not exists(join(base_dir, project_name)):
        makedirs(join(base_dir, project_name))

    target_file = join(base_dir, project_name, f"{pr_nb}_{timestamp}.json")
    with open(target_file, "w") as f:
        f.write(result)

    # Check if it replaces an old result (if yes, move old result to archive)
    for old_pr_nb, old_timestamp in non_archive_old_results[project_name]:
        if old_pr_nb == pr_nb:
            old_target_file = join(base_dir, project_name, f"{old_pr_nb}_{old_timestamp}.json")
            archive_dir = join(base_dir, project_name, "archive")
            if not exists(archive_dir):
                makedirs(archive_dir)
                print(f"Created directory {archive_dir}")
            renamed_target_file = join(archive_dir, f"{old_pr_nb}_{old_timestamp}.json")
            os.rename(old_target_file, renamed_target_file)
            print(f"Moved old result to {renamed_target_file}")
            break

    print(f"New result in {target_file}")
