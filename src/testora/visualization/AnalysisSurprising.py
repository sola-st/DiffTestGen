import json
from os import listdir, makedirs
from os.path import join, isdir


def get_the_suprise(log_folder):
    surprise = []

    log_files = listdir(log_folder)
    for log_file in log_files:
        with open(join(log_folder, log_file), "r") as f:
            info = json.load(f)
        
        for info_block in info:
            if "is_surprising" in info_block.keys():
                if info_block["is_surprising"] == True:
                    surprise.append(info_block['pr_nb'])

    return surprise

def main():
    iteration = 1

    all_surprises = {}

    results_folder = join("data", "results")
    log_folder_parent = join(results_folder, f"logs_iter{iteration}")
    table_output_folder = join(results_folder, "table_and_plots", f"meta_iter{iteration}")
    makedirs(table_output_folder, exist_ok=True)

    all_log_folder = [join(log_folder_parent, folder) for folder in listdir(log_folder_parent)\
            if isdir(join(log_folder_parent, folder)) and folder.startswith("log_")]
    all_log_folder = sorted(all_log_folder)
    for log_folder in all_log_folder:
        version_id = log_folder.rsplit("log_", 1)[1]
        surprise = get_the_suprise(log_folder)
        all_surprises.update({version_id: surprise})
        
    meta_file = join(table_output_folder, f"superise_meta.json")
    with open(meta_file, "w") as f:
        json.dump(all_surprises, f, indent=4, ensure_ascii=False)   
    print(f"Collected coverage information is written to {meta_file}")


if __name__=="__main__":
    main()
