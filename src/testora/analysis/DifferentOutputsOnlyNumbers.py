from os.path import join
import json
import os


results_folder = join("data", "results")

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"
# option 1: for all projects
# target_projects = ["marshmallow", "scipy", "pandas", "keras"]

# option 2: for a single project
with open(".target_project", "r") as f:
    target_project = f.read().strip()
target_projects = [target_project]

config_versions = [
    [5, 8, 8, 'pr-modified', True, True, True],
    [5, 0, 8, 'pr-modified', True, True, True],
    [5, 8, 8, None, True, True, True],
    # [5, 8, 8, 'pr-modified', False, True, True],
    [5, 8, 8, 'pr-modified', True, False, True],
    [5, 8, 8, 'pr-modified', True, True, False],
    ]
config_versions_names = [
    "DiffTestGen",
    "no_feedback_loop",
    "no_changed_tests",
    # "no_cg",
    "no_static",
    "no_runtime",
]

for target_project in target_projects:
    print(f"---- Project: {target_project} ----")
    for config, name in zip(config_versions, config_versions_names):
        project_level_differ_tests = 0
        config.append(name)
        version_id = '_'.join(map(str, config))
        bp_folder = join(results_folder, "breakpoint", model_version, f"iter_{iteration}", f"bp_{version_id}", target_project)
        
        files = os.listdir(bp_folder)
        for fname in files:
            log_file_path = join(bp_folder, fname)
            with open(log_file_path, "r") as f:
                info = json.load(f) 
            old_executions_str = info['old_executions_differ_relevant']
            project_level_differ_tests += old_executions_str.count('TestExecution(')

        print(f"Version: {name}, Differ PRs: {len(files)}, Differ Tests: {project_level_differ_tests}")