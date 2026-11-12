import ast
import json
from pathlib import Path
from typing import Set
from os.path import join

def _read_prs(file_path: Path) -> Set[str]:
    with open(file_path, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}

def _read_difftestgen_only_prs(file_path: Path) -> Set[int]:
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    only_in_difftestgen_block = ast.literal_eval(data[0]["only_in_difftestgen"]) # this is a inner json string
    all_pr = []
    for prs in only_in_difftestgen_block.values():
        all_pr.extend(prs)
    return set(all_pr)

iteration_max = 3   
file_folder =  "data/results/table_and_plots/different_outputs_statistics"


# 1 Find common PRs across all repetitions that have no different outputs across the three approaches
iteration_files = [
    Path(file_folder) / f"iter_{iteration}/differ_outputs_meta/all_three_approaches_no_different_outputs_prs.txt"
    for iteration in range(iteration_max)
]
prs_by_iteration = [_read_prs(file_path) for file_path in iteration_files]
common_prs = set.intersection(*prs_by_iteration)

output_file = join(file_folder, "common_prs_no_different_outputs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(common_prs))
print(f"Wrote {len(common_prs)} common PRs to {output_file}")


# 2 Find common PRs across all repetitions that are only in difftestgen

overall_only_in_dtg = []
for iteration in range(iteration_max):
    difftestgen_only_file = join(file_folder, f"iter_{iteration}/differ_outputs_meta/difftestgen.json")
    difftestgen_only_prs = _read_difftestgen_only_prs(difftestgen_only_file)
    overall_only_in_dtg.append(difftestgen_only_prs)

all_unique_prs = set.union(*overall_only_in_dtg)
output_file = join(file_folder, f"union_only_in_difftestgen_prs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(all_unique_prs))

unique_common_prs = set.intersection(*overall_only_in_dtg)
output_file = join(file_folder, f"intersection_only_in_difftestgen_prs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(unique_common_prs))
print(f"Wrote {len(unique_common_prs)} difftestgen-only PRs to {output_file}")
