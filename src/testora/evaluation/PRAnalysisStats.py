from collections import Counter
from dataclasses import dataclass, field
import glob
from os import listdir, makedirs
from os.path import join
from statistics import mean
from testora.util.LogParser import parse_log_files
from testora.util.Logs import List
import matplotlib.pyplot as plt

# PR ranges used for RQ2 (test generation) and RQ4 (costs)
# project_to_pr_range = {
#     "keras": [20264, 20856],
#     "marshmallow": [2277, 2809],
#     "pandas": [59908, 60843],
#     # "scipy": [21652, 22457],
# }


project_info = {
    "keras": 133,
    "marshmallow": 53,
    "pandas": 127,
    "scipy": 126,
}

name = "testora" # "testora" # "difftestgen"
base_dir = f"data/results/gpt-5-mini-2025-08-07/iter_0/log_{name}/"
output_folder = f"data/results/table_and_plots/costs/{name}"
makedirs(output_folder, exist_ok=True)


@dataclass
class Costs:
    test_gen: List[float] = field(default_factory=list)
    test_refinement: List[float] = field(default_factory=list)
    test_exec: List[float] = field(default_factory=list)

    def __add__(self, other):
        return Costs(
            self.test_gen + other.test_gen,
            self.test_refinement + other.test_refinement,
            self.test_exec + other.test_exec,
        )


def parse_pr_results(project, pr_list):
    # list all .json files in base_dir/project
    path = join(base_dir, project, "*.json")
    json_files = glob.glob(path)

    # filter files that are in the PR range
    filtered_files = []
    for json_file in json_files:
        pr_number = int(json_file.split('/')[-1].split('_')[0])
        if pr_number in pr_list:
            filtered_files.append(json_file)

    # parse the log files
    pr_results, _ = parse_log_files(filtered_files)

    return pr_results


def compute_general_stats(pr_results):
    print(f"Total PRs: {len(pr_results)}")
    ignored_prs = [r for r in pr_results if r.ignored]
    print(f"Ignored PRs: {len(ignored_prs)}")
    reasons_ignored = Counter(r.ignored_reason for r in ignored_prs)
    print(f"Reasons for Ignored PRs: {reasons_ignored}")
    checked_prs = [r for r in pr_results if not r.ignored]
    print(f"Checked PRs: {len(checked_prs)}")
    pr_with_different_behavior = [
        r for r in checked_prs if r.nb_different_behavior > 0]
    print(f"PRs with different behavior: {len(pr_with_different_behavior)}")

    return f"{len(pr_results)} & {len(ignored_prs)} & {len(checked_prs)} & {len(pr_with_different_behavior)}"


def compute_test_generation_stats(pr_results):
    checked_prs = [r for r in pr_results if not r.ignored]

    nbs_generated_tests = [r.nb_generated_tests for r in checked_prs]
    gen_tests_out = f"""{min(nbs_generated_tests)} & / & {round(sum(nbs_generated_tests) /
                                                        len(nbs_generated_tests))} & / & {max(nbs_generated_tests)}"""
    print(f"Generated tests: (min & avg & max) {gen_tests_out}")

    nbs_test_executions = [r.nb_test_executions for r in checked_prs]
    total_execs_out = f"{min(nbs_test_executions)} & / & {round(sum(nbs_test_executions)/len(nbs_test_executions))} & / & {max(nbs_test_executions)}"
    print(f"Test executions: (min & avg & max) {total_execs_out}")

    nbs_test_non_failures = [r.nb_test_executions - r.nb_test_failures for r in checked_prs]
    non_failures_out = f"{min(nbs_test_non_failures)} & / & {round(sum(nbs_test_non_failures)/len(nbs_test_non_failures))} & / & {max(nbs_test_non_failures)}"
    print(f"Test non-failures: (min & avg & max) {non_failures_out}")

    nbs_diff_covered_tests = [r.nb_diff_covered_tests for r in checked_prs]
    diff_covered_out = f"{min(nbs_diff_covered_tests)} & / & {round(sum(nbs_diff_covered_tests)/len(nbs_diff_covered_tests))} & / & {max(nbs_diff_covered_tests)}"
    print(f"Tests with diff-coverage: (min & avg & max) {diff_covered_out}")

    avg_old_diff_coverages = [r.avg_old_diff_coverage for r in checked_prs]
    print(
        f"Avg old diff-coverage: (min & avg & max) {min(avg_old_diff_coverages)} & / & {round(sum(avg_old_diff_coverages)/len(avg_old_diff_coverages), 2)} & / & {max(avg_old_diff_coverages)}")

    avg_new_diff_coverages = [r.avg_new_diff_coverage for r in checked_prs]
    print(
        f"Avg new diff-coverage: (min & avg & max) {min(avg_new_diff_coverages)} & / & {round(sum(avg_new_diff_coverages)/len(avg_new_diff_coverages), 2)} & / & {max(avg_new_diff_coverages)}")

    return f"{gen_tests_out} & {diff_covered_out} & {total_execs_out} & {non_failures_out}"


def compute_cost_stats(pr_results, input_token_costs, output_token_costs, time_costs):
    checked_prs = [r for r in pr_results if not r.ignored]

    # append token costs per PR to the global list
    input_token_costs.test_gen.extend([r.input_tokens_test_gen for r in checked_prs])
    input_token_costs.test_refinement.extend([r.input_tokens_test_refinement for r in checked_prs])
    input_token_costs.test_exec.extend([r.input_tokens_test_exec for r in checked_prs])

    output_token_costs.test_gen.extend([r.output_tokens_test_gen for r in checked_prs])
    output_token_costs.test_refinement.extend([r.output_tokens_test_refinement for r in checked_prs])
    output_token_costs.test_exec.extend([r.output_tokens_test_exec for r in checked_prs])

    # append time costs per PR to the global list
    time_costs.test_gen.extend([r.time_taken_test_gen.total_seconds() / 60 for r in checked_prs])
    time_costs.test_refinement.extend([r.time_taken_test_refinement.total_seconds() / 60 for r in checked_prs])
    time_costs.test_exec.extend([r.time_taken_test_exec.total_seconds() / 60 for r in checked_prs])


def avg_tokens_per_PR(input_token_costs, output_token_costs):
    total_input_tokens = sum(input_token_costs.test_gen) + \
        sum(input_token_costs.test_refinement) + \
        sum(input_token_costs.test_exec)
    total_output_tokens = sum(output_token_costs.test_gen) + \
        sum(output_token_costs.test_refinement) + \
        sum(output_token_costs.test_exec)

    return total_input_tokens / len(input_token_costs.test_gen), total_output_tokens / len(output_token_costs.test_gen)


def avg_money_per_PR(input_token_costs, output_token_costs):
    # # OpenAI pricing as of Feb 17, 2025
    # input_dollars_1m = 0.15
    # output_dollars_1m = 0.6

    # OpenAI pricing as of June 1st, 2026, Gpt-5-mini
    input_dollars_1m = 0.25 # 
    # what about cached input??
    output_dollars_1m = 2

    total_input_tokens = sum(input_token_costs.test_gen) + \
        sum(input_token_costs.test_refinement) + \
        sum(input_token_costs.test_exec)
    total_output_tokens = sum(output_token_costs.test_gen) + \
        sum(output_token_costs.test_refinement) + \
        sum(output_token_costs.test_exec)

    total_input_dollars = total_input_tokens * input_dollars_1m / 1e6
    total_output_dollars = total_output_tokens * output_dollars_1m / 1e6

    return total_input_dollars / len(input_token_costs.test_gen), total_output_dollars / len(output_token_costs.test_gen)


def print_and_plot_token_results(input_token_costs, output_token_costs):
    total_token_costs = input_token_costs + output_token_costs

    # box plot with four points on x axis (test generation, test refinement, test execution) and y axis showing the token costs
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.boxplot([total_token_costs.test_gen, total_token_costs.test_refinement,
               total_token_costs.test_exec])
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Test\n generation", "Test\n refinement", "Test\n execution"])
    ax.set_ylabel("Token costs")
    target_file = f"{output_folder}/token_costs.pdf"
    plt.tight_layout()
    plt.savefig(target_file)

    print(f"\\newcommand{{\\tokensTestGenPerPR}}{{{round(mean(total_token_costs.test_gen))}}}")
    print(f"\\newcommand{{\\tokensTestRefinementPerPR}}{{{round(mean(total_token_costs.test_refinement))}}}")
    print(f"\\newcommand{{\\tokensTestExecPerPR}}{{{round(mean(total_token_costs.test_exec))}}}")

    avg_input_dollars, avg_output_dollars = avg_money_per_PR(input_token_costs, output_token_costs)
    print("\\newcommand{\dollarsPerPR}{" + str(round(avg_input_dollars + avg_output_dollars, 5))+"}")

    avg_input_tokens, avg_output_tokens = avg_tokens_per_PR(input_token_costs, output_token_costs)
    print(f"\\newcommand{{\\inputTokensPerPR}}{{{round(avg_input_tokens)}}}")
    print(f"\\newcommand{{\\outputTokensPerPR}}{{{round(avg_output_tokens)}}}")
    print(f"\\newcommand{{\\totalTokensPerPR}}{{{round(avg_input_tokens + avg_output_tokens)}}}")


def print_and_plot_time_results(time_costs):
    # box plot with four points on x axis (test generation, test refinement, test execution, classification) and y axis showing the time costs
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.boxplot([time_costs.test_gen, time_costs.test_refinement, time_costs.test_exec])
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Test\n generation", "Test\n refinement", "Test\n execution"])
    ax.set_ylabel("Time (minutes)")
    target_file = f"{output_folder}/time_costs.pdf"
    plt.tight_layout()
    plt.savefig(target_file)

    avg_time_per_PR = sum(time_costs.test_gen +
                          time_costs.test_refinement +
                          time_costs.test_exec) / len(time_costs.test_gen)
    print("\\newcommand{\\minutesPerPR}{"+str(round(avg_time_per_PR, 2))+"}")


if __name__ == "__main__":
    general_table_rows = []
    test_generation_table_rows = []

    input_token_costs = Costs()
    output_token_costs = Costs()
    time_costs = Costs()
    for project, num in project_info.items():
        print(f"\n-------------- {project} -------------")
        pr_file = join("data", "meta", "pr_nums_checks", f"{project}_PRs_subset{num}.txt")
        with open(pr_file, "r") as f:
            prs = f.readlines()
        pr_list = [int(pr) for pr in prs]
        # if project == "keras":
        #     pr_list = pr_list[:23]
        # elif project == "pandas":
        #     pr_list = pr_list[:22]

        # log_folder = join("data/results/gpt-5-mini-2025-08-07/iter_0_100/log_testora", project)
        # pr_list = []
        # log_files = listdir(log_folder)
        # for file in log_files:
        #     pr_num = int(file.split("_", 1)[0])
        #     pr_list.append(pr_num)

        pr_results = parse_pr_results(project, pr_list)

        row = compute_general_stats(pr_results)
        general_table_rows.append(f"{project} & {row} \\\\")

        row = compute_test_generation_stats(pr_results)
        test_generation_table_rows.append(f"{project} & {row} \\\\")

        compute_cost_stats(pr_results, input_token_costs, output_token_costs, time_costs)

    print("\n\n")
    print("Table w/ general stats:\n")
    print("\n".join(general_table_rows))

    print("\n\n")
    print("Table w/ test generation stats:\n")
    print("\n".join(test_generation_table_rows))
    print("\n\n")

    print_and_plot_token_results(input_token_costs, output_token_costs)
    print_and_plot_time_results(time_costs)
