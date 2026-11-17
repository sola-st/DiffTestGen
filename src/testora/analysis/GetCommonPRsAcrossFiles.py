import ast
import json
import random
from pathlib import Path
from typing import Dict, Set
from os.path import join


def _read_prs(file_path: Path) -> Set[str]:
    with open(file_path, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}


def _read_difftestgen_only_prs(file_path: Path) -> Dict[str, Set[int]]:
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    only_in_difftestgen_block = ast.literal_eval(data[0]["only_in_difftestgen"]) # this is a inner json string
    return {
        project: set(prs)
        for project, prs in only_in_difftestgen_block.items()
    }


def _read_testora_not_difftestgen_prs(file_path: Path) -> Dict[str, Dict[str, Set[int]]]:
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    testora_only_block = ast.literal_eval(data[0]["in_testora_not_dtg"])
    testora_pp_only_block = ast.literal_eval(data[0]["in_testora_pp_not_dtg"])
    return {
        project: {
            "testora": set(testora_only_block.get(project, set())),
            "testora_pp": set(testora_pp_only_block.get(project, set())),
        }
        for project in set(testora_only_block) | set(testora_pp_only_block)
    }


def _count_different_outputs(log_folder: Path, pr_num: int) -> int:
    log_files = sorted(log_folder.glob(f"{pr_num}_*.json"))
    if not log_files:
        raise FileNotFoundError(f"No log file found for PR {pr_num} in {log_folder}")

    with open(log_files[0], "r", encoding="utf-8") as file:
        entries = json.load(file)
    return sum(
        1
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("message"), str)
        and entry["message"].startswith("Different outputs")
    )

iteration_max = 3   
file_folder =  "data/results/table_and_plots/different_outputs_statistics"
model_version = "gpt-5-mini-2025-08-07"
random_seed = 42


# 1 Find common PRs across all repetitions that have no different outputs across the three approaches
iteration_files = [
    Path(file_folder) / f"iter_{iteration}/differ_outputs_meta/all_three_approaches_no_different_outputs_prs.txt"
    for iteration in range(iteration_max)
]
prs_by_iteration = [_read_prs(file_path) for file_path in iteration_files]

common_prs = set.intersection(*prs_by_iteration)
output_file = join(file_folder, "intersection_prs_no_different_outputs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(common_prs))
print(f"Wrote {len(common_prs)} common PRs to {output_file}")

all_unique_prs = set.union(*prs_by_iteration)
output_file = join(file_folder, "union_prs_no_different_outputs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(all_unique_prs))
print(f"Wrote {len(all_unique_prs)} unique PRs to {output_file}")


# 2 Find common PRs across all repetitions that are only in difftestgen

only_in_dtg_by_iteration = []
for iteration in range(iteration_max):
    difftestgen_only_file = join(file_folder, f"iter_{iteration}/differ_outputs_meta/difftestgen.json")
    only_in_dtg_by_iteration.append(
        _read_difftestgen_only_prs(Path(difftestgen_only_file))
    )

overall_only_in_dtg = [
    set().union(*prs_by_project.values())
    for prs_by_project in only_in_dtg_by_iteration
]
all_unique_prs = set.union(*overall_only_in_dtg)
output_file = join(file_folder, f"union_only_in_difftestgen_prs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(all_unique_prs))

unique_common_prs = set.intersection(*overall_only_in_dtg)
output_file = join(file_folder, f"intersection_only_in_difftestgen_prs_across_repetitions.txt")
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(unique_common_prs))
print(f"Wrote {len(unique_common_prs)} difftestgen-only PRs to {output_file}")

pr_iterations_by_project = {}
for iteration, prs_by_project in enumerate(only_in_dtg_by_iteration):
    for project, pr_nums in prs_by_project.items():
        for pr_num in pr_nums:
            pr_iterations_by_project.setdefault(project, {}).setdefault(pr_num, []).append(iteration)

rng = random.Random(random_seed)
pr_records = []
for project in sorted(pr_iterations_by_project):
    for pr_num, iterations in sorted(pr_iterations_by_project[project].items()):
        related_iterations = sorted(iterations)
        selected_iteration = rng.choice(related_iterations)
        log_folder = (
            Path("data/results")
            / model_version
            / f"iter_{selected_iteration}"
            / "log_difftestgen"
            / project
        )
        pr_records.append({
            "project": project,
            "pr_num": pr_num,
            "related_repetitions": related_iterations,
            "related_repetition_count": len(related_iterations),
            "random_seed": random_seed,
            "selected_repetition": selected_iteration,
            "different_output_test_count": _count_different_outputs(log_folder, pr_num),
            "classified_test_count": min(_count_different_outputs(log_folder, pr_num), 5)})

output_file = join(file_folder, "union_only_in_difftestgen_prs_across_repetitions.json")
project_summary = {}
for record in pr_records:
    project_data = project_summary.setdefault(
        record["project"],
        {"pr_count": 0, "different_output_test_count": 0, "classified_test_count": 0},
    )
    project_data["pr_count"] += 1
    project_data["different_output_test_count"] += record["different_output_test_count"]
    project_data["classified_test_count"] += record["classified_test_count"]

summary_record = {
    "summary": {
        "total_pr_count": len(pr_records),
        "total_different_output_test_count": sum(
            record["different_output_test_count"] for record in pr_records
        ),
        "total_classified_test_count": sum(
            record["classified_test_count"] for record in pr_records
        ),
        "by_project": project_summary,
    }
}
pr_records.insert(0, summary_record)
with open(output_file, "w", encoding="utf-8") as file:
    json.dump(pr_records, file, indent=4)
print(f"Wrote {len(pr_records)} PR records to {output_file}")


# 3 Find the union of PRs in testora or testora_pp, but not in difftestgen,
# across all repetitions.
testora_only_by_iteration = []
for iteration in range(iteration_max):
    difftestgen_file = join(file_folder, f"iter_{iteration}/differ_outputs_meta/difftestgen.json")
    testora_only_by_iteration.append(
        _read_testora_not_difftestgen_prs(Path(difftestgen_file))
    )

testora_only_pr_sources = {}
for iteration, prs_by_project in enumerate(testora_only_by_iteration):
    for project, prs_by_source in prs_by_project.items():
        for source, pr_nums in prs_by_source.items():
            for pr_num in pr_nums:
                pr_record = testora_only_pr_sources.setdefault(
                    (project, pr_num), {"sources": set(), "sources_by_iteration": {}}
                )
                pr_record["sources"].add(source)
                pr_record["sources_by_iteration"].setdefault(iteration, set()).add(source)

all_testora_only_prs = {pr_num for _, pr_num in testora_only_pr_sources}
output_file = join(
    file_folder,
    "union_only_in_testora_or_testora_pp_not_difftestgen_prs_across_repetitions.txt",
)
with open(output_file, "w", encoding="utf-8") as file:
    file.writelines(f"{record}\n" for record in sorted(all_testora_only_prs))
print(f"Wrote {len(all_testora_only_prs)} testora/testora_pp-only PRs to {output_file}")

details = []
for (project, pr_num), record in sorted(testora_only_pr_sources.items()):
    sources = sorted(record["sources"])
    details.append({
        "project": project,
        "pr_num": pr_num,
        "source": "both" if len(sources) == 2 else sources[0],
        "iterations": [
            {
                "iteration": iteration,
                "source": (
                    "both"
                    if len(iteration_sources) == 2
                    else next(iter(iteration_sources))
                ),
            }
            for iteration, iteration_sources in sorted(record["sources_by_iteration"].items())
        ],
    })

details_output_file = join(
    file_folder,
    "union_only_in_testora_or_testora_pp_not_difftestgen_prs_across_repetitions.json",
)
with open(details_output_file, "w", encoding="utf-8") as file:
    json.dump(details, file, indent=4)
print(f"Wrote details for {len(details)} testora/testora_pp-only PRs to {details_output_file}")
