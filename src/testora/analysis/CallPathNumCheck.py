import json
from os.path import join
from os import listdir, makedirs
from collections import Counter


iteration = 0
# model_version = "gpt-4o-mini-2024-07-18"
model_version = "gpt-5-mini-2025-08-07"

config_name = "difftestgen" # "difftestgen", chaco_difftestgen

target_projects = []
if config_name == "chaco_difftestgen":
    target_projects = ["pandas", "scipy"]
else:
    target_projects = ["keras", "marshmallow", "pandas", "scipy"]


base_folder = join("data", "results")
output_folder = join(base_folder, "table_and_plots", "call_path_num")
makedirs(output_folder, exist_ok=True)

all_path_info = []
all_path_nums = []
for target_project in target_projects:
    log_folder = join(base_folder, model_version, f"iter_{iteration}", f"log_{config_name}", target_project)
    log_files = listdir(log_folder)
    for file in log_files:
        pr_num = int(file.split("_", 1)[0])
        cur_pr_str = { # no call path detected
            "project": target_project,
            "pr_nb": pr_num,
            "nb_changed_funcs": 0,
            "changed_funcs": [],
            "nb_changed_pri_funcs": 0,
            "changed_pri_funcs": [],
            "nb_cross_enties": 0,
            "cross_enties": "",
            "nb_all_path": None,
            "all_path_details": None
        }
        all_path_len_info = ""
        all_path_len_info_json = ""
        all_path_num = 0
        query_checked = False
        
        log_file_path = join(log_folder, file)
        with open(log_file_path, "r") as f:
            info = json.load(f) 
            
        for block in info:
            if "message" in block.keys():
                if block["message"].startswith("Call graph length information"):
                    all_path_len_info = block["content"]
                    all_path_len_info_json = json.loads(all_path_len_info)
                    all_path_num = len(all_path_len_info_json["all"])
                    all_path_nums.append(all_path_num)
                    # print(f"{pr_num}: {all_path_num}")

                    cur_pr_str = {
                        "project": target_project,
                        "pr_nb": pr_num,
                        "nb_changed_funcs": 0,
                        "changed_funcs": [],
                        "nb_changed_pri_funcs": 0,
                        "changed_pri_funcs": [],
                        "nb_cross_enties": 0,
                        "cross_enties": "",
                        "nb_all_path": all_path_num,
                        "all_path_details": all_path_len_info
                    }
                elif block["message"].startswith("Querying") or block["message"].startswith("Cached result for querying"):
                    query_checked = True
                    if "The diff affects the following functions:" in block["content"]:
                        tmp = block["content"].split("The diff affects the following functions:", 1)[1]
                        cg_lines = tmp.split("\n")
                        changed_functions = cg_lines[0].rstrip(".").strip().split(", ") # list
                        if changed_functions[0]:
                            private_functions = [func for func in changed_functions if func.rsplit(".", 1)[1].startswith("_") and not func.rsplit(".", 1)[1].startswith("__")]
                            private_entry_lines = [line for line in cg_lines if line.startswith("Method #")]

                            cur_pr_str = {
                                "project": target_project,
                                "pr_nb": pr_num,
                                "nb_changed_funcs": len(changed_functions),
                                "changed_funcs": f"{changed_functions}",
                                "nb_changed_pri_funcs": len(private_functions),
                                "changed_pri_funcs": f"{private_functions}",
                                "nb_cross_enties": len(private_entry_lines),
                                "cross_enties": "\n".join(private_entry_lines),
                                "nb_all_path": all_path_num,
                                "all_path_details": all_path_len_info
                            }
                    # else:
                    #     print(f"{pr_num}: no changed function")
                            
            if query_checked == True:
                all_path_info.append(cur_pr_str)
                break # to junp out not to check other blocks

all_path_info.insert(0, Counter(all_path_nums))   
print(len(all_path_nums))  
print(Counter(all_path_nums))           
result_file = join(output_folder, f"{config_name}_cpath_meta.json")
with open(result_file, "w") as f:
    json.dump(all_path_info, f, indent=4)
            


