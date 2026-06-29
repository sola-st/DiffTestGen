import json
from os import listdir, rename
from os.path import join


def rename_log_file(file, file_folder):
    new_file_name = None
    log_file = join(file_folder, file)
    try:
        with open(log_file, "r") as f:
            info = json.load(f)
    except:
        print(f"Error reading {log_file}")
        return new_file_name

    call_graph_block = info[-1]
    pr = call_graph_block["pr_nb"]
    # # !!! rename only once
    if not str(pr) in file:
        if call_graph_block["message"].startswith("Done with"):
            new_file_name = f"{pr}_{file}"
        else:
            unfinshed_file = file.replace(".json", "_unfinished.json")
            new_file_name = f"{pr}_{unfinshed_file}"
        rename(log_file, join(file_folder, new_file_name.replace("logs_", "")))
    
    return new_file_name
    

if __name__ == "__main__":
    # to rename logs in folder
    folder = ""
    # projects = ["keras", "marshmallow", "pandas", "scipy"]
    # for pro in projects:
        # project_folder = join(folder, pro)
        # files = listdir(project_folder)
    files = listdir(folder)
    for file in files:
        if file.startswith("logs_"):
            rename_log_file(file, folder)
