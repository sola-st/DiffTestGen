import subprocess


with open(".target_project", "r") as f:
    target_project = f.read().strip()

with open(f"data/meta/pandas_normal_100.txt", "r") as f:
    prs = f.readlines()
    pr_list = [int(pr) for pr in prs]
# pr_list = [20349]

for pr_num in pr_list:
    subprocess.run(["python", "-m", "testora.SphinxOnlyFinder", 
            "--project", target_project, "--pr", f"{pr_num}"])