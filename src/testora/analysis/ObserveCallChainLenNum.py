import json
from os import listdir
from os.path import join


# to get the number of all shortest paths, and the corresponding avg.
log_len_info = []
path_nums = []

log_folder = "data/results/marshmallow_all_1210" # "data/results/pandas_1210"
for log_file in listdir(log_folder):
    if "logs_" in log_file and not "_unfinished" in log_file:
        try:
            with open(join(log_folder, log_file), "r") as f:
                info = json.load(f)
        except:
            print(log_file)
            continue

        for block in info:
            if "message" in block.keys():
                if  block["message"] == "Call graph length information":
                    pr = block["pr_nb"]
                    print(pr)
                    # e.g., "{\"shortest\": [2], \"shortest_avg\": 2.0, \"all\": [2], \"all_avg\": 2.0}"
                    call_chain_len_info = json.loads(block["content"])
                    log_len_info.append(f"{pr}\t{call_chain_len_info}")
                    path_nums.append(len(call_chain_len_info["shortest"]))
                    break
                elif "Call graph (" in block["message"]:
                    break # no call path len block, no private function changes

with open(f"local/call_len_{len(log_len_info)}.txt", "w") as f:
    f.writelines("\n".join(map(str, log_len_info)))

avg = sum(path_nums)/len(path_nums)
path_nums.insert(0, avg)
with open(f"local/num_entries_{len(path_nums)}.txt", "w") as f:
    f.writelines("\n".join(map(str, path_nums)))
