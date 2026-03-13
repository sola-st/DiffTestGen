import shutil
import subprocess
from os.path import join, isfile
from os import makedirs, listdir

from testora.analysis.RenameLocalLogs import rename_log_file


with open(".target_project", "r") as f:
    target_project = f.read().strip()

pr_meta = {
    "pandas": 16,
    "scipy": 18
}
pr_file = join("data", "meta", "chaco_prs", f"chaco_{target_project}_{pr_meta[target_project]}.txt")

with open(pr_file, "r") as f:
    prs = f.readlines()
pr_list = [int(pr) for pr in prs]
for pr_num in pr_list:
    subprocess.run(["python", "-m", "chaco.RunChaCoTests", "--project", target_project, "--pr_nb", f"{pr_num}"])
    
# store the logs and breakpoint data seperately
log_folder = join("data", "results", "chaco")
makedirs(log_folder, exist_ok=True)
log_num = 0
for f in listdir('.'):
    if isfile(f) and f.startswith("logs_"):
        log_num +=1
        new_file_name = rename_log_file(f)
        if new_file_name:
            shutil.move(new_file_name, log_folder)
        else:
            shutil.move(f, log_folder) # keep the original file if read the file fails
print(f"\n-- Gets {log_num} PR logs.")

bp_data_cur_version = join("data", "results", "breakpoint", "bp_chaco", target_project) # no multi-round needed
makedirs(bp_data_cur_version, exist_ok=True)
bp_num = 0
for f in listdir('.'):
    if isfile(f) and f.endswith("_breakpoint_data.json"):
        bp_num +=1
        shutil.move(f, bp_data_cur_version)
print(f"-- Gets {bp_num} PRs with different outputs.")