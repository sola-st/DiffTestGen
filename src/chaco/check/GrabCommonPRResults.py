import shutil
from os.path import join
from os import makedirs, listdir


model = "gpt-5-mini-2025-08-07"

pr_meta = {
    # "pandas": 16,
    "scipy": 4
}
for target_project, num in pr_meta.items():
    pr_file = join("data", "meta", f"chaco_{target_project}_common_{num}.txt")
    with open(pr_file, "r") as f:
        prs = f.readlines()
    pr_list = [pr.strip() for pr in prs]

    # source side
    # the prs also in testora dataset
    bp_files = []
    try:
        bp_folder = join("data", "results", "breakpoint", model, "iter_0", "bp_5_8_8_pr-modified_True_True_True_DiffTestGen", target_project)
        bp_files = listdir(bp_folder)
    except:
        pass
    dtg_folder = join("data", "results", model, "iter_0", "log_5_8_8_pr-modified_True_True_True_DiffTestGen", target_project)
    # dtg_folder = "data/results/pandas/archive"
    log_files = listdir(dtg_folder)

    # target side
    chaco_folder = join("data", "results", "breakpoint", "bp_chaco", target_project)
    makedirs(chaco_folder, exist_ok=True)
    # dtg_folder = join("data", "results", model, "iter_0", "log_chaco_5_8_8_True_True_pr-modified", target_project)
    chaco_dtg_folder = join("data", "results","chaco")
    makedirs(chaco_dtg_folder, exist_ok=True)

    cp_bp_num = 0
    cp_log_num = 0
    for pr_num in pr_list:
        try:
            bp_file = [f for f in bp_files if pr_num in f][0]
            shutil.copyfile(join(bp_folder, bp_file), join(chaco_folder, bp_file))
            cp_bp_num += 1
        except:
            pass # if no breakpoint file, skip

        try:
            log_file = [f for f in log_files if pr_num in f][0]
            shutil.copyfile(join(dtg_folder, log_file), join(chaco_dtg_folder, log_file))
            cp_log_num += 1
        except:
            print(f"Log file for PR {pr_num} not found in log folder (not done yet).")

    print(f"{target_project}: Copied {cp_bp_num} breakpoint files and {cp_log_num} log files.")