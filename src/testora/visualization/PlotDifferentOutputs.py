from os.path import join
import json
import os
from matplotlib import gridspec, pyplot as plt
import numpy as np



def plot_nbs_of_different_outputs(diff_nbs_pr_level, all_prs, title, result_pdf):
    # Compute standard deviation for each group
    stds = [np.std(group) for group in diff_nbs_pr_level]
    means = [np.mean(group) for group in diff_nbs_pr_level]
    x = np.arange(1, len(stds) + 1)

    # Plot standard deviation as error bars
    fig = plt.figure(figsize=(24, 8))
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])

    # Main plot
    ax_plot = fig.add_subplot(gs[0])
    ax_plot.errorbar(x, means, yerr=stds, fmt='o', capsize=5, color='orange', label='Std Dev')
    ax_plot.plot(x, means, color='blue', linestyle='--', marker='x', label='Mean')
    ax_plot.set_title(title + ' (Std Dev)')
    ax_plot.set_xlabel('PRs')
    ax_plot.set_ylabel('Coverage (%)')
    ax_plot.grid(True)
    ax_plot.legend()
    labels = [str(i+1) for i in range(len(stds))]
    ax_plot.set_xticks(x)
    ax_plot.set_xticklabels(labels)

    # Table subplot
    ax_table = fig.add_subplot(gs[1])
    ax_table.axis('off')  # Hide axes

    # Prepare max/min values for table
    max_vals = [f"{np.max(group)}" for group in diff_nbs_pr_level]
    min_vals = [f"{np.min(group)}" for group in diff_nbs_pr_level]

    # Create table data
    cell_text = [all_prs, max_vals, min_vals]
    row_labels = ['PR', 'Max', 'Min']
    col_labels = [str(i+1) for i in range(len(diff_nbs_pr_level))]

    table = ax_table.table(
        cellText=cell_text,
        rowLabels=row_labels,
        colLabels=col_labels,
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    plt.tight_layout()
    plt.savefig(result_pdf)
    plt.close()

def main():
    results_folder = join("data", "results")

    iterations = 5
    # option 1: for all projects
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]

    # option 2: for a single project
    # with open(".target_project", "r") as f:
    #     target_project = f.read().strip()
    # target_projects = [target_project]

    # target_projects = ["scipy"]

    config_versions = [
        [5, 8, 8, True]
        ]

    for config in config_versions:
        version_id = '_'.join(map(str, config))
        diff_nbs_pr_level = [[] for _ in range(40)] 
        pr_idx = 0
        all_prs = []

        for target_project in target_projects:
            pr_file = join("data", "meta", "pr_nums", f"{target_project}_PRs_subset10.txt")
            with open(pr_file, "r") as f:
                prs = f.readlines()
            pr_list = [int(pr) for pr in prs]
            all_prs.extend(pr_list)
            
            for pr in pr_list:
                pr_runs = []
                for iter in range(iterations):
                    log_folder = join(results_folder, f"iter_{iter}", f"log_{version_id}", target_project)
                    log_file_path = None
                    for fname in os.listdir(log_folder):
                        if str(pr) in fname:
                            log_file_path = join(log_folder, fname)
                            break
                    if log_file_path is None:
                        print(f"Iteration {iter}: No log file found for PR {pr} in {log_folder}")
                        pr_runs.append(0)  # If missing, fill with zero
                    else:
                        with open(log_file_path, "r") as f:
                            info = json.load(f) 
                        
                        diff_nb = 0
                        for info_block in info:
                            try:
                                msg = info_block["message"]
                                # e.g., "Generated 4 more tests. (4 tests before deduplication and cleaning)"
                                if msg.startswith("Different outputs"):
                                    diff_nb += 1
                            except:
                                pass
                        pr_runs.append(diff_nb)

                diff_nbs_pr_level[pr_idx] = pr_runs  # Store 5 runs for this PR
                pr_idx += 1 

        # Plot standard deviation for each PR
        title = "Different Outputs Across 5 Repetitions per PR"
        result_pdf = join(results_folder, "table_and_plots", f"Outputs_stddev_per_pr.pdf")
        plot_nbs_of_different_outputs(diff_nbs_pr_level, all_prs, title, result_pdf)


if __name__=="__main__":
    main()