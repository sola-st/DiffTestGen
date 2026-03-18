from os.path import join

from testora.evaluation import EvalTaskManager


pr_split_num = 3 # could be None, 1, 2, or 3

with open(".target_project", "r") as f:
    target_project = f.read().strip()
    
# marshmallow 53, keras 133, pandas 128, scipy 129
num = 65
if target_project == "keras":
    num = 160
elif target_project == "pandas":
    num = 143
elif target_project == "scipy":
    num = 129

pr_file = join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{num}.txt")
if pr_split_num:
    pr_file = pr_file.replace(".txt", f"_{pr_split_num}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]

EvalTaskManager.initialize()
EvalTaskManager.remove_unfinished(target_project, pr_list)