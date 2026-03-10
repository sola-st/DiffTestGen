from os.path import join
from os import listdir


model = "gpt-5-mini-2025-08-07"
with open(".target_project", "r") as f:
    target_project = f.read().strip()

def get_pr_list_from_folder(folder):
    files = listdir(folder)
    pr_list = []
    for file in files:
        pr_list.append(int(file.split("_")[1]))
    return pr_list

def get_delta_prs(list1, list2):
    delta = []
    for pr in list1:
        if not pr in list2:
            delta.append(pr)
    return delta

def write_pr_list_to_file(pr_list, prefix):
    filename = f"data/meta/{target_project}_{prefix}_{len(set(pr_list))}.txt"
    with open(filename, "w") as f:
        f.writelines("\n".join(map(str, set(pr_list))))

chaco_folder = join("data", "results", "breakpoint", "bp_chaco", target_project)
pr_list_chaco = get_pr_list_from_folder(chaco_folder)

dtg_folder = join("data", "results", "breakpoint", model, "bp_chaco_5_8_8_True_True_pr-modified")
pr_list_dtg = get_pr_list_from_folder(dtg_folder)

in_chaco_not_in_dtg = get_delta_prs(pr_list_chaco, pr_list_dtg)
in_dtg_not_in_chaco = get_delta_prs(pr_list_dtg, pr_list_chaco)

write_pr_list_to_file(in_chaco_not_in_dtg, "in_chaco_not_in_dtg")
write_pr_list_to_file(in_dtg_not_in_chaco, "in_dtg_not_in_chaco")