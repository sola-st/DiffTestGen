import ast
from collections import Counter
import json


# unique_in_dtg = {
#     'keras': [20280, 20302, 20443, 20469, 20491, 20530, 20580, 20594, 20610, 20615, 
#               20623, 20630, 20642, 20725, 20732, 20751, 20758, 20784, 20785, 20808, 20810, 20812, 20819, 20851], 
#     'marshmallow': [2706, 2709, 2752, 2779, 2803], 
#     'pandas': [60130, 60188, 60196, 60235, 60255, 60264, 60265, 60266, 60271, 60295, 60331, 60334, 60461, 60483, 60549, 60558, 60584, 60586, 60726], 
#     'scipy': [21730, 21751, 21784, 21799, 21808, 21871, 21944, 21948, 21980, 21984, 21991, 22024, 22048, 
#               22061, 22081, 22099, 22132, 22135, 22139, 22149, 22322, 22373]
# }

meta_file = "data/results/table_and_plots/different_outputs_statistics/iter_0/differ_outputs_meta/difftestgen.json"

with open(meta_file, "r") as f:
    meta = json.load(f)
             
unique_in_dtg = ast.literal_eval(meta[0]["only_in_difftestgen"])
diff_relevant_tests = {
    "overall": 0,
    "keras": 0,
    "marshmallow": 0,
    "pandas": 0,
    "scipy": 0
}
all_different_outputs = []

for info in meta[5:]:
    cur_project = info["project"]
    pr = info["pr_num"]
    if pr  in unique_in_dtg[cur_project]:
        different_output = info["different_outputs"]
        print(f"{pr}: {different_output}")
        diff_relevant_tests[cur_project] += different_output
        diff_relevant_tests["overall"] += different_output
        all_different_outputs.append(different_output)

print(diff_relevant_tests) #  {'overall': 576, 'keras': 193, 'marshmallow': 26, 'pandas': 120, 'scipy': 237}
c = Counter(all_different_outputs)
for k, v in sorted(c.items()):
    print(k, v)



