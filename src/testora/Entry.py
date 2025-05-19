# Only needed if running different versions of prompts non-stop.
import shutil
import subprocess
from testora import Config
from os.path import join, isfile
from os import makedirs
import os


config_versions = [
    [1, 0, 1],
    [1, 1, 1],
    [2, 2, 2],
    [3, 3, 3],
    [4, 4, 4],
    [5, 5, 5],
    [6, 6, 6],
    [7, 7, 7],
    [8, 8, 8]
    ]

breakpoints_data_folder = join("data", "results", "latest", "breakpoint")

for config in config_versions:
    # add tasks to database
    subprocess.run(["python", "-m", "testora.evaluation.PreparePRChunks"])
    # get the desired configuration
    Config.initial_test_generation_prompt_version, Config.feedback_test_generation_prompt_version, Config.context_version = config
    # run RegressionFinder
    subprocess.run(["python", "-m", "testora.RegressionFinder", "--db"])
    # store the breakpoint data seperately
    bp_data_cur_version = join(breakpoints_data_folder, f"bp_{'_'.join(map(str, config))}")
    makedirs(bp_data_cur_version, exist_ok=True)
    for f in os.listdir('.'):
        if isfile(f) and f.endswith("_breakpoint_data.json"):
            shutil.move(f, bp_data_cur_version)