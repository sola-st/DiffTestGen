from collections import Counter
from dataclasses import dataclass, field
import glob
import io
from os import makedirs
from os.path import join
from statistics import mean
import sys
from testora.util.LogParser import parse_log_files
from testora.util.Logs import List
import matplotlib.pyplot as plt


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

    @staticmethod
    def _mean(values):
        return sum(values) / len(values) if values else 0.0

    def compute_averages(self):
        return Costs(
            [self._mean(self.test_gen)] if self.test_gen else [],
            [self._mean(self.test_refinement)] if self.test_refinement else [],
            [self._mean(self.test_exec)] if self.test_exec else [],
        )


def compute_cost_stats(pr_results, input_token_costs, output_token_costs, time_costs):
    checked_prs = [r for r in pr_results if not r.ignored]

    input_token_costs.test_gen.extend([r.input_tokens_test_gen for r in checked_prs])
    input_token_costs.test_refinement.extend([r.input_tokens_test_refinement for r in checked_prs])
    input_token_costs.test_exec.extend([r.input_tokens_test_exec for r in checked_prs])

    output_token_costs.test_gen.extend([r.output_tokens_test_gen for r in checked_prs])
    output_token_costs.test_refinement.extend([r.output_tokens_test_refinement for r in checked_prs])
    output_token_costs.test_exec.extend([r.output_tokens_test_exec for r in checked_prs])

    time_costs.test_gen.extend([r.time_taken_test_gen.total_seconds() / 60 for r in checked_prs])
    time_costs.test_refinement.extend([r.time_taken_test_refinement.total_seconds() / 60 for r in checked_prs])
    time_costs.test_exec.extend([r.time_taken_test_exec.total_seconds() / 60 for r in checked_prs])


def run_and_save_meta(output_file, func, *args, **kwargs):
    buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = buffer
    try:
        result = func(*args, **kwargs)
    finally:
        sys.stdout = original_stdout

    content = buffer.getvalue()
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    return result


def compute_test_generation_stats(pr_results):
    checked_prs = [r for r in pr_results if not r.ignored]

    nbs_generated_tests = [r.nb_generated_tests for r in checked_prs]
    gen_tests_out = f"{min(nbs_generated_tests)} & / & {round(sum(nbs_generated_tests) / len(nbs_generated_tests))} & / & {max(nbs_generated_tests)}"
    print(f"Generated tests: (min & avg & max) {gen_tests_out}")

    nbs_test_executions = [r.nb_test_executions for r in checked_prs]
    total_execs_out = f"{min(nbs_test_executions)} & / & {round(sum(nbs_test_executions) / len(nbs_test_executions))} & / & {max(nbs_test_executions)}"
    print(f"Test executions: (min & avg & max) {total_execs_out}")

    nbs_test_non_failures = [r.nb_test_executions - r.nb_test_failures for r in checked_prs]
    non_failures_out = f"{min(nbs_test_non_failures)} & / & {round(sum(nbs_test_non_failures) / len(nbs_test_non_failures))} & / & {max(nbs_test_non_failures)}"
    print(f"Test non-failures: (min & avg & max) {non_failures_out}")

    nbs_diff_covered_tests = [r.nb_diff_covered_tests for r in checked_prs]
    diff_covered_out = f"{min(nbs_diff_covered_tests)} & / & {round(sum(nbs_diff_covered_tests) / len(nbs_diff_covered_tests))} & / & {max(nbs_diff_covered_tests)}"
    print(f"Tests with diff-coverage: (min & avg & max) {diff_covered_out}")

    avg_old_diff_coverages = [r.avg_old_diff_coverage for r in checked_prs]
    print(
        f"Avg old diff-coverage: (min & avg & max) {min(avg_old_diff_coverages)} & / & {round(sum(avg_old_diff_coverages) / len(avg_old_diff_coverages), 2)} & / & {max(avg_old_diff_coverages)}"
    )

    avg_new_diff_coverages = [r.avg_new_diff_coverage for r in checked_prs]
    print(
        f"Avg new diff-coverage: (min & avg & max) {min(avg_new_diff_coverages)} & / & {round(sum(avg_new_diff_coverages) / len(avg_new_diff_coverages), 2)} & / & {max(avg_new_diff_coverages)}"
    )

    return f"{gen_tests_out} & {diff_covered_out} & {total_execs_out} & {non_failures_out}"


def avg_tokens_per_PR(input_token_costs, output_token_costs):
    total_input_tokens = sum(input_token_costs.test_gen) + sum(input_token_costs.test_refinement) + sum(input_token_costs.test_exec)
    total_output_tokens = sum(output_token_costs.test_gen) + sum(output_token_costs.test_refinement) + sum(output_token_costs.test_exec)

    input_count = max(len(input_token_costs.test_gen), 1)
    output_count = max(len(output_token_costs.test_gen), 1)
    return total_input_tokens / input_count, total_output_tokens / output_count


def avg_money_per_PR(input_token_costs, output_token_costs):
    input_dollars_1m = 0.25
    output_dollars_1m = 2

    total_input_tokens = sum(input_token_costs.test_gen) + sum(input_token_costs.test_refinement) + sum(input_token_costs.test_exec)
    total_output_tokens = sum(output_token_costs.test_gen) + sum(output_token_costs.test_refinement) + sum(output_token_costs.test_exec)

    total_input_dollars = total_input_tokens * input_dollars_1m / 1e6
    total_output_dollars = total_output_tokens * output_dollars_1m / 1e6

    input_count = max(len(input_token_costs.test_gen), 1)
    output_count = max(len(output_token_costs.test_gen), 1)
    return total_input_dollars / input_count, total_output_dollars / output_count


class PRAnalysisStats:
    def __init__(self, iteration, base_dir, output_folder):
        self.iteration = iteration
        self.base_dir = base_dir
        self.output_folder = output_folder
        makedirs(self.output_folder, exist_ok=True)

    def parse_pr_results(self, project, pr_list):
        path = join(self.base_dir, project, "*.json")
        json_files = glob.glob(path)

        filtered_files = []
        for json_file in json_files:
            pr_number = int(json_file.split('/')[-1].split('_')[0])
            if pr_number in pr_list:
                filtered_files.append(json_file)

        pr_results, _ = parse_log_files(filtered_files)
        return pr_results

    def compute_general_stats(self, pr_results):
        print(f"Total PRs: {len(pr_results)}")
        ignored_prs = [r for r in pr_results if r.ignored]
        print(f"Ignored PRs: {len(ignored_prs)}")
        reasons_ignored = Counter(r.ignored_reason for r in ignored_prs)
        print(f"Reasons for Ignored PRs: {reasons_ignored}")
        checked_prs = [r for r in pr_results if not r.ignored]
        print(f"Checked PRs: {len(checked_prs)}")
        pr_with_different_behavior = [r for r in checked_prs if r.nb_different_behavior > 0]
        print(f"PRs with different behavior: {len(pr_with_different_behavior)}")
        return f"{len(pr_results)} & {len(ignored_prs)} & {len(checked_prs)} & {len(pr_with_different_behavior)}"

    def print_and_plot_token_results(self, input_token_costs, output_token_costs):
        total_token_costs = input_token_costs + output_token_costs

        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.boxplot([
            total_token_costs.test_gen,
            total_token_costs.test_refinement,
            total_token_costs.test_exec,
        ])
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(["Test\n generation", "Test\n refinement", "Test\n execution"])
        ax.set_ylabel("Token costs")
        target_file = f"{self.output_folder}/token_costs.pdf"
        plt.tight_layout()
        plt.savefig(target_file)

        print(f"\\newcommand{{\\tokensTestGenPerPR}}{{{round(mean(total_token_costs.test_gen) if total_token_costs.test_gen else 0)}}}")
        print(f"\\newcommand{{\\tokensTestRefinementPerPR}}{{{round(mean(total_token_costs.test_refinement) if total_token_costs.test_refinement else 0)}}}")
        print(f"\\newcommand{{\\tokensTestExecPerPR}}{{{round(mean(total_token_costs.test_exec) if total_token_costs.test_exec else 0)}}}")

        avg_input_dollars, avg_output_dollars = avg_money_per_PR(input_token_costs, output_token_costs)
        print("\\newcommand{\\dollarsPerPR}{" + str(round(avg_input_dollars + avg_output_dollars, 5)) + "}")

        avg_input_tokens, avg_output_tokens = avg_tokens_per_PR(input_token_costs, output_token_costs)
        print(f"\\newcommand{{\\inputTokensPerPR}}{{{round(avg_input_tokens)}}}")
        print(f"\\newcommand{{\\outputTokensPerPR}}{{{round(avg_output_tokens)}}}")
        print(f"\\newcommand{{\\totalTokensPerPR}}{{{round(avg_input_tokens + avg_output_tokens)}}}")

    def print_and_plot_time_results(self, time_costs):
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.boxplot([time_costs.test_gen, time_costs.test_refinement, time_costs.test_exec])
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(["Test\n generation", "Test\n refinement", "Test\n execution"])
        ax.set_ylabel("Time (minutes)")
        target_file = f"{self.output_folder}/time_costs.pdf"
        plt.tight_layout()
        plt.savefig(target_file)

        avg_time_per_PR = sum(time_costs.test_gen + time_costs.test_refinement + time_costs.test_exec) / len(time_costs.test_gen) if time_costs.test_gen else 0.0
        print("\\newcommand{\\minutesPerPR}{" + str(round(avg_time_per_PR, 2)) + "}")

    def main(self):
        general_table_rows = []
        test_generation_table_rows = []
        general_stats = []
        test_generation_stats = []

        input_token_costs = Costs()
        output_token_costs = Costs()
        time_costs = Costs()

        for project, num in project_info.items():
            print(f"\n-------------- {project} -------------")
            pr_file = join("data", "meta", "pr_nums_checks", f"{project}_PRs_subset{num}.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            pr_list = [int(pr) for pr in prs]

            pr_results = self.parse_pr_results(project, pr_list)
            ignored_prs = [r for r in pr_results if r.ignored]
            checked_prs = [r for r in pr_results if not r.ignored]
            pr_with_different_behavior = [r for r in checked_prs if r.nb_different_behavior > 0]
            general_stats.append({
                "project": project,
                "total_prs": len(pr_results),
                "ignored_prs": len(ignored_prs),
                "checked_prs": len(checked_prs),
                "different_behavior": len(pr_with_different_behavior),
            })

            row = self.compute_general_stats(pr_results)
            general_table_rows.append(f"{project} & {row} \\")

            checked_prs = [r for r in pr_results if not r.ignored]
            nbs_generated_tests = [r.nb_generated_tests for r in checked_prs]
            nbs_test_executions = [r.nb_test_executions for r in checked_prs]
            nbs_test_non_failures = [r.nb_test_executions - r.nb_test_failures for r in checked_prs]
            nbs_diff_covered_tests = [r.nb_diff_covered_tests for r in checked_prs]
            test_generation_stats.append({
                "project": project,
                "generated_tests": {"min": min(nbs_generated_tests), "avg": sum(nbs_generated_tests) / len(nbs_generated_tests), "max": max(nbs_generated_tests)},
                "test_executions": {"min": min(nbs_test_executions), "avg": sum(nbs_test_executions) / len(nbs_test_executions), "max": max(nbs_test_executions)},
                "non_failures": {"min": min(nbs_test_non_failures), "avg": sum(nbs_test_non_failures) / len(nbs_test_non_failures), "max": max(nbs_test_non_failures)},
                "diff_covered_tests": {"min": min(nbs_diff_covered_tests), "avg": sum(nbs_diff_covered_tests) / len(nbs_diff_covered_tests), "max": max(nbs_diff_covered_tests)},
            })

            row = compute_test_generation_stats(pr_results)
            test_generation_table_rows.append(f"{project} & {row} \\")

            compute_cost_stats(pr_results, input_token_costs, output_token_costs, time_costs)

        print("\n\n")
        print("Table w/ general stats:\n")
        print("\n".join(general_table_rows))

        print("\n\n")
        print("Table w/ test generation stats:\n")
        print("\n".join(test_generation_table_rows))
        print("\n\n")

        self.print_and_plot_token_results(input_token_costs, output_token_costs)
        self.print_and_plot_time_results(time_costs)
        return input_token_costs, output_token_costs, time_costs, general_stats, test_generation_stats


if __name__ == "__main__":
    project_info = {
        "keras": 133,
        "marshmallow": 53,
        "pandas": 127,
        "scipy": 126,
    }

    def build_summary(title, general_rows, test_rows, avg_input_tokens, avg_output_tokens, avg_minutes, avg_cost_table):
        avg_total_tokens = avg_input_tokens + avg_output_tokens
        avg_total_dollars = (avg_input_tokens * 0.25 / 1e6) + (avg_output_tokens * 2 / 1e6)
        summary_lines = [
            title,
            "",
            "Table w/ general stats:",
            *general_rows,
            "",
            "Table w/ test generation stats:",
            *test_rows,
            "",
            f"Average input tokens per PR: {avg_input_tokens:.2f}",
            f"Average output tokens per PR: {avg_output_tokens:.2f}",
            f"Average total tokens per PR: {avg_total_tokens:.2f}",
            f"Average minutes per PR: {avg_minutes:.2f}",
            f"\\newcommand{{\\dollarsPerPR}}{{{avg_total_dollars:.5f}}}",
            f"\\newcommand{{\\inputTokensPerPR}}{{{round(avg_input_tokens)}}}",
            f"\\newcommand{{\\outputTokensPerPR}}{{{round(avg_output_tokens)}}}",
            f"\\newcommand{{\\totalTokensPerPR}}{{{round(avg_total_tokens)}}}",
            f"\\newcommand{{\\minutesPerPR}}{{{round(avg_minutes, 2)}}}",
            "",
            avg_cost_table,
        ]
        print(f"\n{title}\n")
        for line in summary_lines[1:]:
            print(line)
        return "\n".join(summary_lines) + "\n"

    def summarize_runs(general_run_entries, test_run_entries):
        general_rows = []
        test_rows = []

        for project in project_info:
            total_vals = [entry["total_prs"] for run in general_run_entries for entry in run if entry["project"] == project]
            ignored_vals = [entry["ignored_prs"] for run in general_run_entries for entry in run if entry["project"] == project]
            checked_vals = [entry["checked_prs"] for run in general_run_entries for entry in run if entry["project"] == project]
            diff_vals = [entry["different_behavior"] for run in general_run_entries for entry in run if entry["project"] == project]

            avg_total = mean(total_vals) if total_vals else 0.0
            avg_ignored = mean(ignored_vals) if ignored_vals else 0.0
            avg_checked = mean(checked_vals) if checked_vals else 0.0
            avg_diff = mean(diff_vals) if diff_vals else 0.0
            general_rows.append(f"{project} & {avg_total:.0f} & {avg_ignored:.0f} & {avg_checked:.0f} & {avg_diff:.0f} \\")

        for project in project_info:
            generated_vals = [entry["generated_tests"]["avg"] for run in test_run_entries for entry in run if entry["project"] == project]
            diff_vals = [entry["diff_covered_tests"]["avg"] for run in test_run_entries for entry in run if entry["project"] == project]
            exec_vals = [entry["test_executions"]["avg"] for run in test_run_entries for entry in run if entry["project"] == project]
            non_fail_vals = [entry["non_failures"]["avg"] for run in test_run_entries for entry in run if entry["project"] == project]

            min_generated = [entry["generated_tests"]["min"] for run in test_run_entries for entry in run if entry["project"] == project]
            max_generated = [entry["generated_tests"]["max"] for run in test_run_entries for entry in run if entry["project"] == project]
            min_diff = [entry["diff_covered_tests"]["min"] for run in test_run_entries for entry in run if entry["project"] == project]
            max_diff = [entry["diff_covered_tests"]["max"] for run in test_run_entries for entry in run if entry["project"] == project]
            min_exec = [entry["test_executions"]["min"] for run in test_run_entries for entry in run if entry["project"] == project]
            max_exec = [entry["test_executions"]["max"] for run in test_run_entries for entry in run if entry["project"] == project]
            min_non_fail = [entry["non_failures"]["min"] for run in test_run_entries for entry in run if entry["project"] == project]
            max_non_fail = [entry["non_failures"]["max"] for run in test_run_entries for entry in run if entry["project"] == project]

            avg_generated = mean(generated_vals) if generated_vals else 0.0
            avg_diff = mean(diff_vals) if diff_vals else 0.0
            avg_exec = mean(exec_vals) if exec_vals else 0.0
            avg_non_fail = mean(non_fail_vals) if non_fail_vals else 0.0
            test_rows.append(
                f"{project} & {min(min_generated):.0f} & / & {avg_generated:.0f} & / & {max(max_generated):.0f} & "
                f"{min(min_diff):.0f} & / & {avg_diff:.0f} & / & {max(max_diff):.0f} & "
                f"{min(min_exec):.0f} & / & {avg_exec:.0f} & / & {max(max_exec):.0f} & "
                f"{min(min_non_fail):.0f} & / & {avg_non_fail:.0f} & / & {max(max_non_fail):.0f} \\")

        return general_rows, test_rows

    def build_cost_table(per_name_runs):
        tool_labels = {
            "testora": "Testora",
            "testora_pp": "Testora++",
            "difftestgen": "\\name{}",
        }
        columns = []
        for name in ["testora", "testora_pp", "difftestgen"]:
            runs = per_name_runs.get(name, [])
            if not runs:
                columns.append((tool_labels[name], 0.0, 0.0, 0.0, 0.0))
                continue

            input_tokens = [avg_tokens_per_PR(run["input_token_costs"], run["output_token_costs"])[0] for run in runs]
            output_tokens = [avg_tokens_per_PR(run["input_token_costs"], run["output_token_costs"])[1] for run in runs]
            dollar_values = [
                avg_money_per_PR(run["input_token_costs"], run["output_token_costs"])[0] + avg_money_per_PR(run["input_token_costs"], run["output_token_costs"])[1]
                for run in runs
            ]
            minute_values = [
                sum(run["time_costs"].test_gen + run["time_costs"].test_refinement + run["time_costs"].test_exec) / len(run["time_costs"].test_gen)
                if run["time_costs"].test_gen else 0.0
                for run in runs
            ]

            columns.append((
                tool_labels[name],
                mean(input_tokens),
                mean(output_tokens),
                mean(dollar_values),
                mean(minute_values),
            ))

        rows = [
            ("Tokens", "Input", columns[0][1], columns[1][1], columns[2][1]),
            ("", "Output", columns[0][2], columns[1][2], columns[2][2]),
            ("", "Total", columns[0][1] + columns[0][2], columns[1][1] + columns[1][2], columns[2][1] + columns[2][2]),
            ("Cost", "Dollars", columns[0][3], columns[1][3], columns[2][3]),
            ("Time", "Minutes", columns[0][4], columns[1][4], columns[2][4]),
        ]

        table_lines = [
            "\\begin{table}[t]",
            "  \\centering",
            "  \\caption{Per-PR cost in terms of tokens, money, and time. \\todo{repetitions}}",
            "  \\begin{tabular}{@{}llrrr@{}}",
            "    \\toprule",
            "    &  & Testora & Testora++ & \\name{}\\\\",
            "    \\midrule",
            "    Tokens & Input   & " + f"{rows[0][2]:,.0f}" + " & " + f"{rows[0][3]:,.0f}" + " & " + f"{rows[0][4]:,.0f}" + "  " + "\\\\",
            "    & Output  & " + f"{rows[1][2]:,.0f}" + " & " + f"{rows[1][3]:,.0f}" + " & " + f"{rows[1][4]:,.0f}" + " " + "\\\\",
            "    & Total  & " + f"{rows[2][2]:,.0f}" + " & " + f"{rows[2][3]:,.0f}" + " & " + f"{rows[2][4]:,.0f}" + " " + "\\\\",
            "    \\midrule",
            "    Cost & Dollars  & " + f"{rows[3][2]:.3f}" + " & " + f"{rows[3][3]:.3f}" + " & " + f"{rows[3][4]:.3f}" + "  " + "\\\\",
            "    \\midrule",
            "    Time & Minutes  & " + f"{rows[4][2]:.2f}" + " & " + f"{rows[4][3]:.2f}" + " & " + f"{rows[4][4]:.2f}" + "  " + "\\\\",
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\label{tab:costs}",
            "\\end{table}",
        ]
        return "\n".join(table_lines)

    names = ["testora", "testora_pp", "difftestgen"]
    iteration_max = 3
    per_name_runs = {name: [] for name in names}
    all_runs = []

    for iteration in range(iteration_max):
        for name in names:
            base_dir = f"data/results/gpt-5-mini-2025-08-07/iter_{iteration}/log_{name}/"
            output_folder = join("data", "results", "table_and_plots", "costs", name, f"iter_{iteration}")
            analysis = PRAnalysisStats(iteration, base_dir, output_folder)
            repetition_meta_path = join(output_folder, f"meta_iter_{iteration}.txt")
            input_token_costs, output_token_costs, time_costs, general_stats, test_generation_stats = run_and_save_meta(
                repetition_meta_path,
                analysis.main,
            )

            run_entry = {
                "iteration": iteration,
                "name": name,
                "general_stats": general_stats,
                "test_generation_stats": test_generation_stats,
                "input_token_costs": input_token_costs,
                "output_token_costs": output_token_costs,
                "time_costs": time_costs,
            }
            per_name_runs[name].append(run_entry)
            all_runs.append(run_entry)

    meta_summary_dir = join("data", "results", "table_and_plots", "costs")
    makedirs(meta_summary_dir, exist_ok=True)
    avg_cost_table = build_cost_table(per_name_runs)
    avg_table_tex_path = join(meta_summary_dir, "avg_cost_table.tex")
    with open(avg_table_tex_path, "w", encoding="utf-8") as f:
        f.write(avg_cost_table)
    print(f"Average cost table written to: {avg_table_tex_path}")

    for name, runs in per_name_runs.items():
        general_rows, test_rows = summarize_runs(
            [run["general_stats"] for run in runs],
            [run["test_generation_stats"] for run in runs],
        )
        name_input_tokens = [avg_tokens_per_PR(run["input_token_costs"], run["output_token_costs"])[0] for run in runs]
        name_output_tokens = [avg_tokens_per_PR(run["input_token_costs"], run["output_token_costs"])[1] for run in runs]
        name_minutes = [sum(run["time_costs"].test_gen + run["time_costs"].test_refinement + run["time_costs"].test_exec) / len(run["time_costs"].test_gen) if run["time_costs"].test_gen else 0.0 for run in runs]
        summary_path = join(meta_summary_dir, name, f"meta_{name}_avg.txt")
        makedirs(join(meta_summary_dir, name), exist_ok=True)
        run_and_save_meta(
            summary_path,
            lambda name=name, general_rows=general_rows, test_rows=test_rows, avg_in=mean(name_input_tokens), avg_out=mean(name_output_tokens), avg_min=mean(name_minutes), avg_cost_table=avg_cost_table: build_summary(
                f"Summary for {name} across repetitions:",
                general_rows,
                test_rows,
                avg_in,
                avg_out,
                avg_min,
                avg_cost_table,
            ),
        )
        print(f"Summary written to: {summary_path}")
