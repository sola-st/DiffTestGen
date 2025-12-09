import subprocess

iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_versions = []
config_versions = [
    # [1, 0, 1, False, False, None],
    [5, 8, 8, True, True, "pr-modified"]
]

with open(".target_project", "r") as f:
    target_project = f.read().strip()

with open(f"data/meta/pandas_normal_100.txt", "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]
# pr_list = [60417]

for config in config_versions:
    version_id = '_'.join(map(str, config))
    config = config + [iteration, model_version]
    # run RegressionFinder
    for pr_num in pr_list:
        subprocess.run(["python", "-m", "testora.SphinxOnlyFinder", 
                "--project", target_project, "--pr", f"{pr_num}", f"--paras={config}"])