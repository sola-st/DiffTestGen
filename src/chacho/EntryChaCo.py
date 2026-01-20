import shutil
import subprocess
from os.path import join, isfile
from os import makedirs, listdir


with open(".target_project", "r") as f:
    target_project = f.read().strip()

pr_meta = {
    "pandas": 29,
    "scipy": 46
}
# pr_meta = {
#     "pandas": 45,
#     "scipy": 50
# }
pr_file = join("data", "meta", f"chaco_{target_project}_unique_{pr_meta[target_project]}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs][:3]
for pr_num in pr_list:
    subprocess.run(["python", "-m", "chacho.RunChaCoTests", "--project", target_project, "--pr_nb", f"{pr_num}"])
    
# store the breakpoint data seperately
bp_data_cur_version = join("data", "results", "breakpoint", "bp_chaco", target_project)
makedirs(bp_data_cur_version, exist_ok=True)
bp_num = 0
for f in listdir('.'):
    if isfile(f) and f.endswith("_breakpoint_data.json"):
        bp_num +=1
        shutil.move(f, bp_data_cur_version)
print(f"\n-- Gets {bp_num} PRs with different outputs.")